"""Sapheneia orchestrator service.

Sole writer of run-state to TimescaleDB. Runs the per-iteration
data → forecast → trading → metrics inner loop as an asyncio background task,
keyed by ``run_id``. Forecast / trading / metrics services remain stateless.
"""

__all__: list[str] = []
