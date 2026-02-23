"""
Config command implementation.

Handles config file validation, schema display, and initialization.
"""

import click
import json
import yaml
from pathlib import Path


def validate_config(config_file: Path):
    """Validate a strategy config file."""

    click.echo(f"Validating config: {config_file}")

    try:
        with open(config_file) as f:
            config_data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        click.echo(f"Invalid YAML: {e}", err=True)
        raise click.Abort()

    # Import config model
    from ..config import StrategyConfig

    try:
        config = StrategyConfig.from_dict(config_data)
        click.echo("\nConfig is valid!")
        click.echo("\nParsed values:")
        click.echo(f"  Ticker: {config.ticker}")
        click.echo(f"  Model: {config.model}")
        click.echo(f"  Start date: {config.start_date}")
        click.echo(f"  End date: {config.end_date}")
        click.echo(f"  Initial capital: ${config.initial_capital:,.2f}")
        click.echo(f"  Context size: {config.context_size}")
        click.echo(f"  Horizon size: {config.horizon_size}")
        click.echo(f"  Strategy: {config.strategy_type}")

    except Exception as e:
        click.echo(f"\nValidation failed: {e}", err=True)
        raise click.Abort()


def show_schema(output_format: str):
    """Show the config file schema."""

    schema = {
        "metadata": {
            "id": "string (required) - Unique strategy identifier",
            "version": "string (optional) - Config version",
            "description": "string (optional) - Strategy description",
        },
        "evaluation": {
            "ticker": "string (required) - Ticker symbol (e.g., SPY)",
            "start_date": "string (required) - Start date YYYY-MM-DD or YYYYMMDD",
            "end_date": "string (required) - End date YYYY-MM-DD or YYYYMMDD",
        },
        "forecast": {
            "model": "string (required) - Model name (e.g., amazon/chronos-t5-tiny)",
            "context_size": "integer (optional, default: 90) - Days of context",
            "horizon_size": "integer (optional, default: 10) - Days to forecast",
        },
        "trading": {
            "initial_capital": "float (optional, default: 100000) - Starting capital",
            "strategy_type": "string (optional, default: threshold) - threshold|return|quantile",
            "params": {
                "threshold_type": "string - absolute|percent",
                "threshold_value": "float - Threshold value",
                "execution_size": "float - Trade size",
            },
        },
    }

    if output_format == "json":
        click.echo(json.dumps(schema, indent=2))
    else:
        click.echo(yaml.dump(schema, default_flow_style=False, sort_keys=False))


def init_config(output_file: Path, ticker: str, model: str):
    """Create a new strategy config file."""

    from datetime import datetime, timedelta

    # Calculate default dates (last year)
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")

    config = {
        "metadata": {
            "id": f"{ticker.lower()}-{model.split('/')[-1]}",
            "version": "1.0.0",
            "description": f"Strategy for {ticker} using {model}",
        },
        "evaluation": {
            "ticker": ticker,
            "start_date": start_date,
            "end_date": end_date,
        },
        "forecast": {
            "model": model,
            "context_size": 90,
            "horizon_size": 10,
        },
        "trading": {
            "initial_capital": 100000.0,
            "strategy_type": "threshold",
            "params": {
                "threshold_type": "absolute",
                "threshold_value": 2.0,
                "execution_size": 10.0,
            },
        },
    }

    # Write config
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    click.echo(f"Created config file: {output_file}")
    click.echo("\nGenerated config:")
    click.echo(yaml.dump(config, default_flow_style=False, sort_keys=False))
