# GAP-03: Add Python Orchestration Entry Point

**Priority:** MEDIUM
**Severity:** MEDIUM
**Category:** Architecture
**Effort:** 1-2 days

---

## Architecture Review

### Reliability
- **Current Risk:** Single entry point (Go CLI) creates dependency
- **Mitigation:** Python CLI provides alternative path for researchers
- **Error Handling:** Wrap all operations in try/catch with meaningful errors
- **Graceful Shutdown:** Handle SIGINT/SIGTERM for clean exit

### Continuity
- **Config Validation:** Validate YAML config before starting backtest
- **Progress Tracking:** Show progress bar or iteration count
- **Internal Checkpointing:** Portfolio state checkpointed every N iterations for resilience (not user-exposed)
- **Output Persistence:** Write results to files progressively

### Integrity
- **Config Schema:** Validate config against Pydantic model
- **Audit Log:** Write detailed log file alongside results
- **Determinism:** Same config + data = same results (seed random if needed)
- **Versioning:** Include CLI version in output metadata

### Optimization
- **Lazy Loading:** Only import heavy modules (torch, transformers) when needed
- **Async by Default:** Use asyncio for all I/O operations
- **Progress Caching:** Cache intermediate results to avoid recomputation
- **Memory Efficient:** Stream large datasets instead of loading all in memory

### Separation (Scalability)
- **CLI Layer:** Thin wrapper around core backtest logic
- **Config Layer:** Separate config loading/validation
- **Output Layer:** Pluggable output formats (JSON, CSV, InfluxDB)
- **Plugin Architecture:** Support custom strategies via entry points

---

## Summary

Currently only the Go CLI (`aleutian`) handles orchestration. There's no Python entry point for researchers who want to stay in Python. The `orchestration/` module is a library (adapters, schemas), not an orchestrator.

## Current State

- Go CLI is the only way to run full orchestration
- `orchestration/` module contains adapters and schemas but no CLI
- Python-focused researchers must use Go CLI
- Creates language barrier for experimentation
- Strategy YAML files exist but require Go CLI to execute

## Expected Behavior

```bash
# Python-native way to run backtests
python -m sapheneia evaluate --config strategy.yaml

# Or as installed command
sapheneia evaluate --config strategy.yaml

# Quick single forecast
sapheneia forecast --ticker SPY --model chronos-t5-tiny --horizon 10

# List available models
sapheneia models list

# Show config schema
sapheneia config schema
```

## Acceptance Criteria

- [ ] Create `sapheneia/cli/` module with Click-based CLI
- [ ] Implement `evaluate` command for running backtests
- [ ] Implement `forecast` command for single predictions
- [ ] Implement `models` command to list available models
- [ ] Implement `config` command for config management
- [ ] Add to `pyproject.toml` as console script
- [ ] Support YAML config files compatible with existing strategies
- [ ] Progress bar for long-running backtests
- [ ] Documentation for CLI usage

## Implementation

### File: `sapheneia/cli/__init__.py`

```python
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
@click.version_option(version="1.0.0", prog_name="sapheneia")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.option("--quiet", "-q", is_flag=True, help="Suppress non-error output")
def cli(verbose: bool, quiet: bool):
    """
    Sapheneia - Time Series Forecasting Platform

    Run forecasts and backtests using foundation models.

    Examples:

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
def evaluate(
    config: Path,
    output: Optional[Path],
    run_id: Optional[str],
    dry_run: bool,
):
    """
    Run a backtest evaluation from a strategy config file.

    The config file should be a YAML file with the following structure:

    \b
    metadata:
      id: "spy-chronos-t5-tiny"
      version: "1.0.0"

    evaluation:
      ticker: "SPY"
      start_date: "20230101"
      end_date: "20240101"

    forecast:
      model: "amazon/chronos-t5-tiny"
      context_size: 252
      horizon_size: 20

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
    ))


# =============================================================================
# FORECAST COMMAND
# =============================================================================

@cli.command()
@click.option("--ticker", "-t", required=True, help="Ticker symbol (e.g., SPY)")
@click.option("--model", "-m", required=True, help="Model name (e.g., chronos-t5-tiny)")
@click.option("--horizon", "-h", default=10, type=int, help="Forecast horizon (default: 10)")
@click.option("--context", "-c", default=90, type=int, help="Context window size (default: 90)")
@click.option("--as-of-date", type=str, default=None, help="As-of date for backtest mode (YYYY-MM-DD)")
@click.option("--output", "-o", type=click.Choice(["json", "table", "csv"]), default="table")
def forecast(
    ticker: str,
    model: str,
    horizon: int,
    context: int,
    as_of_date: Optional[str],
    output: str,
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
        output_format=output,
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
@click.option("--format", "-o", type=click.Choice(["table", "json"]), default="table")
def models_list(family: Optional[str], format: str):
    """
    List available forecasting models.

    Example:

        sapheneia models list
        sapheneia models list --family chronos
    """
    from .commands.models import list_models

    list_models(family_filter=family, output_format=format)


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
@click.option("--format", "-o", type=click.Choice(["yaml", "json"]), default="yaml")
def config_schema(format: str):
    """
    Show the config file schema.

    Example:

        sapheneia config schema
    """
    from .commands.config import show_schema

    show_schema(output_format=format)


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
```

### File: `sapheneia/cli/commands/evaluate.py`

```python
"""
Evaluate command implementation.
"""

import click
import logging
from pathlib import Path
from typing import Optional
import yaml

logger = logging.getLogger(__name__)


async def run_evaluate(
    config_path: Path,
    output_dir: Optional[Path],
    run_id: Optional[str],
    dry_run: bool,
):
    """Run backtest evaluation.

    Note: Checkpointing is internal for resilience. Resume from checkpoint
    is not exposed to CLI - rerun with same config if needed.
    """

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

    if dry_run:
        click.echo("Config is valid. Dry run complete.")
        return

    # Import heavy modules only when needed
    from orchestration.backtest import run_backtest, BacktestConfig

    # Create backtest config
    backtest_config = BacktestConfig(
        ticker=config.ticker,
        model=config.model,
        start_date=config.start_date,
        end_date=config.end_date,
        initial_capital=config.initial_capital,
        context_size=config.context_size,
        horizon_size=config.horizon_size,
        strategy_params=config.strategy_params,
    )

    # Data provider function
    async def data_provider(ticker: str, end_date: str, days: int):
        # TODO: Implement data fetching from InfluxDB or file
        # For now, use mock data
        import random
        base_price = 450.0
        return [base_price + random.uniform(-5, 5) for _ in range(days)]

    # Run backtest with progress
    with click.progressbar(length=100, label="Running backtest") as bar:
        result = await run_backtest(
            config=backtest_config,
            data_provider=data_provider,
            run_id=run_id,
        )
        bar.update(100)

    # Output results
    click.echo("\n" + "=" * 60)
    click.echo("BACKTEST RESULTS")
    click.echo("=" * 60)
    click.echo(f"  Run ID: {result.run_id}")
    click.echo(f"  Total trades: {len(result.trades)}")
    click.echo(f"  Total return: {result.total_return:.2%}")
    click.echo(f"  Sharpe ratio: {result.metrics.sharpe_ratio:.2f}")
    click.echo(f"  Max drawdown: {result.metrics.max_drawdown:.2%}")
    click.echo(f"  Win rate: {result.metrics.win_rate:.2%}")

    # Save results
    output_dir = output_dir or Path(f"./results/{result.run_id}")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save summary
    summary_path = output_dir / "summary.json"
    import json
    with open(summary_path, "w") as f:
        json.dump({
            "run_id": result.run_id,
            "config": config_data,
            "total_return": result.total_return,
            "metrics": {
                "sharpe_ratio": result.metrics.sharpe_ratio,
                "max_drawdown": result.metrics.max_drawdown,
                "cagr": result.metrics.cagr,
                "calmar_ratio": result.metrics.calmar_ratio,
                "win_rate": result.metrics.win_rate,
            },
        }, f, indent=2)

    click.echo(f"\nResults saved to {output_dir}")
```

### Update `pyproject.toml`

```toml
[project.scripts]
sapheneia = "sapheneia.cli:main"

[project.optional-dependencies]
cli = [
    "click>=8.0",
    "pyyaml>=6.0",
    "rich>=13.0",  # For pretty printing
]
```

## Directory Structure

```
sapheneia/
├── cli/
│   ├── __init__.py          # Main CLI with click groups
│   ├── config.py             # Config models and validation
│   └── commands/
│       ├── __init__.py
│       ├── evaluate.py       # evaluate command
│       ├── forecast.py       # forecast command
│       ├── models.py         # models list command
│       └── config.py         # config validate/schema/init
```

## Dependencies

- GAP-02 (Trading feedback loop) for `evaluate` command
- GAP-01 (Metrics integration) for complete results

## Test Cases

1. **Config validation**: Valid and invalid configs
2. **Dry run**: Validates without executing
3. **Forecast**: Single forecast output
4. **Models list**: Lists available models

## Note on Checkpointing

Checkpointing is implemented internally in `PortfolioManager` for resilience during
long backtests, but is not exposed to CLI. If a backtest is interrupted, rerun with
the same config. The checkpoint infrastructure exists to prevent data loss during
a single run, not to support user-initiated resume.

## Related Files

- `pyproject.toml`
- New: `sapheneia/cli/__init__.py`
- New: `sapheneia/cli/commands/*.py`
- Existing: `simulations/strategies/*.yaml`
