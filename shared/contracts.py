"""Canonical request/response envelopes shared between the orchestrator and
the forecast leaf services.

Why this exists
---------------
Before this contract, the orchestrator sniffed three different response shapes
(``median``, ``forecast.values``, ``prediction.median``) and fell back to
``0.0`` when none matched. ``0.0`` is not an error to the trading service — it
is an extremely strong SELL signal, so a contract drift produced a full run of
confident, wrong trades that still terminated as ``status = completed``.

For a backtesting platform, silently-wrong is strictly worse than failing. So:
one envelope, validated on the way out of the leaf service and on the way into
the orchestrator, and an unrecognised shape raises.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class ForecastRequest(BaseModel):
    """The one request shape every forecast family accepts.

    Note there is no ``model_variant``/``checkpoint`` field: which model runs is
    determined by *which container is called* (each pins one model via
    ``MODEL_VARIANT``). ``model_id`` is carried only so the service can assert
    the caller reached the right container and refuse otherwise.
    """

    #: Bounded: the model containers are single-worker and pinned, so one
    #: oversized request would OOM the container and take out every run that
    #: needs that model. 8192 is far above any realistic backtest context.
    context: list[float] = Field(
        ..., min_length=2, max_length=8192, description="Historical values, oldest first"
    )
    prediction_length: int = Field(..., gt=0, le=1024, description="Steps to forecast")
    num_samples: int = Field(default=20, gt=0, le=1000)
    model_id: str | None = Field(
        default=None,
        description="Expected model. If set and it does not match the model this "
        "container loaded, the request is rejected rather than silently served "
        "by the wrong model.",
    )


class QuantileBand(BaseModel):
    quantile: float = Field(..., ge=0.0, le=1.0)
    values: list[float]


class ForecastEnvelope(BaseModel):
    """The one response shape every forecast family returns."""

    model_id: str = Field(..., description="The model that actually produced this forecast")
    family: str
    median: list[float] = Field(..., min_length=1)
    quantiles: list[QuantileBand] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)

    @field_validator("median")
    @classmethod
    def _finite(cls, v: list[float]) -> list[float]:
        for x in v:
            if x != x or x in (float("inf"), float("-inf")):
                raise ValueError("median contains NaN or infinity")
        return v

    def quantile(self, q: float, *, tol: float = 1e-6) -> list[float] | None:
        for band in self.quantiles:
            if abs(band.quantile - q) < tol:
                return band.values
        return None

    def price_at_horizon(self, trading_horizon: int) -> float:
        """Point estimate ``trading_horizon`` steps ahead (1-indexed).

        Raises rather than returning a sentinel — see the module docstring.
        """
        if not self.median:
            raise ValueError("forecast envelope has an empty median series")
        if trading_horizon < 1:
            raise ValueError(f"trading_horizon must be >= 1, got {trading_horizon}")
        if trading_horizon > len(self.median):
            raise ValueError(
                f"trading_horizon={trading_horizon} exceeds forecast length {len(self.median)}"
            )
        return float(self.median[trading_horizon - 1])


class ModelMismatchError(ValueError):
    """Raised when a request reaches a container holding a different model."""
