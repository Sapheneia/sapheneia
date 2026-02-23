"""
Models command implementation.

Lists available forecasting models.
"""

import click
import json
from typing import Optional


AVAILABLE_MODELS = [
    {
        "family": "chronos",
        "models": [
            {"name": "amazon/chronos-t5-tiny", "params": "8M", "description": "Fastest, least accurate"},
            {"name": "amazon/chronos-t5-mini", "params": "20M", "description": "Good balance"},
            {"name": "amazon/chronos-t5-small", "params": "46M", "description": "Better accuracy"},
            {"name": "amazon/chronos-t5-base", "params": "200M", "description": "High accuracy"},
            {"name": "amazon/chronos-t5-large", "params": "710M", "description": "Best accuracy"},
            {"name": "amazon/chronos-bolt-tiny", "params": "9M", "description": "Fast bolt variant"},
            {"name": "amazon/chronos-bolt-mini", "params": "21M", "description": "Bolt mini"},
            {"name": "amazon/chronos-bolt-small", "params": "48M", "description": "Bolt small"},
            {"name": "amazon/chronos-bolt-base", "params": "205M", "description": "Bolt base"},
        ],
    },
    {
        "family": "timesfm",
        "models": [
            {"name": "google/timesfm-1.0-200m", "params": "200M", "description": "TimesFM 1.0"},
            {"name": "google/timesfm-2.0-500m-pytorch", "params": "500M", "description": "TimesFM 2.0"},
        ],
    },
    {
        "family": "moirai",
        "models": [
            {"name": "salesforce/moirai-1.1-R-small", "params": "14M", "description": "Moirai small"},
            {"name": "salesforce/moirai-1.1-R-base", "params": "91M", "description": "Moirai base"},
            {"name": "salesforce/moirai-1.1-R-large", "params": "311M", "description": "Moirai large"},
        ],
    },
    {
        "family": "moment",
        "models": [
            {"name": "AutonLab/MOMENT-1-large", "params": "385M", "description": "MOMENT large"},
        ],
    },
    {
        "family": "granite",
        "models": [
            {"name": "ibm/granite-timeseries-ttm-r1", "params": "1M", "description": "Granite TTM"},
            {"name": "ibm/granite-timeseries-ttm-r2", "params": "1M", "description": "Granite TTM R2"},
        ],
    },
    {
        "family": "lagllama",
        "models": [
            {"name": "time-series-foundation-models/Lag-Llama", "params": "~250M", "description": "Lag-Llama"},
        ],
    },
]


def list_models(family_filter: Optional[str], output_format: str):
    """List available models."""

    models = AVAILABLE_MODELS

    # Filter by family if specified
    if family_filter:
        models = [m for m in models if m["family"].lower() == family_filter.lower()]
        if not models:
            click.echo(f"No models found for family: {family_filter}", err=True)
            click.echo(f"Available families: {', '.join(m['family'] for m in AVAILABLE_MODELS)}")
            return

    if output_format == "json":
        click.echo(json.dumps(models, indent=2))
    else:
        # Table format
        click.echo("\nAvailable Forecasting Models")
        click.echo("=" * 70)

        for family_group in models:
            family = family_group["family"]
            click.echo(f"\n{family.upper()}")
            click.echo("-" * 70)
            click.echo(f"{'Model':<45} {'Params':<10} {'Description'}")
            click.echo("-" * 70)

            for model in family_group["models"]:
                click.echo(f"{model['name']:<45} {model['params']:<10} {model['description']}")

        click.echo("\n" + "-" * 70)
        total = sum(len(f["models"]) for f in models)
        click.echo(f"Total: {total} models in {len(models)} families")
