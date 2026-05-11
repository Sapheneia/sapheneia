"""Thin async-friendly wrapper around influxdb-client (sync) using asyncio.to_thread."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

logger = logging.getLogger(__name__)

STOCK_PRICES_MEASUREMENT = "stock_prices"
BACKTEST_RESULTS_MEASUREMENT = "backtest_results"
BACKTEST_METRICS_MEASUREMENT = "backtest_metrics"


class InfluxStore:
    def __init__(self, url: str, token: str, org: str, bucket: str):
        self._client = InfluxDBClient(url=url, token=token, org=org)
        self._org = org
        self._bucket = bucket
        self._write_api = self._client.write_api(write_options=SYNCHRONOUS)
        self._query_api = self._client.query_api()

    @property
    def bucket(self) -> str:
        return self._bucket

    def close(self) -> None:
        self._client.close()

    async def health_ok(self) -> bool:
        def _check() -> bool:
            try:
                health = self._client.health()
                return getattr(health, "status", None) == "pass"
            except Exception:
                return False

        return await asyncio.to_thread(_check)

    async def wait_until_ready(self, attempts: int, delay_s: float) -> bool:
        for i in range(attempts):
            if await self.health_ok():
                return True
            logger.warning("InfluxDB not ready, retrying", extra={"attempt": i + 1})
            await asyncio.sleep(delay_s)
        return False

    async def latest_stock_timestamp(self, ticker: str) -> Optional[datetime]:
        """Return latest stored timestamp for ticker in last 30d, or None."""
        flux = (
            f'from(bucket: "{self._bucket}")\n'
            f'  |> range(start: -30d)\n'
            f'  |> filter(fn: (r) => r._measurement == "{STOCK_PRICES_MEASUREMENT}")\n'
            f'  |> filter(fn: (r) => r.ticker == "{ticker}")\n'
            f'  |> last()\n'
        )

        def _run() -> Optional[datetime]:
            tables = self._query_api.query(flux)
            for table in tables:
                for record in table.records:
                    return record.get_time()
            return None

        return await asyncio.to_thread(_run)

    async def write_stock_bars(self, ticker_tag: str, bars: List[dict]) -> int:
        """bars: from yahoo.fetch_chart. Returns count written."""
        if not bars:
            return 0

        def _run() -> int:
            points = []
            for bar in bars:
                p = (
                    Point(STOCK_PRICES_MEASUREMENT)
                    .tag("ticker", ticker_tag)
                    .field("open", bar["open"])
                    .field("high", bar["high"])
                    .field("low", bar["low"])
                    .field("close", bar["close"])
                    .field("adj_close", bar["adj_close"])
                    .field("volume", int(bar["volume"]))
                    .time(bar["time"], write_precision=WritePrecision.S)
                )
                points.append(p)
            self._write_api.write(bucket=self._bucket, org=self._org, record=points)
            return len(points)

        return await asyncio.to_thread(_run)

    async def query_stock_history(
        self, ticker: str, days: int, end_date: Optional[str]
    ) -> List[dict]:
        """Match Go: range start=-{days+10}d, optional stop={end_date}T23:59:59Z,
        pivot fields, sort ascending, then keep last `days` rows.
        """
        range_start = f"-{days + 10}d"
        if end_date:
            stop = f"{end_date}T23:59:59Z"
            range_clause = f"|> range(start: {range_start}, stop: {stop})"
        else:
            range_clause = f"|> range(start: {range_start})"

        flux = (
            f'from(bucket: "{self._bucket}")\n'
            f'  {range_clause}\n'
            f'  |> filter(fn: (r) => r._measurement == "{STOCK_PRICES_MEASUREMENT}")\n'
            f'  |> filter(fn: (r) => r.ticker == "{ticker}")\n'
            f'  |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")\n'
            f'  |> sort(columns: ["_time"], desc: false)\n'
        )

        def _run() -> List[dict]:
            rows: List[dict] = []
            tables = self._query_api.query(flux)
            for table in tables:
                for record in table.records:
                    values = record.values
                    rows.append(
                        {
                            "time": record.get_time(),
                            "open": float(values.get("open", 0.0) or 0.0),
                            "high": float(values.get("high", 0.0) or 0.0),
                            "low": float(values.get("low", 0.0) or 0.0),
                            "close": float(values.get("close", 0.0) or 0.0),
                            "adj_close": float(values.get("adj_close", 0.0) or 0.0),
                            "volume": int(values.get("volume", 0) or 0),
                        }
                    )
            rows.sort(key=lambda r: r["time"])
            if len(rows) > days:
                rows = rows[-days:]
            return rows

        return await asyncio.to_thread(_run)

    async def write_backtest_results(
        self,
        run_id: str,
        ticker: str,
        model: str,
        strategy: str,
        results: List[dict],
        metrics: dict,
    ) -> int:
        """Mirror Go handleWriteResults: per-day backtest_results points + one
        summary backtest_metrics point at the last date. Skips points whose
        date won't parse. Batches of 1000.
        """
        if not results:
            return 0

        tags = {
            "run_id": run_id,
            "ticker": ticker,
            "model": model,
            "strategy": strategy,
        }

        def _parse_date(s: str) -> Optional[datetime]:
            try:
                return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                return None

        def _run() -> int:
            points: List[Point] = []
            for r in results:
                t = _parse_date(r.get("date", ""))
                if t is None:
                    logger.warning("invalid date format, skipping point", extra={"date": r.get("date")})
                    continue
                p = Point(BACKTEST_RESULTS_MEASUREMENT)
                for tag_name, tag_value in tags.items():
                    p = p.tag(tag_name, tag_value)
                p = (
                    p.field("forecast", float(r.get("forecast", 0.0)))
                    .field("actual", float(r.get("actual", 0.0)))
                    .field("signal", str(r.get("signal", "")))
                    .field("position", float(r.get("position", 0.0)))
                    .field("cash", float(r.get("cash", 0.0)))
                    .field("portfolio_value", float(r.get("portfolio_value", 0.0)))
                    .time(t, write_precision=WritePrecision.S)
                )
                points.append(p)

            # summary metrics point at last date (uses last results entry's date,
            # falling back to now if it doesn't parse — matches Go's t, _ := time.Parse).
            last_date = results[-1].get("date", "")
            metrics_t = _parse_date(last_date) or datetime.now(timezone.utc)
            mp = Point(BACKTEST_METRICS_MEASUREMENT)
            for tag_name, tag_value in tags.items():
                mp = mp.tag(tag_name, tag_value)
            mp = (
                mp.field("sharpe_ratio", float(metrics.get("sharpe_ratio", 0.0)))
                .field("max_drawdown", float(metrics.get("max_drawdown", 0.0)))
                .field("cagr", float(metrics.get("cagr", 0.0)))
                .field("calmar_ratio", float(metrics.get("calmar_ratio", 0.0)))
                .field("win_rate", float(metrics.get("win_rate", 0.0)))
                .field("total_points", len(results))
                .time(metrics_t, write_precision=WritePrecision.S)
            )
            points.append(mp)

            for i in range(0, len(points), 1000):
                batch = points[i : i + 1000]
                self._write_api.write(bucket=self._bucket, org=self._org, record=batch)
            return len(points)

        return await asyncio.to_thread(_run)
