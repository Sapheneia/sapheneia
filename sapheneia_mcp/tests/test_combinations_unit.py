"""Unit tests for the combinations matrix expansion + rendering."""

from __future__ import annotations

import yaml

from sapheneia_mcp.tools import combinations as combo


def test_validate_returns_valid(combinations_yaml: str) -> None:
    result = combo.validate_combinations(combinations_yaml)
    assert result["valid"] is True
    assert result["errors"] == []


def test_validate_rejects_horizon_overflow(combinations_yaml: str) -> None:
    bad = combinations_yaml.replace("trading_horizon:  [1, 5]", "trading_horizon:  [1, 100]")
    result = combo.validate_combinations(bad)
    assert result["valid"] is False
    assert any("trading_horizon" in str(e) for e in result["errors"])


def test_validate_rejects_garbage_yaml() -> None:
    result = combo.validate_combinations(":\n  - bad")
    # Either YAML parse error or schema error; both fine.
    assert result["valid"] is False


def test_expand_matrix_groups_by_forecast_cohort(combinations_yaml: str) -> None:
    cohorts = combo.expand_matrix(combinations_yaml)
    # 2 tickers × 2 models × 2 context = 8 cohorts; each with 2 horizons × 2 strategies = 4 variants
    assert len(cohorts) == 8
    for c in cohorts:
        assert set(c["forecast_key"].keys()) == {"model", "ticker", "context_size"}
        assert len(c["strategy_variants"]) == 4


def test_render_strategies_produces_parseable_yaml(combinations_yaml: str, tmp_path) -> None:
    cohorts = combo.expand_matrix(combinations_yaml)
    rendered = combo.render_strategies(combinations_yaml, cohorts[0])
    assert len(rendered) == 4
    for body in rendered:
        parsed = yaml.safe_load(body)
        assert parsed["forecast"]["model"] == cohorts[0]["forecast_key"]["model"]
        assert parsed["forecast"]["context_size"] == cohorts[0]["forecast_key"]["context_size"]
        assert parsed["evaluation"]["ticker"] == cohorts[0]["forecast_key"]["ticker"]
        assert parsed["trading"]["horizon"] in {1, 5}
        assert parsed["trading"]["strategy_type"] in {"threshold", "quantile"}
        assert parsed["cache"]["enabled"] is True
