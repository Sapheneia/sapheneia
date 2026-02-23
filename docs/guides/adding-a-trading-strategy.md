# Adding a New Trading Strategy to Sapheneia

This guide walks through every code change required to add a new trading strategy
to the Sapheneia trading service. All six steps must be completed for the strategy
to be fully integrated: discoverable through the API, executable by the orchestrator,
schema-validated on input, and covered by automated tests.

The guide uses a placeholder strategy called `new_strat` throughout. Replace every
occurrence of `new_strat` / `NEW_STRAT` with your actual strategy name, following
the same casing conventions.

---

## Overview of the integration surface

A trading strategy touches six distinct locations in the codebase:

| Step | File | What changes |
|------|------|--------------|
| 1 | `trading/services/trading.py` | `StrategyType` enum |
| 2 | `trading/services/trading.py` | `TradingStrategy` class |
| 3 | `trading/services/trading.py` | `generate_trading_signal()` router |
| 4 | `orchestration/clients/trading_client.py` | `StrategyType` enum |
| 5 | `trading/schemas/schema.py` | Pydantic request schema |
| 6 | `tests/trading/` | Unit and endpoint tests |

---

## Step 1: Define the strategy type in the service enum

Open `trading/services/trading.py` and locate the `StrategyType` enum. Add your new
variant alongside the existing ones.

**Before:**

```python
class StrategyType(Enum):
    THRESHOLD = "threshold"
    RETURN = "return"
    QUANTILE = "quantile"
```

**After:**

```python
class StrategyType(Enum):
    THRESHOLD = "threshold"
    RETURN = "return"
    QUANTILE = "quantile"
    NEW_STRAT = "new_strat"
```

Note: The service-side `StrategyType` inherits from `Enum` only (not `str`).
Use `.value` to get the string representation when needed (e.g. `StrategyType.NEW_STRAT.value == "new_strat"`).

The string value (`"new_strat"`) is the exact value clients must send in the
`strategy_type` field of every request.

---

## Step 2: Implement signal calculation

Add a `@staticmethod` method named `calculate_new_strat_signal` to the
`TradingStrategy` class in `trading/services/trading.py`.

### Method contract

The method must accept a single `params: dict` argument and return a dictionary
with the following keys:

| Key | Type | Description |
|-----|------|-------------|
| `action` | `str` | One of `"buy"`, `"sell"`, or `"hold"` |
| `size` | `float` | Recommended position size (shares/units, non-negative) |
| `reason` | `str` | Human-readable explanation of the signal |
| `available_cash` | `float` | Cash remaining after the hypothetical trade |
| `position_after` | `float` | Position size after the hypothetical trade |
| `stopped` | `bool` | `True` if no capital remains and the strategy should halt |

Note that `execute_trading_signal` (the public entry point) wraps this output and
enforces capital constraints before returning to the caller. Your signal method
only needs to recommend an action and size; the execution layer handles the rest.

### Internal helpers

Use the two helper statics already defined on `TradingStrategy` for data preparation:

- `_validate_common_params(params)` - raises `InvalidParametersError` for missing or
  out-of-range common fields (`forecast_price`, `current_price`, `current_position`,
  `available_cash`, `initial_capital`). Call this at the top of every signal method.
- `_convert_to_array(data)` - converts a `list[float]` or `None` to a `np.ndarray`
  or `None`. Use this before operating on any OHLC history passed in `params`.
- `_get_history_array(params, which_history)` - returns the correct numpy array from
  `params` based on the value of `which_history` (`"open"`, `"high"`, `"low"`, or
  `"close"`).

### Example implementation

The example below implements a simple moving-average crossover signal. It buys when
the forecast price is above the short-period SMA and sells when below. Adapt the
logic to your actual strategy.

```python
@staticmethod
def calculate_new_strat_signal(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate new_strat trading signal using a moving-average crossover.

    Buys when forecast_price exceeds the short-period SMA of recent closes,
    sells when it falls below, and holds otherwise.

    Args:
        params: Dictionary containing strategy parameters. Required:
            - forecast_price: float - Forecasted price
            - current_price: float - Current market price
            - current_position: float - Current position size
            - available_cash: float - Available cash
            - initial_capital: float - Initial capital
            - close_history: List[float] - Recent close prices (min 2 elements)
        Optional:
            - short_window: int - SMA period (default: 5)
            - execution_size: float - Shares to trade (default: 1.0)
            - min_history_length: int - Minimum close_history length (default: 2)

    Returns:
        Dictionary with keys: action, size, reason, available_cash,
        position_after, stopped.

    Raises:
        InvalidParametersError: If required parameters are missing or invalid.
    """
    # Always validate common params first.
    TradingStrategy._validate_common_params(params)

    # Extract strategy-specific parameters with safe defaults.
    forecast_price = params["forecast_price"]
    current_price = params["current_price"]
    current_position = params["current_position"]
    available_cash = params["available_cash"]
    short_window = params.get("short_window", 5)
    execution_size = params.get("execution_size", settings.DEFAULT_EXECUTION_SIZE)
    min_history_length = params.get(
        "min_history_length", settings.DEFAULT_MIN_HISTORY_LENGTH
    )

    # Validate strategy-specific parameters.
    if short_window <= 0:
        raise InvalidParametersError(
            message="short_window must be positive",
            parameter="short_window",
            validation_errors={"short_window": short_window},
        )

    if execution_size <= 0:
        raise InvalidParametersError(
            message="execution_size must be positive",
            parameter="execution_size",
            validation_errors={"execution_size": execution_size},
        )

    # Convert history to numpy array (returns None if not provided).
    close_history = TradingStrategy._convert_to_array(params.get("close_history"))

    # Fall back to hold if we lack sufficient history.
    if close_history is None or len(close_history) < min_history_length:
        logger.warning(
            "Insufficient close_history for new_strat signal, returning hold. "
            "History length: %d",
            len(close_history) if close_history is not None else 0,
        )
        return {
            "action": "hold",
            "size": 0,
            "reason": "Insufficient close history for new_strat calculation",
            "available_cash": available_cash,
            "position_after": current_position,
            "stopped": False,
        }

    # Calculate the short SMA from the most recent window of closes.
    recent = close_history[-short_window:]
    short_sma = float(np.mean(recent))

    logger.debug(
        "new_strat: forecast=%.4f, short_sma=%.4f, current_price=%.4f",
        forecast_price,
        short_sma,
        current_price,
    )

    if forecast_price > short_sma:
        return {
            "action": "buy",
            "size": execution_size,
            "reason": (
                f"Forecast {forecast_price:.4f} > short SMA {short_sma:.4f} "
                f"(window={short_window})"
            ),
            "available_cash": available_cash,
            "position_after": current_position,
            "stopped": False,
        }
    elif forecast_price < short_sma:
        return {
            "action": "sell",
            "size": execution_size,
            "reason": (
                f"Forecast {forecast_price:.4f} < short SMA {short_sma:.4f} "
                f"(window={short_window})"
            ),
            "available_cash": available_cash,
            "position_after": current_position,
            "stopped": False,
        }
    else:
        return {
            "action": "hold",
            "size": 0,
            "reason": (
                f"Forecast {forecast_price:.4f} == short SMA {short_sma:.4f}, "
                "no edge"
            ),
            "available_cash": available_cash,
            "position_after": current_position,
            "stopped": False,
        }
```

### Key conventions to follow

- Always call `_validate_common_params(params)` before touching any field in
  `params`. It raises `InvalidParametersError` with structured details for every
  missing or invalid common field.
- Return `stopped: True` only when both `available_cash <= 0` and
  `position_after <= 0`. The execution layer in `execute_trading_signal` also
  performs this check, but setting it accurately in the signal method ensures
  correct audit logging.
- Log at `DEBUG` level for per-tick diagnostic data and at `WARNING` level for
  fallback conditions (missing history, invalid inputs that trigger defaults).
- Do not mutate `params`. Extract values into local variables only.
- Raise `InvalidParametersError` (imported from `trading.core.exceptions`) for
  strategy-specific validation failures, not generic `ValueError`.

---

## Step 3: Add routing in generate_trading_signal

`generate_trading_signal` is the dispatcher that routes a request to the correct
signal calculation method. Add an `elif` branch for `NEW_STRAT`.

**Location:** `trading/services/trading.py`, inside `TradingStrategy`.

**Before:**

```python
if strategy_type == StrategyType.THRESHOLD.value:
    return TradingStrategy.calculate_threshold_signal(params)

elif strategy_type == StrategyType.RETURN.value:
    return TradingStrategy.calculate_return_signal(params)

elif strategy_type == StrategyType.QUANTILE.value:
    return TradingStrategy.calculate_quantile_signal(params)

else:
    error_msg = f"Unknown strategy type: {strategy_type}"
    logger.error(error_msg)
    raise InvalidStrategyError(message=error_msg, strategy_type=strategy_type)
```

**After:**

```python
if strategy_type == StrategyType.THRESHOLD.value:
    return TradingStrategy.calculate_threshold_signal(params)

elif strategy_type == StrategyType.RETURN.value:
    return TradingStrategy.calculate_return_signal(params)

elif strategy_type == StrategyType.QUANTILE.value:
    return TradingStrategy.calculate_quantile_signal(params)

elif strategy_type == StrategyType.NEW_STRAT.value:
    return TradingStrategy.calculate_new_strat_signal(params)

else:
    error_msg = f"Unknown strategy type: {strategy_type}"
    logger.error(error_msg)
    raise InvalidStrategyError(message=error_msg, strategy_type=strategy_type)
```

The dispatcher normalizes the incoming `strategy_type` to lowercase before
comparison (`str(strategy_type).lower()`), so both `"new_strat"` and `"NEW_STRAT"`
resolve correctly to `StrategyType.NEW_STRAT.value`.

---

## Step 4: Add client support in the orchestration layer

The orchestration service accesses the trading service through
`orchestration/clients/trading_client.py`. This module defines its own `StrategyType`
enum, separate from the one in the trading service, to avoid a cross-service import
dependency.

You must mirror the new variant here.

**Location:** `orchestration/clients/trading_client.py`

**Before:**

```python
class StrategyType(str, Enum):
    """Available trading strategy types for signal generation."""
    THRESHOLD = "threshold"
    RETURN = "return"
    QUANTILE = "quantile"
```

**After:**

```python
class StrategyType(str, Enum):
    """Available trading strategy types for signal generation."""
    THRESHOLD = "threshold"
    RETURN = "return"
    QUANTILE = "quantile"
    NEW_STRAT = "new_strat"
```

`TradingClient.execute_signal` reads `strategy_type.value` when building the
request payload (line: `"strategy_type": strategy_type.value`), so the string value
`"new_strat"` is what the trading service receives over HTTP.

If your strategy has common default parameters that the orchestrator should supply
when the caller does not provide them explicitly, add a corresponding block in
`execute_signal` alongside the existing `THRESHOLD` defaults block:

```python
# In TradingClient.execute_signal, after the existing defaults block:
if strategy_type == StrategyType.NEW_STRAT:
    payload.setdefault("short_window", 5)
    payload.setdefault("execution_size", 10.0)
```

---

## Step 5: Add schema validation

Pydantic schemas in `trading/schemas/schema.py` validate every incoming HTTP
request body before it reaches `TradingStrategy`. Create a new schema class that
inherits from `BaseStrategyRequest` and overrides only the fields specific to your
strategy.

### Add the new strategy type to StrategyTypeEnum

`StrategyTypeEnum` in `schema.py` is used by `BaseStrategyRequest`. Add the new
variant:

```python
class StrategyTypeEnum(str, Enum):
    THRESHOLD = "threshold"
    RETURN = "return"
    QUANTILE = "quantile"
    NEW_STRAT = "new_strat"
```

### Create the request schema

Add the new schema class after the existing strategy schemas and before the
discriminated union at the bottom of the file:

```python
class NewStratRequest(BaseStrategyRequest):
    """
    Schema for new_strat trading strategy.

    Validates inputs for the moving-average crossover strategy. Requires
    at least min_history_length elements in close_history.
    """

    strategy_type: Literal["new_strat"] = "new_strat"

    # Strategy-specific required fields
    close_history: List[float] = Field(
        ...,
        description="Recent close prices used for SMA calculation (required)",
    )

    # Strategy-specific optional fields
    short_window: int = Field(
        default=5,
        gt=0,
        le=settings.MAX_HISTORY_WINDOW,
        description=(
            f"SMA window period (must be positive, "
            f"max: {settings.MAX_HISTORY_WINDOW})"
        ),
    )
    execution_size: float = Field(
        default=1.0,
        gt=0,
        description="Number of shares to trade per signal (must be positive)",
    )
    min_history_length: Optional[int] = Field(
        default=2,
        gt=0,
        description="Minimum close_history length required (must be positive)",
    )

    @field_validator("close_history")
    @classmethod
    def validate_close_history(cls, v: List[float]) -> List[float]:
        """Validate close_history is non-empty and within size limits."""
        if len(v) == 0:
            raise ValueError("close_history cannot be empty")
        if len(v) > settings.MAX_ARRAY_SIZE:
            raise ValueError(
                f"close_history cannot exceed {settings.MAX_ARRAY_SIZE} elements"
            )
        return v

    @model_validator(mode="after")
    def validate_window_fits_history(self) -> "NewStratRequest":
        """Validate that short_window does not exceed close_history length."""
        if self.short_window > len(self.close_history):
            raise ValueError(
                f"short_window ({self.short_window}) cannot exceed "
                f"close_history length ({len(self.close_history)})"
            )
        return self

    class Config:
        json_schema_extra = {
            "example": {
                "strategy_type": "new_strat",
                "forecast_price": 105.0,
                "current_price": 100.0,
                "current_position": 0.0,
                "available_cash": 100000.0,
                "initial_capital": 100000.0,
                "close_history": [98.0, 99.0, 100.5, 101.0, 102.0],
                "short_window": 5,
                "execution_size": 10.0,
            }
        }
```

### Update the discriminated union

The `StrategyRequest` union type at the bottom of `schema.py` controls which schema
FastAPI selects based on `strategy_type`. Add `NewStratRequest` to it:

**Before:**

```python
StrategyRequest = Union[
    ThresholdStrategyRequest, ReturnStrategyRequest, QuantileStrategyRequest
]
```

**After:**

```python
StrategyRequest = Union[
    ThresholdStrategyRequest,
    ReturnStrategyRequest,
    QuantileStrategyRequest,
    NewStratRequest,
]
```

FastAPI uses the `Literal["new_strat"]` annotation on `strategy_type` to
discriminate between union members without ambiguity.

---

## Step 6: Write tests

Create a test file at `tests/trading/test_new_strat.py`. The file should cover three
categories: signal calculation logic, parameter validation, and the HTTP endpoint.

```python
"""
Tests for the new_strat trading strategy.

Covers:
- Signal calculation: buy, sell, and hold scenarios
- Validation: missing required params, invalid values, window constraints
- HTTP endpoint: round-trip via FastAPI TestClient
"""

import pytest
from typing import Dict, Any

# Attempt to import the trading app; skip all tests if dependencies are absent.
try:
    from fastapi.testclient import TestClient
    from trading.main import app
    from trading.services.trading import TradingStrategy, StrategyType
    from trading.core.exceptions import InvalidParametersError
    from trading.core.config import settings

    APP_AVAILABLE = True
except ImportError as e:
    APP_AVAILABLE = False
    APP_IMPORT_ERROR = str(e)

pytestmark = pytest.mark.skipif(
    not APP_AVAILABLE,
    reason="trading.main app cannot be imported (likely missing dependencies)",
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client() -> TestClient:
    """FastAPI TestClient for the trading app."""
    return TestClient(app)


@pytest.fixture
def auth_headers() -> Dict[str, str]:
    """Bearer token headers for authenticated requests."""
    return {"Authorization": f"Bearer {settings.TRADING_API_KEY}"}


@pytest.fixture
def base_params() -> Dict[str, Any]:
    """Minimal common parameters shared by all new_strat tests."""
    return {
        "strategy_type": "new_strat",
        "forecast_price": 105.0,
        "current_price": 100.0,
        "current_position": 0.0,
        "available_cash": 100_000.0,
        "initial_capital": 100_000.0,
        "close_history": [96.0, 97.0, 98.0, 99.0, 100.0],
        "short_window": 5,
        "execution_size": 10.0,
    }


# ---------------------------------------------------------------------------
# Signal calculation tests
# ---------------------------------------------------------------------------


class TestNewStratSignal:
    """Unit tests for TradingStrategy.calculate_new_strat_signal."""

    def test_buy_signal_when_forecast_above_sma(self, base_params):
        """Buy when forecast exceeds the short-period SMA."""
        # SMA of [96, 97, 98, 99, 100] == 98.0; forecast 105 > 98 -> buy.
        result = TradingStrategy.calculate_new_strat_signal(base_params)

        assert result["action"] == "buy"
        assert result["size"] == base_params["execution_size"]
        assert result["stopped"] is False
        assert "short SMA" in result["reason"]

    def test_sell_signal_when_forecast_below_sma(self, base_params):
        """Sell when forecast falls below the short-period SMA."""
        # SMA of [96, 97, 98, 99, 100] == 98.0; forecast 85 < 98 -> sell.
        params = {**base_params, "forecast_price": 85.0}
        result = TradingStrategy.calculate_new_strat_signal(params)

        assert result["action"] == "sell"
        assert result["size"] == base_params["execution_size"]
        assert result["stopped"] is False

    def test_hold_signal_when_forecast_equals_sma(self, base_params):
        """Hold when forecast equals the SMA (no statistical edge)."""
        # Mean of [96, 97, 98, 99, 100] == 98.0.
        params = {**base_params, "forecast_price": 98.0}
        result = TradingStrategy.calculate_new_strat_signal(params)

        assert result["action"] == "hold"
        assert result["size"] == 0

    def test_hold_when_history_is_missing(self, base_params):
        """Return hold gracefully when no close_history is provided."""
        params = {k: v for k, v in base_params.items() if k != "close_history"}
        result = TradingStrategy.calculate_new_strat_signal(params)

        assert result["action"] == "hold"
        assert result["size"] == 0
        assert "Insufficient" in result["reason"]

    def test_hold_when_history_too_short(self, base_params):
        """Return hold when history length is below min_history_length."""
        params = {**base_params, "close_history": [100.0], "min_history_length": 5}
        result = TradingStrategy.calculate_new_strat_signal(params)

        assert result["action"] == "hold"

    def test_strategy_type_registered_in_enum(self):
        """NEW_STRAT must be present in the service StrategyType enum."""
        assert StrategyType.NEW_STRAT.value == "new_strat"

    def test_buy_preserves_portfolio_state(self, base_params):
        """Buy signal returns unchanged available_cash and position_after
        (capital management is handled by execute_trading_signal, not here)."""
        result = TradingStrategy.calculate_new_strat_signal(base_params)

        assert result["available_cash"] == base_params["available_cash"]
        assert result["position_after"] == base_params["current_position"]


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------


class TestNewStratValidation:
    """Tests that invalid inputs raise the correct exceptions."""

    def test_missing_forecast_price_raises(self, base_params):
        """InvalidParametersError when forecast_price is absent."""
        params = {k: v for k, v in base_params.items() if k != "forecast_price"}
        with pytest.raises(InvalidParametersError):
            TradingStrategy.calculate_new_strat_signal(params)

    def test_missing_current_price_raises(self, base_params):
        """InvalidParametersError when current_price is absent."""
        params = {k: v for k, v in base_params.items() if k != "current_price"}
        with pytest.raises(InvalidParametersError):
            TradingStrategy.calculate_new_strat_signal(params)

    def test_negative_forecast_price_raises(self, base_params):
        """InvalidParametersError when forecast_price is not positive."""
        params = {**base_params, "forecast_price": -10.0}
        with pytest.raises(InvalidParametersError):
            TradingStrategy.calculate_new_strat_signal(params)

    def test_negative_execution_size_raises(self, base_params):
        """InvalidParametersError when execution_size is not positive."""
        params = {**base_params, "execution_size": -5.0}
        with pytest.raises(InvalidParametersError):
            TradingStrategy.calculate_new_strat_signal(params)

    def test_zero_short_window_raises(self, base_params):
        """InvalidParametersError when short_window is zero."""
        params = {**base_params, "short_window": 0}
        with pytest.raises(InvalidParametersError):
            TradingStrategy.calculate_new_strat_signal(params)

    def test_negative_current_position_raises(self, base_params):
        """InvalidParametersError for negative (short) positions."""
        params = {**base_params, "current_position": -1.0}
        with pytest.raises(InvalidParametersError):
            TradingStrategy.calculate_new_strat_signal(params)


# ---------------------------------------------------------------------------
# Endpoint tests
# ---------------------------------------------------------------------------


class TestNewStratEndpoint:
    """Integration tests via FastAPI TestClient for the /trading/execute endpoint."""

    def test_valid_request_returns_200(self, client, auth_headers, base_params):
        """A well-formed new_strat request returns HTTP 200 with a valid body."""
        response = client.post(
            "/trading/execute",
            json=base_params,
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["action"] in ("buy", "sell", "hold")
        assert data["size"] >= 0
        assert isinstance(data["reason"], str)
        assert isinstance(data["stopped"], bool)

    def test_unauthenticated_request_returns_401(self, client, base_params):
        """Requests without a valid API key are rejected."""
        response = client.post("/trading/execute", json=base_params)
        assert response.status_code == 401

    def test_missing_close_history_returns_422(self, client, auth_headers, base_params):
        """Omitting close_history fails Pydantic validation with HTTP 422."""
        params = {k: v for k, v in base_params.items() if k != "close_history"}
        response = client.post(
            "/trading/execute",
            json=params,
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_empty_close_history_returns_422(self, client, auth_headers, base_params):
        """An empty close_history array fails the field_validator with HTTP 422."""
        params = {**base_params, "close_history": []}
        response = client.post(
            "/trading/execute",
            json=params,
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_window_exceeds_history_returns_422(self, client, auth_headers, base_params):
        """short_window larger than close_history fails model validation."""
        params = {**base_params, "short_window": 20, "close_history": [100.0, 101.0]}
        response = client.post(
            "/trading/execute",
            json=params,
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_invalid_strategy_type_returns_422(self, client, auth_headers, base_params):
        """An unrecognised strategy_type is rejected at schema validation."""
        params = {**base_params, "strategy_type": "nonexistent_strategy"}
        response = client.post(
            "/trading/execute",
            json=params,
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_buy_signal_end_to_end(self, client, auth_headers, base_params):
        """When forecast is above SMA, the endpoint returns action=buy."""
        # forecast_price 105 > SMA(96..100) = 98, so we expect buy.
        response = client.post(
            "/trading/execute",
            json=base_params,
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["action"] == "buy"

    def test_sell_signal_end_to_end(self, client, auth_headers, base_params):
        """When forecast is below SMA, the endpoint returns action=sell."""
        params = {**base_params, "forecast_price": 85.0}
        response = client.post(
            "/trading/execute",
            json=params,
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["action"] == "sell"
```

Run the tests from the project root:

```bash
pytest tests/trading/test_new_strat.py -v
```

---

## Checklist

Use this checklist before opening a pull request:

- [ ] `StrategyType.NEW_STRAT = "new_strat"` added to `trading/services/trading.py`
- [ ] `calculate_new_strat_signal` implemented as a `@staticmethod` on `TradingStrategy`
- [ ] `_validate_common_params` called at the top of the signal method
- [ ] `elif strategy_type == StrategyType.NEW_STRAT.value` branch added in `generate_trading_signal`
- [ ] `StrategyType.NEW_STRAT = "new_strat"` added to `orchestration/clients/trading_client.py`
- [ ] `StrategyTypeEnum.NEW_STRAT = "new_strat"` added to `trading/schemas/schema.py`
- [ ] `NewStratRequest(BaseStrategyRequest)` created with `Literal["new_strat"]` on `strategy_type`
- [ ] `NewStratRequest` added to the `StrategyRequest` discriminated union
- [ ] All three test classes (signal, validation, endpoint) implemented and passing
- [ ] No `shell=True`, `pickle`, or hardcoded secrets introduced

---

## Common mistakes

**Forgetting to update the client enum.**
The trading service will accept the new strategy type, but the orchestrator will fail
to construct a valid `StrategyType` enum member when it tries to pass the value
through `TradingClient.execute_signal`. Always keep both enums in sync.

**Not adding to the discriminated union.**
If `NewStratRequest` is defined but not included in `StrategyRequest`, FastAPI will
route new_strat requests to the first union member that matches (`ThresholdStrategyRequest`),
which will reject them with a 422 validation error because `threshold_type` is missing.

**Omitting the `Literal` annotation on `strategy_type`.**
The discriminated union relies on `strategy_type: Literal["new_strat"]` to route
requests without ambiguity. If you use `StrategyTypeEnum` instead of `Literal`, Pydantic
cannot determine which union member to instantiate and falls back to left-to-right
matching, which will behave incorrectly for overlapping fields.

**Not calling `_validate_common_params` first.**
Signal methods that bypass this call will produce cryptic `KeyError` exceptions
instead of structured `InvalidParametersError` responses when required fields are
absent.
