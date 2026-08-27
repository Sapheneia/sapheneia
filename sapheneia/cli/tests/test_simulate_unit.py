"""Unit tests for `sapheneia simulate` (mocked orchestrator)."""

from __future__ import annotations

from pathlib import Path

import respx
from click.testing import CliRunner
from httpx import Response

from sapheneia.cli import cli

REPO_ROOT = Path(__file__).resolve().parents[3]
EXAMPLE_STRATEGY = REPO_ROOT / "simulations" / "templates" / "spy_chronos_tiny.example.yaml"


@respx.mock
def test_simulate_completes_happy_path(tmp_path: Path) -> None:
    base = "http://localhost:12704"
    respx.post(f"{base}/v1/orchestration/runs").mock(
        return_value=Response(200, json={"run_id": "run-test", "status": "pending"})
    )
    respx.get(f"{base}/v1/orchestration/runs/run-test").mock(
        return_value=Response(
            200,
            json={
                "run_id": "run-test",
                "status": "completed",
                "metrics": {"sharpe": 1.5, "max_drawdown": -0.07},
                "error": None,
                "config": {},
                "experiment_id": "manual",
                "ticker": "SPY",
                "model_id": "amazon/chronos-t5-tiny",
                "strategy_type": "threshold",
                "started_at": "2026-04-23T12:00:00",
                "completed_at": "2026-04-23T12:05:00",
                "cache_enabled": False,
            },
        )
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["simulate", "--strategy", str(EXAMPLE_STRATEGY), "--poll-interval", "0.01"],
    )
    assert result.exit_code == 0, result.output
    assert "Submitted: run-test" in result.output
    assert "sharpe" in result.output


@respx.mock
def test_simulate_exits_nonzero_on_failed_run() -> None:
    base = "http://localhost:12704"
    respx.post(f"{base}/v1/orchestration/runs").mock(
        return_value=Response(200, json={"run_id": "run-bad", "status": "pending"})
    )
    respx.get(f"{base}/v1/orchestration/runs/run-bad").mock(
        return_value=Response(
            200,
            json={
                "run_id": "run-bad",
                "status": "failed",
                "metrics": None,
                "error": "data service unreachable",
                "config": {},
                "experiment_id": "manual",
                "ticker": "SPY",
                "model_id": "amazon/chronos-t5-tiny",
                "strategy_type": "threshold",
                "started_at": "2026-04-23T12:00:00",
                "completed_at": "2026-04-23T12:01:00",
                "cache_enabled": False,
            },
        )
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["simulate", "--strategy", str(EXAMPLE_STRATEGY), "--poll-interval", "0.01"],
    )
    assert result.exit_code == 1
    assert "data service unreachable" in result.output


@respx.mock
def test_simulate_exits_2_on_timeout() -> None:
    """The poll loop's kill-switch must actually fire.

    This is the only thing standing between an operator and an infinite poll
    against a stuck run, and it had no test.
    """
    base = "http://localhost:12704"
    respx.post(f"{base}/v1/orchestration/runs").mock(
        return_value=Response(200, json={"run_id": "run-stuck", "status": "pending"})
    )
    respx.get(f"{base}/v1/orchestration/runs/run-stuck").mock(
        return_value=Response(
            200,
            json={
                "run_id": "run-stuck",
                "status": "running",  # never reaches a terminal state
                "metrics": None,
                "error": None,
                "config": {},
                "experiment_id": "manual",
                "ticker": "SPY",
                "model_id": "amazon/chronos-t5-tiny",
                "strategy_type": "threshold",
                "started_at": "2026-04-23T12:00:00",
                "completed_at": None,
                "cache_enabled": False,
            },
        )
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "simulate",
            "--strategy",
            str(EXAMPLE_STRATEGY),
            "--poll-interval",
            "0.01",
            "--timeout",
            "0.05",
        ],
    )
    assert result.exit_code == 2, result.output
    assert "Timeout after" in result.output
