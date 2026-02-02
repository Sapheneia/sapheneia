"""
Forecast command implementation.

Runs single forecasts for a ticker.
"""

import click
import logging
import json
from typing import Optional

logger = logging.getLogger(__name__)


async def run_forecast(
    ticker: str,
    model: str,
    horizon: int,
    context_size: int,
    as_of_date: Optional[str],
    output_format: str,
    timeout: Optional[float] = None,
):
    """Run a single forecast."""

    click.echo(f"Running forecast for {ticker}")
    click.echo(f"  Model: {model}")
    click.echo(f"  Horizon: {horizon} days")
    click.echo(f"  Context: {context_size} days")
    if as_of_date:
        click.echo(f"  As-of date: {as_of_date}")

    # Import modules
    from orchestration.service import InferenceService
    from orchestration.schema import (
        InferenceRequest,
        ContextData,
        HorizonSpec,
        Period,
        DataSource,
    )
    from orchestration.clients.data_client import DataClient
    from datetime import datetime, timedelta

    # Fetch data
    click.echo("\nFetching historical data...")
    data_client = DataClient()

    prices = await data_client.query_data(
        ticker=ticker,
        days=context_size,
        end_date=as_of_date,
    )

    if not prices:
        click.echo("Error: Could not fetch data. Is the data service running?", err=True)
        raise click.Abort()

    click.echo(f"  Retrieved {len(prices)} data points")

    # Calculate dates
    if as_of_date:
        end_date = as_of_date
    else:
        end_date = datetime.now().strftime("%Y-%m-%d")

    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    start_dt = end_dt - timedelta(days=len(prices))
    start_date = start_dt.strftime("%Y-%m-%d")

    # Create inference request
    inference_request = InferenceRequest(
        ticker=ticker,
        model=model,
        context=ContextData(
            values=prices,
            period=Period.DAY_1,
            source=DataSource.INFLUXDB,
            start_date=start_date,
            end_date=end_date,
        ),
        horizon=HorizonSpec(
            length=horizon,
            period=Period.DAY_1,
        ),
    )

    # Run inference
    click.echo("\nRunning inference...")
    service = InferenceService(timeout=timeout)

    try:
        response = await service.predict(inference_request)
    except Exception as e:
        click.echo(f"Error: Inference failed: {e}", err=True)
        raise click.Abort()

    # Format output
    forecast_values = response.forecast.values

    if output_format == "json":
        output = {
            "ticker": ticker,
            "model": model,
            "request_id": response.request_id,
            "forecast_start": response.forecast.start_date,
            "forecast_end": response.forecast.end_date,
            "values": forecast_values,
            "inference_time_ms": response.metadata.inference_time_ms,
        }
        click.echo(json.dumps(output, indent=2))

    elif output_format == "csv":
        # Calculate forecast dates
        forecast_start = datetime.strptime(response.forecast.start_date, "%Y-%m-%d")
        click.echo("date,forecast")
        for i, val in enumerate(forecast_values):
            date = (forecast_start + timedelta(days=i)).strftime("%Y-%m-%d")
            click.echo(f"{date},{val:.2f}")

    else:  # table format
        click.echo("\n" + "=" * 50)
        click.echo(f"FORECAST RESULTS - {ticker}")
        click.echo("=" * 50)
        click.echo(f"  Model: {model}")
        click.echo(f"  Request ID: {response.request_id}")
        click.echo(f"  Inference time: {response.metadata.inference_time_ms}ms")
        click.echo(f"\nForecast period: {response.forecast.start_date} to {response.forecast.end_date}")
        click.echo("\n  Day  |  Forecast")
        click.echo("  " + "-" * 20)

        current_price = prices[-1]
        for i, val in enumerate(forecast_values, 1):
            change = ((val / current_price) - 1) * 100
            arrow = "+" if change > 0 else ""
            click.echo(f"  {i:3d}  |  ${val:,.2f} ({arrow}{change:.1f}%)")

        avg_forecast = sum(forecast_values) / len(forecast_values)
        avg_change = ((avg_forecast / current_price) - 1) * 100
        click.echo("\n  Average forecast: ${:.2f} ({}{:.1f}%)".format(
            avg_forecast, "+" if avg_change > 0 else "", avg_change
        ))
