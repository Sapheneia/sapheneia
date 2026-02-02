"""
Evaluate command implementation.

Runs backtests from strategy config files.
"""

import click
import logging
import json
from pathlib import Path
from typing import Optional
import yaml

logger = logging.getLogger(__name__)


async def run_evaluate(
    config_path: Path,
    output_dir: Optional[Path],
    run_id: Optional[str],
    dry_run: bool,
    timeout: Optional[float] = None,
):
    """Run backtest evaluation."""

    # Load and validate config
    click.echo(f"Loading config from {config_path}")

    with open(config_path) as f:
        config_data = yaml.safe_load(f)

    # Validate config
    from ..config import StrategyConfig
    try:
        config = StrategyConfig.from_dict(config_data)
    except Exception as e:
        click.echo(f"Invalid config: {e}", err=True)
        raise click.Abort()

    click.echo(f"  Ticker: {config.ticker}")
    click.echo(f"  Model: {config.model}")
    click.echo(f"  Period: {config.start_date} to {config.end_date}")
    click.echo(f"  Capital: ${config.initial_capital:,.2f}")

    if dry_run:
        click.echo("\nConfig is valid. Dry run complete.")
        return

    # Import heavy modules only when needed
    from orchestration.backtest import run_backtest, BacktestConfig
    from orchestration.clients.trading_client import StrategyType
    from orchestration.clients.data_client import DataClient

    # Determine strategy type
    strategy_type = StrategyType.THRESHOLD
    strategy_name = config.strategy_type.lower()
    if strategy_name == "return":
        strategy_type = StrategyType.RETURN
    elif strategy_name == "quantile":
        strategy_type = StrategyType.QUANTILE

    # Create backtest config
    backtest_config = BacktestConfig(
        ticker=config.ticker,
        model=config.model,
        start_date=config.start_date,
        end_date=config.end_date,
        initial_capital=config.initial_capital,
        context_size=config.context_size,
        horizon_size=config.horizon_size,
        strategy_type=strategy_type,
        strategy_params=config.strategy_params,
        inference_timeout=timeout,
    )

    # Data provider using DataClient
    data_client = DataClient()

    async def data_provider(ticker: str, end_date: str, days: int):
        """Fetch data from Go data service."""
        prices = await data_client.query_data(
            ticker=ticker,
            days=days,
            end_date=end_date,
        )
        return prices

    # Run backtest
    click.echo("\nRunning backtest...")
    result = await run_backtest(
        config=backtest_config,
        data_provider=data_provider,
        run_id=run_id,
    )

    # Output results
    click.echo("\n" + "=" * 60)
    click.echo("BACKTEST RESULTS")
    click.echo("=" * 60)
    click.echo(f"  Run ID: {result.run_id}")
    click.echo(f"  Duration: {result.duration_seconds:.1f}s")
    click.echo(f"  Total trades: {len(result.trades)}")
    click.echo(f"  Initial capital: ${config.initial_capital:,.2f}")
    click.echo(f"  Final value: ${result.final_value:,.2f}")
    click.echo(f"  Total return: {result.total_return:.2%}")
    click.echo(f"  Sharpe ratio: {result.metrics.sharpe_ratio:.2f}")
    click.echo(f"  Max drawdown: {result.metrics.max_drawdown:.2%}")
    click.echo(f"  CAGR: {result.metrics.cagr:.2%}")
    click.echo(f"  Win rate: {result.metrics.win_rate:.2%}")

    # Save results
    output_dir = output_dir or Path(f"./results/{result.run_id}")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save summary
    summary_path = output_dir / "summary.json"
    with open(summary_path, "w") as f:
        json.dump(result.to_dict(), f, indent=2)

    # Save equity curve
    equity_path = output_dir / "equity_curve.json"
    with open(equity_path, "w") as f:
        json.dump({"equity_curve": result.equity_curve}, f, indent=2)

    click.echo(f"\nResults saved to {output_dir}")
