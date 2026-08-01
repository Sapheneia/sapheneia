"""Run-lifecycle service: create runs, dispatch background tasks, cancel."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import uuid
from datetime import datetime
from typing import Any

from shared.model_family import ModelFamily

from ..repositories.runs_repo import RunsRepository
from ..schemas.strategy import StrategyConfig
from .inner_loop import InnerLoop

logger = logging.getLogger("sapheneia.orchestrator.runs")


def _family_from_model_id(model_id: str) -> str:
    return ModelFamily.from_model_id(model_id).value


def make_run_id(experiment_id: str, ticker: str, model_id: str, suffix: str | None = None) -> str:
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    safe_model = model_id.replace("/", "_")
    suf = suffix or uuid.uuid4().hex[:6]
    return f"{experiment_id}__{ticker}__{safe_model}__{ts}_{suf}"


class RunsService:
    def __init__(
        self,
        *,
        runs_repo: RunsRepository,
        inner_loop: InnerLoop,
        max_concurrent_runs: int,
        heartbeat_refresh_interval: float = 60.0,
    ):
        self.runs_repo = runs_repo
        self.inner = inner_loop
        self._semaphore = asyncio.Semaphore(max_concurrent_runs)
        self._active_tasks: dict[str, asyncio.Task] = {}
        self._heartbeat_refresh_interval = heartbeat_refresh_interval

    async def submit(self, strategy_data: dict[str, Any]) -> tuple[str, str]:
        cfg = StrategyConfig.model_validate(strategy_data)
        run_id = make_run_id(cfg.metadata.experiment_id, cfg.evaluation.ticker, cfg.forecast.model)
        await self.runs_repo.ensure_ticker(cfg.evaluation.ticker)
        await self.runs_repo.ensure_model(
            cfg.forecast.model, _family_from_model_id(cfg.forecast.model)
        )
        await self.runs_repo.create(
            run_id=run_id,
            experiment_id=cfg.metadata.experiment_id,
            ticker=cfg.evaluation.ticker,
            model_id=cfg.forecast.model,
            strategy_type=cfg.trading.strategy_type,
            config=strategy_data,
            cache_enabled=cfg.cache.enabled,
            cache_scope=cfg.cache.scope,
        )
        task = asyncio.create_task(
            self._run_with_semaphore(run_id, cfg, cfg.metadata.experiment_id)
        )
        self._active_tasks[run_id] = task
        task.add_done_callback(lambda _t, rid=run_id: self._active_tasks.pop(rid, None))
        return run_id, "pending"

    async def submit_batch(self, strategies: list[dict[str, Any]]) -> list[tuple[str, str]]:
        out = []
        for s in strategies:
            try:
                out.append(await self.submit(s))
            except Exception as exc:  # noqa: BLE001
                logger.exception("Failed to submit strategy: %s", exc)
                out.append(("__error__", f"validation: {exc}"))
        return out

    async def cancel(self, run_id: str) -> bool:
        task = self._active_tasks.get(run_id)
        if task is None:
            return False
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await task
        await self.runs_repo.update_status(
            run_id, "cancelled", error="cancelled by request", completed=True
        )
        return True

    async def _run_with_semaphore(
        self, run_id: str, cfg: StrategyConfig, experiment_id: str
    ) -> None:
        # While waiting for a concurrency slot the run is still `pending`; refresh
        # its heartbeat so the reconciler does not mistake a queued run for an
        # orphaned one (which would be killed after HEARTBEAT_STALE_AFTER).
        while True:
            try:
                await asyncio.wait_for(
                    self._semaphore.acquire(), timeout=self._heartbeat_refresh_interval
                )
                break
            except TimeoutError:
                await self.runs_repo.heartbeat(run_id)
        try:
            await self.inner.run(run_id, cfg, experiment_id)
        finally:
            self._semaphore.release()
