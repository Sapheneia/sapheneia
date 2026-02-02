"""
Data Service Client

Handles communication with the Go data service for
reading and writing time-series data.
"""

import httpx
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import os

logger = logging.getLogger(__name__)


@dataclass
class ResultPoint:
    """Single backtest result point."""
    date: str
    forecast: float
    actual: float
    signal: str
    position: float
    cash: float
    portfolio_value: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "date": self.date,
            "forecast": self.forecast,
            "actual": self.actual,
            "signal": self.signal,
            "position": self.position,
            "cash": self.cash,
            "portfolio_value": self.portfolio_value,
        }


@dataclass
class MetricsSummary:
    """Metrics summary for storage."""
    sharpe_ratio: float
    max_drawdown: float
    cagr: float
    calmar_ratio: float
    win_rate: float

    def to_dict(self) -> Dict[str, float]:
        return {
            "sharpe_ratio": self.sharpe_ratio,
            "max_drawdown": self.max_drawdown,
            "cagr": self.cagr,
            "calmar_ratio": self.calmar_ratio,
            "win_rate": self.win_rate,
        }

    @classmethod
    def from_metrics_response(cls, metrics) -> "MetricsSummary":
        """Create from MetricsResponse."""
        return cls(
            sharpe_ratio=metrics.sharpe_ratio,
            max_drawdown=metrics.max_drawdown,
            cagr=metrics.cagr,
            calmar_ratio=metrics.calmar_ratio,
            win_rate=metrics.win_rate,
        )


@dataclass
class DataPoint:
    """Single data point from query."""
    time: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    adj_close: float

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DataPoint":
        return cls(
            time=data.get("time", ""),
            open=data.get("open", 0.0),
            high=data.get("high", 0.0),
            low=data.get("low", 0.0),
            close=data.get("close", 0.0),
            volume=data.get("volume", 0),
            adj_close=data.get("adj_close", 0.0),
        )


class DataClient:
    """
    Client for the Go data service.

    Handles both reading historical data and writing backtest results.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: float = 60.0,
    ):
        self.base_url = base_url or os.getenv(
            "DATA_SERVICE_URL",
            "http://sapheneia-data:8000"
        )
        self.timeout = timeout

    def _build_headers(self, request_id: Optional[str] = None) -> Dict[str, str]:
        """Build HTTP headers with optional request ID."""
        headers = {"Content-Type": "application/json"}
        if request_id:
            headers["X-Request-ID"] = request_id
        return headers

    async def write_results(
        self,
        run_id: str,
        ticker: str,
        model: str,
        strategy: str,
        results: List[ResultPoint],
        metrics: MetricsSummary,
        request_id: Optional[str] = None,
    ) -> bool:
        """
        Write backtest results to InfluxDB.

        Args:
            run_id: Unique identifier for this backtest run
            ticker: Ticker symbol
            model: Model used for forecasting
            strategy: Trading strategy type
            results: List of result points
            metrics: Summary metrics
            request_id: Optional request ID for distributed tracing

        Returns:
            True if successful, False otherwise
        """
        payload = {
            "run_id": run_id,
            "ticker": ticker,
            "model": model,
            "strategy": strategy,
            "results": [r.to_dict() for r in results],
            "metrics": metrics.to_dict(),
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/v1/data/write_results",
                    json=payload,
                    headers=self._build_headers(request_id),
                )
                response.raise_for_status()

                data = response.json()
                logger.info(
                    f"Wrote {data.get('points_written', 0)} points "
                    f"for run_id={run_id}"
                )
                return True

        except httpx.HTTPStatusError as e:
            logger.error(f"Data service HTTP error: {e}")
            return False

        except httpx.RequestError as e:
            logger.error(f"Data service connection error: {e}")
            return False

        except Exception as e:
            logger.exception(f"Unexpected error writing results: {e}")
            return False

    async def query_data(
        self,
        ticker: str,
        days: int = 90,
        end_date: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> List[float]:
        """
        Query historical data from InfluxDB.

        Args:
            ticker: Ticker symbol
            days: Number of days of history
            end_date: Optional end date (for backtest mode)
            request_id: Optional request ID for distributed tracing

        Returns:
            List of close prices
        """
        payload: Dict[str, Any] = {
            "ticker": ticker,
            "days": days,
        }
        if end_date:
            payload["end_date"] = end_date

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/v1/data/query",
                    json=payload,
                    headers=self._build_headers(request_id),
                )
                response.raise_for_status()

                data = response.json()
                # Extract close prices from response
                return [point.get("close", 0.0) for point in data.get("data", [])]

        except httpx.HTTPStatusError as e:
            logger.error(f"Data service HTTP error: {e}")
            return []

        except httpx.RequestError as e:
            logger.error(f"Data service connection error: {e}")
            return []

        except Exception as e:
            logger.exception(f"Unexpected error querying data: {e}")
            return []

    async def query_data_full(
        self,
        ticker: str,
        days: int = 90,
        end_date: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> List[DataPoint]:
        """
        Query historical data with full OHLCV.

        Args:
            ticker: Ticker symbol
            days: Number of days of history
            end_date: Optional end date (for backtest mode)
            request_id: Optional request ID for distributed tracing

        Returns:
            List of DataPoint objects
        """
        payload: Dict[str, Any] = {
            "ticker": ticker,
            "days": days,
        }
        if end_date:
            payload["end_date"] = end_date

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/v1/data/query",
                    json=payload,
                    headers=self._build_headers(request_id),
                )
                response.raise_for_status()

                data = response.json()
                return [DataPoint.from_dict(point) for point in data.get("data", [])]

        except httpx.HTTPStatusError as e:
            logger.error(f"Data service HTTP error: {e}")
            return []

        except httpx.RequestError as e:
            logger.error(f"Data service connection error: {e}")
            return []

        except Exception as e:
            logger.exception(f"Unexpected error querying data: {e}")
            return []

    async def fetch_data(
        self,
        tickers: List[str],
        start_date: str,
        interval: str = "1d",
        request_id: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        Fetch data from Yahoo Finance and store in InfluxDB.

        Args:
            tickers: List of ticker symbols
            start_date: Start date (YYYY-MM-DD)
            interval: Data interval (1d, 1h, etc.)
            request_id: Optional request ID for distributed tracing

        Returns:
            Dict with results per ticker
        """
        payload = {
            "names": tickers,
            "start_date": start_date,
            "interval": interval,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/v1/data/fetch",
                    json=payload,
                    headers=self._build_headers(request_id),
                )
                response.raise_for_status()

                data = response.json()
                return data.get("details", {})

        except httpx.HTTPStatusError as e:
            logger.error(f"Data service HTTP error: {e}")
            return {}

        except httpx.RequestError as e:
            logger.error(f"Data service connection error: {e}")
            return {}

        except Exception as e:
            logger.exception(f"Unexpected error fetching data: {e}")
            return {}
