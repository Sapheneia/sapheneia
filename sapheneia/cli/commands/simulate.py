"""`sapheneia simulate` — POST a rendered strategy YAML to the orchestrator.

Polls until the run reaches a terminal state (completed/failed/cancelled),
then prints the metrics.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

import click
import httpx
import yaml


@click.command(name="simulate")
@click.option(
    "--strategy",
    "strategy_path",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Path to a rendered strategy YAML",
)
@click.option(
    "--orchestrator-url",
    default="http://localhost:12704",
    show_default=True,
    envvar="ORCHESTRATOR_URL",
    help="Base URL of the orchestrator service",
)
@click.option(
    "--token",
    default=None,
    envvar="ORCHESTRATOR_API_KEY",
    help="Bearer token for the orchestrator (env: ORCHESTRATOR_API_KEY)",
)
@click.option(
    "--poll-interval",
    type=float,
    default=5.0,
    show_default=True,
    help="Seconds between status polls",
)
@click.option(
    "--timeout",
    type=float,
    default=3600.0,
    show_default=True,
    help="Hard timeout in seconds",
)
def simulate(
    strategy_path: Path,
    orchestrator_url: str,
    token: str | None,
    poll_interval: float,
    timeout: float,
) -> None:
    """Run a single rendered strategy through the orchestrator and print results."""
    payload = yaml.safe_load(strategy_path.read_text())
    headers = {"Authorization": f"Bearer {token}"} if token else {}

    asyncio.run(_run(orchestrator_url, headers, payload, poll_interval, timeout))


async def _run(
    base_url: str,
    headers: dict,
    payload: dict,
    poll_interval: float,
    timeout: float,
) -> None:
    base_url = base_url.rstrip("/")
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(f"{base_url}/v1/orchestration/runs", json=payload, headers=headers)
        r.raise_for_status()
        body = r.json()
        run_id = body["run_id"]
        click.echo(f"Submitted: {run_id}")

        deadline = time.monotonic() + timeout
        terminal = {"completed", "failed", "cancelled"}
        last_status: str | None = None
        while True:
            if time.monotonic() > deadline:
                click.echo(f"Timeout after {timeout:.0f}s — run still in progress.", err=True)
                sys.exit(2)
            r = await client.get(f"{base_url}/v1/orchestration/runs/{run_id}", headers=headers)
            r.raise_for_status()
            data = r.json()
            status = data.get("status", "unknown")
            if status != last_status:
                click.echo(f"  status={status}")
                last_status = status
            if status in terminal:
                _print_result(data)
                if status != "completed":
                    sys.exit(1)
                return
            await asyncio.sleep(poll_interval)


def _print_result(data: dict) -> None:
    metrics = data.get("metrics") or {}
    click.echo("\nResult:")
    click.echo(json.dumps(metrics, indent=2, default=str))
    err = data.get("error")
    if err:
        click.echo(f"\nError: {err}", err=True)
