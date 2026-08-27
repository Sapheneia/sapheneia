"""HTTP client for the forecast service.

Model routing
-------------
Each forecast container loads exactly one model into a process-global pipeline,
pinned by its ``MODEL_VARIANT`` env var. It only consults the request body's
``model_variant`` while its status is ``uninitialized`` — after the first request
it serves that pipeline forever, whatever later requests ask for.

So a single shared endpoint cannot serve a multi-model sweep: it returns the
first-loaded model's forecast for every model in the sweep, recorded under
whichever ``model_id`` was requested. This client therefore resolves
``model_id -> container base URL`` through ``shared.model_registry`` and calls the
container that actually holds the model, and sends ``model_id`` so the service can
assert it and reject a mismatch.
"""

from __future__ import annotations

from shared.contracts import ForecastEnvelope, ForecastRequest
from shared.http_client import BaseHttpClient
from shared.model_registry import ModelInfo, require


class ForecastClient(BaseHttpClient):
    def __init__(
        self,
        base_url: str = "",
        *,
        api_key: str = "",
        timeout: float = 300.0,
    ):
        """
        Args:
            base_url: Optional override. When empty (the default, and the correct
                setting for the compose stack) every request is routed to the
                model's own container via the registry. When set, all requests go
                to that one URL instead — useful only for a single-model
                deployment or a test double.
        """
        super().__init__(base_url, api_key=api_key, timeout=timeout)
        self._override = bool(base_url)

    def resolve(self, model_id: str) -> tuple[ModelInfo, str]:
        """Resolve a model to (registry entry, base URL). Raises if unknown."""
        info = require(model_id)
        return info, self.base_url if self._override else info.base_url

    async def predict(
        self,
        *,
        model_id: str,
        context: list[float],
        horizon: int,
        num_samples: int = 20,
        request_id: str | None = None,
    ) -> ForecastEnvelope:
        info, base = self.resolve(model_id)
        payload = ForecastRequest(
            context=context,
            prediction_length=horizon,
            num_samples=num_samples,
            model_id=model_id,
        )
        raw = await self.post(
            info.forecast_path,
            json=payload.model_dump(),
            request_id=request_id,
            base_url=base,
        )
        # Validate on the way in: an unrecognised shape raises here rather than
        # degrading to a sentinel price downstream.
        return ForecastEnvelope.model_validate(raw)
