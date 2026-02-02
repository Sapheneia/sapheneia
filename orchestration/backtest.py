"""
Backtest Orchestrator

Implements the complete backtest loop:
data -> forecast -> trading -> state update -> metrics
"""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Callable, Awaitable
from dataclasses import dataclass, field

from .clients.trading_client import (
    TradingClient,
    PortfolioManager,
    TradeResult,
    StrategyType,
    PortfolioState,
)
from .clients.metrics_client import MetricsClient, MetricsResponse, prices_to_returns
from .service import InferenceService
from .schema import InferenceRequest, ContextData, HorizonSpec, Period, DataSource
from .adapters import parse_date, DateParseError

logger = logging.getLogger(__name__)


@dataclass
class BacktestConfig:
    """Configuration for backtest run."""
    ticker: str
    model: str
    start_date: str  # YYYY-MM-DD
    end_date: str    # YYYY-MM-DD
    initial_capital: float = 100000.0
    context_size: int = 90  # Days of context
    horizon_size: int = 10  # Days to forecast
    strategy_type: StrategyType = StrategyType.THRESHOLD
    strategy_params: Dict[str, Any] = field(default_factory=dict)
    risk_free_rate: float = 0.0
    step_days: int = 1  # Days between evaluations
    inference_timeout: Optional[float] = None  # Seconds, None uses service default

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "model": self.model,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "initial_capital": self.initial_capital,
            "context_size": self.context_size,
            "horizon_size": self.horizon_size,
            "strategy_type": self.strategy_type.value,
            "strategy_params": self.strategy_params,
            "risk_free_rate": self.risk_free_rate,
            "step_days": self.step_days,
            "inference_timeout": self.inference_timeout,
        }


@dataclass
class BacktestResult:
    """Result of a complete backtest."""
    config: BacktestConfig
    trades: List[TradeResult]
    equity_curve: List[float]
    metrics: MetricsResponse
    evaluation_dates: List[str]
    run_id: str = ""
    duration_seconds: float = 0.0

    @property
    def total_return(self) -> float:
        """Calculate total return."""
        if len(self.equity_curve) < 2:
            return 0.0
        return (self.equity_curve[-1] - self.equity_curve[0]) / self.equity_curve[0]

    @property
    def final_value(self) -> float:
        """Get final portfolio value."""
        return self.equity_curve[-1] if self.equity_curve else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "config": self.config.to_dict(),
            "total_trades": len(self.trades),
            "total_return": self.total_return,
            "final_value": self.final_value,
            "metrics": self.metrics.to_dict(),
            "evaluation_dates_count": len(self.evaluation_dates),
            "duration_seconds": self.duration_seconds,
        }


# Type alias for data provider function
DataProvider = Callable[[str, str, int], Awaitable[List[float]]]


async def run_backtest(
    config: BacktestConfig,
    data_provider: DataProvider,
    run_id: Optional[str] = None,
    checkpoint_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
) -> BacktestResult:
    """
    Run complete backtest with trading feedback loop.

    Args:
        config: Backtest configuration
        data_provider: Async function(ticker, end_date, days) -> List[float] prices
        run_id: Optional run identifier
        checkpoint_callback: Optional callback for checkpoints

    Returns:
        BacktestResult with trades, equity curve, and metrics
    """
    import time
    start_time = time.time()

    run_id = run_id or str(uuid.uuid4())[:8]

    logger.info("=" * 70)
    logger.info(f"BACKTEST STARTING run_id={run_id}")
    logger.info("=" * 70)
    logger.info(f"  Ticker: {config.ticker}")
    logger.info(f"  Model: {config.model}")
    logger.info(f"  Period: {config.start_date} to {config.end_date}")
    logger.info(f"  Capital: ${config.initial_capital:,.2f}")
    logger.info(f"  Strategy: {config.strategy_type.value}")
    logger.info("=" * 70)

    # Initialize services
    inference_service = InferenceService(timeout=config.inference_timeout)
    trading_client = TradingClient()
    metrics_client = MetricsClient()
    portfolio_manager = PortfolioManager(config.initial_capital)

    # Generate evaluation dates
    evaluation_dates = generate_evaluation_dates(
        config.start_date,
        config.end_date,
        config.step_days,
    )

    logger.info(f"  Evaluation dates: {len(evaluation_dates)}")

    # Main backtest loop
    for i, eval_date in enumerate(evaluation_dates):
        logger.info(f"[{run_id}] Evaluating {eval_date} ({i+1}/{len(evaluation_dates)})")

        try:
            # PHASE 1: Get historical data (with temporal bound)
            context_data = await data_provider(
                config.ticker,
                eval_date,
                config.context_size,
            )

            if not context_data or len(context_data) < 10:
                logger.warning(f"Insufficient data for {eval_date}, skipping")
                continue

            current_price = context_data[-1]

            # PHASE 2: Run forecast
            context_start = calculate_start_date(eval_date, len(context_data))
            inference_request = InferenceRequest(
                ticker=config.ticker,
                model=config.model,
                context=ContextData(
                    values=context_data,
                    period=Period.DAY_1,
                    source=DataSource.INFLUXDB,
                    start_date=context_start,
                    end_date=eval_date,
                ),
                horizon=HorizonSpec(
                    length=config.horizon_size,
                    period=Period.DAY_1,
                ),
            )

            inference_response = await inference_service.predict(inference_request)
            forecast_values = inference_response.forecast.values

            # Use mean of forecast as expected price
            forecast_price = sum(forecast_values) / len(forecast_values)

            logger.debug(
                f"  Forecast: current=${current_price:.2f}, "
                f"predicted=${forecast_price:.2f} ({((forecast_price/current_price)-1)*100:+.2f}%)"
            )

            # PHASE 3: Execute trading decision
            trade_result = await trading_client.execute_signal(
                forecast_price=forecast_price,
                current_price=current_price,
                portfolio=portfolio_manager.portfolio,
                strategy_type=config.strategy_type,
                strategy_params=config.strategy_params,
                timestamp=eval_date,
            )

            # PHASE 4: Update portfolio state
            portfolio_manager.apply_trade(trade_result, current_price)

            logger.debug(
                f"  Trade: {trade_result.action.value} "
                f"| Position: {trade_result.position_after:.1f} "
                f"| Cash: ${trade_result.available_cash:,.2f}"
            )

            # Checkpoint if needed
            if portfolio_manager.should_checkpoint():
                checkpoint = portfolio_manager.get_checkpoint()
                logger.info(f"Checkpoint at {eval_date}: equity=${checkpoint['last_equity']:,.2f}")
                if checkpoint_callback:
                    checkpoint_callback(checkpoint)

        except Exception as e:
            logger.error(f"Error on {eval_date}: {e}")
            # Continue with next date - don't fail entire backtest
            continue

    # PHASE 5: Compute metrics
    logger.info("Computing final metrics...")
    returns = prices_to_returns(portfolio_manager.equity_curve)
    metrics = await metrics_client.compute_metrics(
        returns=returns,
        risk_free_rate=config.risk_free_rate,
        periods_per_year=252,
    )

    duration = time.time() - start_time

    result = BacktestResult(
        config=config,
        trades=portfolio_manager.trades,
        equity_curve=portfolio_manager.equity_curve,
        metrics=metrics,
        evaluation_dates=evaluation_dates,
        run_id=run_id,
        duration_seconds=duration,
    )

    # Log summary
    trade_summary = portfolio_manager.get_trade_summary()

    logger.info("=" * 70)
    logger.info(f"BACKTEST COMPLETE run_id={run_id}")
    logger.info("=" * 70)
    logger.info(f"  Duration: {duration:.1f}s")
    logger.info(f"  Total trades: {len(result.trades)}")
    logger.info(f"    Buys: {trade_summary.get('buys', 0)}")
    logger.info(f"    Sells: {trade_summary.get('sells', 0)}")
    logger.info(f"    Holds: {trade_summary.get('holds', 0)}")
    logger.info(f"  Initial capital: ${config.initial_capital:,.2f}")
    logger.info(f"  Final value: ${result.final_value:,.2f}")
    logger.info(f"  Total return: {result.total_return:.2%}")
    logger.info(f"  Sharpe ratio: {metrics.sharpe_ratio:.2f}")
    logger.info(f"  Max drawdown: {metrics.max_drawdown:.2%}")
    logger.info(f"  CAGR: {metrics.cagr:.2%}")
    logger.info(f"  Win rate: {metrics.win_rate:.2%}")
    logger.info("=" * 70)

    return result


def generate_evaluation_dates(
    start_date: str,
    end_date: str,
    step_days: int = 1,
) -> List[str]:
    """
    Generate list of evaluation dates.

    Args:
        start_date: Start date (YYYY-MM-DD or YYYYMMDD)
        end_date: End date (YYYY-MM-DD or YYYYMMDD)
        step_days: Days between evaluations

    Returns:
        List of date strings in YYYY-MM-DD format

    Raises:
        DateParseError: If start_date or end_date cannot be parsed
    """
    start = parse_date(start_date, "start_date")
    end = parse_date(end_date, "end_date")

    if start > end:
        raise ValueError(f"start_date ({start_date}) must be before end_date ({end_date})")

    dates = []
    current = start
    while current <= end:
        # Skip weekends (Saturday=5, Sunday=6)
        if current.weekday() < 5:
            dates.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=step_days)

    return dates


def calculate_start_date(end_date: str, days: int) -> str:
    """
    Calculate start date given end date and number of days.

    Args:
        end_date: End date (YYYY-MM-DD or YYYYMMDD)
        days: Number of days to go back

    Returns:
        Start date in YYYY-MM-DD format

    Raises:
        DateParseError: If end_date cannot be parsed
    """
    end = parse_date(end_date, "end_date")
    start = end - timedelta(days=days)
    return start.strftime("%Y-%m-%d")


async def create_influx_data_provider(
    data_service_url: str = "http://sapheneia-data:8000",
) -> DataProvider:
    """
    Create a data provider that fetches from the Go data service.

    Args:
        data_service_url: URL of the data service

    Returns:
        Async function that fetches data
    """
    async def provider(ticker: str, end_date: str, days: int) -> List[float]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{data_service_url}/v1/data/query",
                json={
                    "ticker": ticker,
                    "days": days,
                    "end_date": end_date,  # Critical: temporal bound
                },
            )
            response.raise_for_status()
            data = response.json()

            # Extract close prices
            prices = [point["close"] for point in data.get("data", [])]
            return prices

    return provider


# Convenience function for simple backtest runs
async def quick_backtest(
    ticker: str,
    model: str,
    start_date: str,
    end_date: str,
    data_provider: DataProvider,
    initial_capital: float = 100000.0,
) -> BacktestResult:
    """
    Run a quick backtest with default settings.

    Args:
        ticker: Stock ticker
        model: Model to use
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        data_provider: Data provider function
        initial_capital: Initial capital

    Returns:
        BacktestResult
    """
    config = BacktestConfig(
        ticker=ticker,
        model=model,
        start_date=start_date,
        end_date=end_date,
        initial_capital=initial_capital,
    )

    return await run_backtest(config, data_provider)


# Need to import httpx for the data provider
import httpx
