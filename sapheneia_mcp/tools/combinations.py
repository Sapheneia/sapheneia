"""Combinations YAML validation, matrix expansion, strategy rendering."""

from __future__ import annotations

import json
from itertools import product
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined
from pydantic import BaseModel, Field, ValidationError, field_validator

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_DIR = REPO_ROOT / "simulations" / "templates"


class _Cache(BaseModel):
    enabled: bool = False
    scope: str = "experiment"
    what: list[str] = Field(default_factory=lambda: ["forecasts"])


class _Parallelism(BaseModel):
    max_concurrent_runs: int = 4
    max_per_model: int = 2


class _Matrix(BaseModel):
    ticker: list[str]
    model: list[str]
    trading_horizon: list[int] = Field(default_factory=lambda: [1])
    context_size: list[int] = Field(default_factory=lambda: [252])
    strategy_type: list[str]


class _Common(BaseModel):
    fetch_start_date: str
    start_date: str
    end_date: str
    forecast_horizon: int = Field(ge=1, le=1000)
    initial_capital: float = Field(gt=0)
    initial_position: float = 0.0


class CombinationsSchema(BaseModel):
    metadata: dict[str, Any]
    matrix: _Matrix
    common: _Common
    strategy_params: dict[str, dict[str, Any]] = Field(default_factory=dict)
    metrics: list[str] = Field(default_factory=list)
    cache: _Cache = Field(default_factory=_Cache)
    parallelism: _Parallelism = Field(default_factory=_Parallelism)

    @field_validator("matrix")
    @classmethod
    def _check_horizons(cls, m: _Matrix, info) -> _Matrix:
        common: _Common | None = info.data.get("common")
        if common is not None and any(h > common.forecast_horizon for h in m.trading_horizon):
            raise ValueError(
                f"all trading_horizon values must be <= common.forecast_horizon"
                f" ({common.forecast_horizon})"
            )
        return m


# ----- public tool entrypoints -----------------------------------------------


def validate_combinations(yaml_text: str) -> dict:
    """Validate combinations YAML against the schema. Returns {valid, errors}."""
    try:
        data = yaml.safe_load(yaml_text)
    except yaml.YAMLError as exc:
        return {"valid": False, "errors": [f"YAML parse error: {exc}"]}
    try:
        CombinationsSchema.model_validate(data)
    except ValidationError as exc:
        return {"valid": False, "errors": [str(e) for e in exc.errors()]}
    return {"valid": True, "errors": []}


def expand_matrix(yaml_text: str) -> list[dict]:
    """Expand the matrix into combinations grouped by forecast cohort.

    Returns a list of cohorts. Each cohort:
        {forecast_key: {model, ticker, context_size}, strategy_variants: [...]}
    Strategy variants share the forecast call, differing only in trading
    horizon and strategy_type.
    """
    data = yaml.safe_load(yaml_text)
    schema = CombinationsSchema.model_validate(data)

    cohorts: dict[tuple[str, str, int], list[dict]] = {}
    for ticker, model, trading_horizon, context_size, strategy_type in product(
        schema.matrix.ticker,
        schema.matrix.model,
        schema.matrix.trading_horizon,
        schema.matrix.context_size,
        schema.matrix.strategy_type,
    ):
        key = (model, ticker, context_size)
        cohorts.setdefault(key, []).append(
            {
                "ticker": ticker,
                "model": model,
                "trading_horizon": trading_horizon,
                "context_size": context_size,
                "strategy_type": strategy_type,
            }
        )

    return [
        {
            "forecast_key": {"model": k[0], "ticker": k[1], "context_size": k[2]},
            "strategy_variants": v,
        }
        for k, v in cohorts.items()
    ]


def render_strategies(combinations_yaml_text: str, cohort: dict) -> list[str]:
    """Render strategy YAMLs for one cohort using the Jinja2 template."""
    data = yaml.safe_load(combinations_yaml_text)
    schema = CombinationsSchema.model_validate(data)

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        undefined=StrictUndefined,
        autoescape=False,
        keep_trailing_newline=True,
    )
    env.filters["to_json"] = lambda v: json.dumps(v)
    template = env.get_template("strategy.yaml.j2")

    rendered: list[str] = []
    for variant in cohort["strategy_variants"]:
        ctx = {
            "experiment_id": schema.metadata.get("experiment_id", "default"),
            "ticker": variant["ticker"],
            "model": variant["model"],
            "trading_horizon": variant["trading_horizon"],
            "context_size": variant["context_size"],
            "strategy_type": variant["strategy_type"],
            "common": schema.common.model_dump(),
            "strategy_params": schema.strategy_params,
            "metrics": schema.metrics,
            "cache": schema.cache.model_dump(),
        }
        rendered.append(template.render(ctx))
    return rendered


def write_rendered_to_disk(experiment_id: str, rendered_yamls: list[str]) -> list[str]:
    """Persist rendered strategy YAMLs under experiments/{TIMESTAMP}/."""
    from datetime import datetime

    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    out_dir = REPO_ROOT / "experiments" / f"{experiment_id}_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    for idx, body in enumerate(rendered_yamls):
        p = out_dir / f"strategy_{idx:04d}.yaml"
        p.write_text(body)
        paths.append(str(p))
    return paths
