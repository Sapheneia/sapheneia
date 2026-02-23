"""
Sapheneia CLI

Command-line interface for running forecasts and backtests.
Provides Python-native alternative to the Go CLI.
"""

import click
import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@click.group()
@click.version_option(package_name="sapheneia", prog_name="sapheneia")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.option("--quiet", "-q", is_flag=True, help="Suppress non-error output")
def cli(verbose: bool, quiet: bool):
    """
    Sapheneia - Time Series Forecasting Platform

    Run forecasts and backtests using foundation models.

    Examples:

    \b
        # Run a backtest
        sapheneia evaluate --config strategy.yaml

        # Quick forecast
        sapheneia forecast --ticker SPY --model chronos-t5-tiny

        # List models
        sapheneia models list
    """
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    elif quiet:
        logging.getLogger().setLevel(logging.ERROR)


# =============================================================================
# EVALUATE COMMAND
# =============================================================================

@cli.command()
@click.option(
    "--config", "-c",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Path to strategy YAML config file"
)
@click.option(
    "--output", "-o",
    type=click.Path(path_type=Path),
    default=None,
    help="Output directory for results (default: ./results/{run_id}/)"
)
@click.option(
    "--run-id",
    type=str,
    default=None,
    help="Custom run identifier (default: auto-generated)"
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Validate config without running backtest"
)
@click.option(
    "--timeout",
    type=float,
    default=None,
    help="Inference timeout in seconds (default: 300, env: INFERENCE_TIMEOUT)"
)
def evaluate(
    config: Path,
    output: Optional[Path],
    run_id: Optional[str],
    dry_run: bool,
    timeout: Optional[float],
):
    """
    Run a backtest evaluation from a strategy config file.

    \b
    The config file should be a YAML file with the following structure:

    \b
    metadata:
      id: "spy-chronos-t5-tiny"
      version: "1.0.0"

    \b
    evaluation:
      ticker: "SPY"
      start_date: "2023-01-01"
      end_date: "2024-01-01"

    \b
    forecast:
      model: "amazon/chronos-t5-tiny"
      context_size: 252
      horizon_size: 20

    \b
    trading:
      initial_capital: 100000.0
      strategy_type: "threshold"
      params:
        threshold_type: "absolute"
        threshold_value: 2.0

    Example:

        sapheneia evaluate --config strategies/spy_chronos.yaml
    """
    from .commands.evaluate import run_evaluate

    asyncio.run(run_evaluate(
        config_path=config,
        output_dir=output,
        run_id=run_id,
        dry_run=dry_run,
        timeout=timeout,
    ))


# =============================================================================
# FORECAST COMMAND
# =============================================================================

@cli.command()
@click.option("--ticker", "-t", required=True, help="Ticker symbol (e.g., SPY)")
@click.option("--model", "-m", required=True, help="Model name (e.g., chronos-t5-tiny)")
@click.option("--horizon", "-H", default=10, type=int, help="Forecast horizon (default: 10)")
@click.option("--context", default=90, type=int, help="Context window size (default: 90)")
@click.option("--as-of-date", type=str, default=None, help="As-of date for backtest mode (YYYY-MM-DD)")
@click.option("--format", "-f", "output_format", type=click.Choice(["json", "table", "csv"]), default="table")
@click.option("--timeout", type=float, default=None, help="Inference timeout in seconds (default: 300)")
def forecast(
    ticker: str,
    model: str,
    horizon: int,
    context: int,
    as_of_date: Optional[str],
    output_format: str,
    timeout: Optional[float],
):
    """
    Run a single forecast for a ticker.

    Example:

        sapheneia forecast --ticker SPY --model chronos-t5-tiny --horizon 10
    """
    from .commands.forecast import run_forecast

    asyncio.run(run_forecast(
        ticker=ticker,
        model=model,
        horizon=horizon,
        context_size=context,
        as_of_date=as_of_date,
        output_format=output_format,
        timeout=timeout,
    ))


# =============================================================================
# MODELS COMMAND
# =============================================================================

@cli.group()
def models():
    """Manage and list available models."""
    pass


@models.command("list")
@click.option("--family", "-f", type=str, default=None, help="Filter by model family")
@click.option("--format", "-o", "output_format", type=click.Choice(["table", "json"]), default="table")
def models_list(family: Optional[str], output_format: str):
    """
    List available forecasting models.

    Example:

    \b
        sapheneia models list
        sapheneia models list --family chronos
    """
    from .commands.models import list_models

    list_models(family_filter=family, output_format=output_format)


# =============================================================================
# CONFIG COMMAND
# =============================================================================

@cli.group()
def config():
    """Manage configuration files."""
    pass


@config.command("validate")
@click.argument("config_file", type=click.Path(exists=True, path_type=Path))
def config_validate(config_file: Path):
    """
    Validate a strategy config file.

    Example:

        sapheneia config validate strategy.yaml
    """
    from .commands.config import validate_config

    validate_config(config_file)


@config.command("schema")
@click.option("--format", "-o", "output_format", type=click.Choice(["yaml", "json"]), default="yaml")
def config_schema(output_format: str):
    """
    Show the config file schema.

    Example:

        sapheneia config schema
    """
    from .commands.config import show_schema

    show_schema(output_format=output_format)


@config.command("init")
@click.argument("output_file", type=click.Path(path_type=Path))
@click.option("--ticker", "-t", default="SPY", help="Ticker symbol")
@click.option("--model", "-m", default="amazon/chronos-t5-tiny", help="Model name")
def config_init(output_file: Path, ticker: str, model: str):
    """
    Create a new strategy config file.

    Example:

        sapheneia config init my_strategy.yaml --ticker AAPL
    """
    from .commands.config import init_config

    init_config(output_file, ticker=ticker, model=model)


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def main():
    """Main entry point for CLI."""
    try:
        cli()
    except KeyboardInterrupt:
        click.echo("\nInterrupted by user", err=True)
        sys.exit(130)
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
