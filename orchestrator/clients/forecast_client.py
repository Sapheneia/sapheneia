"""HTTP client for the forecast service.

Routes by model family to the right endpoint:
  chronos  → POST /forecast/v1/chronos/inference
  timesfm  → POST /forecast/v1/timesfm20/inference
"""

from __future__ import annotations

import httpx

from shared.model_family import ModelFamily


class ForecastClient:
    def __init__(self, base_url: str, *, api_key: str = "", timeout: float = 300.0):
        self._base = base_url.rstrip("/")
        self._timeout = timeout
        self._headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    async def predict(
        self,
        *,
        model_id: str,
        context: list[float],
        horizon: int,
        num_samples: int = 20,
        request_id: str | None = None,
    ) -> dict:
        family = ModelFamily.from_model_id(model_id)
        path = f"/forecast/v1/{family.route_suffix}/inference"
        body = {
            "context": context,
            "prediction_length": horizon,
            "num_samples": num_samples,
        }
        if family is ModelFamily.CHRONOS:
            body["model_variant"] = model_id
        else:
            body["checkpoint"] = model_id
        headers = dict(self._headers)
        if request_id:
            headers["X-Request-ID"] = request_id
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            r = await client.post(f"{self._base}{path}", json=body, headers=headers)
            r.raise_for_status()
            return r.json()
