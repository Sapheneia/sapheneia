"""Cross-schema constraint tests.

The min_history/window contradiction previously behaved differently per code
path (checked before vs after the window slice), so the same config either ran
or silently fell back depending on whether window_history was written
explicitly. pandas rolling's precedent: reject it at construction.
"""

import pydantic
import pytest

from trading.schemas.schema import (
    QuantileStrategyRequest,
    ReturnStrategyRequest,
    ThresholdStrategyRequest,
)

_COMMON = {
    "forecast_price": 110.0,
    "current_price": 100.0,
    "current_position": 0.0,
    "available_cash": 100_000.0,
    "initial_capital": 100_000.0,
}
_HISTORY = [100.0 + i for i in range(20)]
_QUANTILE_EXTRA = {
    "which_history": "close",
    "quantile_signals": {0: {"range": [0, 100], "signal": "hold", "multiplier": 0.0}},
    "open_history": _HISTORY,
    "high_history": _HISTORY,
    "low_history": _HISTORY,
    "close_history": _HISTORY,
}

CASES = [
    (ThresholdStrategyRequest, {"threshold_type": "percentage", "threshold_value": 1.0}),
    (ReturnStrategyRequest, {"position_sizing": "fixed", "threshold_value": 0.05}),
    (QuantileStrategyRequest, _QUANTILE_EXTRA),
]


@pytest.mark.parametrize(("schema", "extra"), CASES, ids=lambda c: getattr(c, "__name__", ""))
def test_min_history_above_window_is_rejected(schema, extra) -> None:
    with pytest.raises(pydantic.ValidationError, match="must be <= window_history"):
        schema(**_COMMON, **extra, window_history=20, min_history_length=30)


@pytest.mark.parametrize(("schema", "extra"), CASES, ids=lambda c: getattr(c, "__name__", ""))
def test_min_history_equal_to_window_is_accepted(schema, extra) -> None:
    schema(**_COMMON, **extra, window_history=20, min_history_length=20)
