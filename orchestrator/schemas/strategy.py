"""Pydantic models for the rendered strategy YAML the orchestrator consumes."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class StrategyMetadata(BaseModel):
    id: str
    experiment_id: str = "default"
    description: str = ""
    author: str = ""


class EvaluationConfig(BaseModel):
    ticker: str
    fetch_start_date: str  # YYYYMMDD or ISO
    start_date: str
    end_date: str

    def parse_date(self, key: str) -> date:
        v = getattr(self, key)
        return _parse_date_str(v, key)


class ForecastConfig(BaseModel):
    model: str
    context_size: int = Field(ge=1, le=10_000)
    forecast_horizon: int = Field(ge=1, le=1000)


class TradingConfig(BaseModel):
    horizon: int = Field(default=1, ge=1, le=1000)
    initial_capital: float = Field(gt=0)
    initial_position: float = 0.0
    initial_cash: float | None = None
    strategy_type: Literal["threshold", "return", "quantile"]
    params: dict[str, Any] = Field(default_factory=dict)


class CacheConfig(BaseModel):
    enabled: bool = False
    scope: Literal["experiment", "global"] = "experiment"
    what: list[Literal["forecasts"]] = Field(default_factory=lambda: ["forecasts"])


class StrategyConfig(BaseModel):
    """Top-level rendered strategy YAML, parsed."""

    metadata: StrategyMetadata
    evaluation: EvaluationConfig
    forecast: ForecastConfig
    trading: TradingConfig
    metrics: list[str] = Field(default_factory=lambda: ["sharpe", "max_drawdown"])
    cache: CacheConfig = Field(default_factory=CacheConfig)

    @field_validator("trading")
    @classmethod
    def _check_horizon(cls, v: TradingConfig, info) -> TradingConfig:
        forecast_cfg = info.data.get("forecast")
        if forecast_cfg is not None and v.horizon > forecast_cfg.forecast_horizon:
            raise ValueError(
                f"trading.horizon ({v.horizon}) must be <= "
                f"forecast.forecast_horizon ({forecast_cfg.forecast_horizon})"
            )
        return v


def _parse_date_str(value: str, field: str) -> date:
    """Accept YYYY-MM-DD, YYYYMMDD, or full ISO."""
    if not value:
        raise ValueError(f"{field}: empty date string")
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(value).date()
    except ValueError as exc:
        raise ValueError(f"{field}: cannot parse '{value}'") from exc
