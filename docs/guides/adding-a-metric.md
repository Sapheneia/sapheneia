# Developer Guide: Adding a New Performance Metric

This guide walks through every change required to add a new performance metric end-to-end. The metric is exposed through the Python metrics service and consumed by the Go orchestration layer. Follow all six steps in order; skipping steps will leave the system in an inconsistent state.

The example used throughout this guide is a hypothetical metric called `new_metric`. Replace the name with the actual metric you are implementing.

---

## Overview of the Change Set

| Step | File | What Changes |
|------|------|--------------|
| 1 | `metrics/core/metrics.py` | Add calculation function |
| 2 | `metrics/core/metrics.py` | Add to `calculate_performance_metrics()` aggregator |
| 3 | `metrics/routes/endpoints.py` | Add to `ComputeRequest` type and routing logic |
| 4 | `orchestration/clients/metrics_client.py` | Add field to `MetricsResponse` dataclass |
| 5 | `datatypes/evaluator.go` (AleutianFOSS) | Add field to Go struct |
| 6 | `tests/metrics/` | Write unit and integration tests |

---

## Step 1: Add the Calculation Function

**File:** `metrics/core/metrics.py`

Add a new function following the same pattern used by all existing metric functions. The critical requirements are:

- Accept `returns` as `List[float]` (or `Union[pd.Series, np.ndarray, List]` if you need to match the full signature)
- Call `_validate_returns(returns)` as the first thing inside the function body; this converts the input to a `pd.Series` with a `DatetimeIndex`, removes `NaN` and `Inf` values, and raises `ValueError` for degenerate inputs
- Wrap the quantstats call in a `try/except` returning `0.0` on failure; this prevents one metric's failure from breaking the entire aggregator
- Return a plain Python `float`

```python
def calculate_new_metric(
    returns: Union[pd.Series, np.ndarray, List],
    periods_per_year: int = 252
) -> float:
    """
    Calculate New Metric: one-line description of what it measures.

    Longer explanation of what the metric captures, when it is useful,
    and how to interpret its value.

    Args:
        returns: Return series (daily, weekly, or monthly returns as decimals)
        periods_per_year: Trading periods per year (252=daily, 52=weekly, 12=monthly)

    Returns:
        New metric value as a float. Returns 0.0 on calculation failure.

    Interpretation:
        > X: Description of what a high value means
        < Y: Description of what a low value means
    """
    returns = _validate_returns(returns)

    try:
        value = qs.stats.some_quantstats_function(returns, periods=periods_per_year)
        return float(value) if not np.isnan(value) else 0.0
    except Exception as e:
        logger.warning(f"Error calculating new metric: {e}")
        return 0.0
```

Key points:

- `_validate_returns` is called on the raw input before anything else. After this call, `returns` is a clean `pd.Series` with a `DatetimeIndex`.
- The `NaN` guard `if not np.isnan(value) else 0.0` handles cases where quantstats returns `NaN` for edge-case inputs.
- The `logger.warning` inside the `except` block is important for observability. Do not use `logger.error` here; the system degrades gracefully by returning `0.0` and a warning is the correct severity.
- `quantstats` is already imported at the module level as `qs`. Do not add a second import.

---

## Step 2: Add to the Aggregator

**File:** `metrics/core/metrics.py`, function `calculate_performance_metrics()`

The aggregator function computes all metrics in one call and is used by the `metric="performance"` and `metric="all"` endpoint routes.

Make two changes:

**2a. Call the new function** alongside the existing five calls:

```python
    # Calculate all metrics
    sharpe = calculate_sharpe_ratio(returns, risk_free_rate, periods_per_year)
    max_dd = calculate_max_drawdown(returns)
    cagr = calculate_cagr(returns, periods_per_year)
    calmar = calculate_calmar_ratio(returns, periods_per_year)
    win_rate = calculate_win_rate(returns)
    new_metric_value = calculate_new_metric(returns, periods_per_year)  # add this line
```

**2b. Add the value to the `result` dict:**

```python
    result = {
        "sharpe_ratio": sharpe,
        "max_drawdown": max_dd,
        "cagr": cagr,
        "calmar_ratio": calmar,
        "win_rate": win_rate,
        "new_metric": new_metric_value,  # add this line
        "metadata": {
            ...
        }
    }
```

Also update the docstring for `calculate_performance_metrics()` to list the new metric in the "Returns:" section:

```
    Returns:
        Dictionary containing:
            - sharpe_ratio: Risk-adjusted return metric
            - max_drawdown: Worst peak-to-trough decline
            - cagr: Compound annual growth rate
            - calmar_ratio: Return per unit of max drawdown
            - win_rate: Percentage of profitable periods
            - new_metric: Description of the new metric  # add this
            - interpretation: Human-readable assessment (if include_interpretation=True)
            - metadata: Configuration used for calculation
```

---

## Step 3: Add to the Endpoint

**File:** `metrics/routes/endpoints.py`

Two changes are needed in this file.

**3a. Extend the `Literal` type on `ComputeRequest.metric`:**

Locate the `ComputeRequest` model and add `"new_metric"` to the existing `Literal` union:

```python
class ComputeRequest(BaseModel):
    """Unified request model for metrics computation."""
    returns: List[float] = Field(..., description="Return series (e.g., daily returns)")
    metric: Literal[
        "performance",
        "all",
        "sharpe",
        "max_drawdown",
        "cagr",
        "calmar",
        "win_rate",
        "new_metric",   # add this
    ] = Field(
        default="performance",
        description="Metric to compute"
    )
```

Pydantic will reject any request with an unrecognized `metric` value with a 422 status code, so adding it to the `Literal` is the only validation change needed.

**3b. Add an `elif` branch in `compute_metrics()`:**

Add the branch immediately before the final `else` block that raises `HTTPException`:

```python
        elif request.metric == "new_metric":
            value = metrics.calculate_new_metric(
                request.returns,
                request.periods_per_year
            )
            return {"new_metric": value}

        else:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid metric: {request.metric}. ..."
            )
```

Also update the docstring for `compute_metrics()` to list the new option:

```
    ## Metric Options:

    - **performance**: All metrics with interpretation & metadata (default)
    - **all**: All metrics, clean response
    - **sharpe**: Sharpe Ratio only
    - **max_drawdown**: Maximum Drawdown only
    - **cagr**: CAGR only
    - **calmar**: Calmar Ratio only
    - **win_rate**: Win Rate only
    - **new_metric**: New Metric only   # add this
```

---

## Step 4: Update the Python Client

**File:** `orchestration/clients/metrics_client.py`

The `MetricsResponse` dataclass is the internal data transfer object used by the orchestration layer. It must match the fields returned by the `metric="all"` endpoint response.

**4a. Add the field to the dataclass:**

```python
@dataclass
class MetricsResponse:
    """Response from metrics service."""
    sharpe_ratio: float
    max_drawdown: float
    cagr: float
    calmar_ratio: float
    win_rate: float
    new_metric: float       # add this field
```

**4b. Update `from_dict()`:**

```python
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MetricsResponse":
        """Create MetricsResponse from compute endpoint response dict."""
        return cls(
            sharpe_ratio=data.get("sharpe_ratio", 0.0),
            max_drawdown=data.get("max_drawdown", 0.0),
            cagr=data.get("cagr", 0.0),
            calmar_ratio=data.get("calmar_ratio", 0.0),
            win_rate=data.get("win_rate", 0.0),
            new_metric=data.get("new_metric", 0.0),    # add this line
        )
```

**4c. Update `to_dict()`:**

```python
    def to_dict(self) -> Dict[str, float]:
        """Serialize metrics to dict for storage or transmission."""
        return {
            "sharpe_ratio": self.sharpe_ratio,
            "max_drawdown": self.max_drawdown,
            "cagr": self.cagr,
            "calmar_ratio": self.calmar_ratio,
            "win_rate": self.win_rate,
            "new_metric": self.new_metric,    # add this line
        }
```

Also update `_get_fallback_metrics()` to include the new field so the circuit breaker path returns a consistent object:

```python
    def _get_fallback_metrics(self) -> MetricsResponse:
        """Return fallback metrics when service unavailable."""
        return MetricsResponse(
            sharpe_ratio=0.0,
            max_drawdown=0.0,
            cagr=0.0,
            calmar_ratio=0.0,
            win_rate=0.0,
            new_metric=0.0,    # add this line
        )
```

---

## Step 5: Update the Go Consumer (AleutianFOSS)

**File:** `datatypes/evaluator.go` in the AleutianFOSS repository

Add the new field to the `MetricsResponse` struct. Use the `json` tag to match the snake_case key returned by the Python endpoint.

```go
// MetricsResponse holds performance metrics returned by the metrics service.
type MetricsResponse struct {
    SharpeRatio float64 `json:"sharpe_ratio"`
    MaxDrawdown float64 `json:"max_drawdown"`
    CAGR        float64 `json:"cagr"`
    CalmarRatio float64 `json:"calmar_ratio"`
    WinRate     float64 `json:"win_rate"`
    NewMetric   float64 `json:"new_metric"`  // add this field
}
```

The `json` tag value must exactly match the key in the Python `to_dict()` return value. A mismatch will cause the field to deserialize as the zero value (`0.0`) with no error.

If the Go service forwards metrics to a GCS job result document, ensure any schema validation or downstream struct that reads `MetricsResponse` is also updated to handle the new field.

---

## Step 6: Write Tests

Add tests in two files.

### Unit tests for the calculation function

**File:** `tests/metrics/test_metrics.py`

Add tests directly below the existing win rate tests and before the integration tests section:

```python
# --- New Metric Tests ---

def test_new_metric_positive_returns(positive_returns):
    """Test new metric with all positive returns."""
    result = calculate_new_metric(positive_returns)
    assert isinstance(result, float)
    # Add assertion appropriate to the expected value range

def test_new_metric_negative_returns(all_negative_returns):
    """Test new metric with all negative returns."""
    result = calculate_new_metric(all_negative_returns)
    assert isinstance(result, float)
    # Add assertion for expected behavior with negative returns

def test_new_metric_empty_returns_raises():
    """Test that empty returns raises ValueError."""
    with pytest.raises(ValueError, match="empty"):
        calculate_new_metric([])

def test_new_metric_single_return_raises():
    """Test that a single return value raises ValueError."""
    with pytest.raises(ValueError, match="at least 2"):
        calculate_new_metric([0.01])

def test_new_metric_all_zeros():
    """Test new metric with all-zero returns (edge case for division)."""
    returns = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    # _validate_returns requires at least 2 values; all zeros are valid input
    result = calculate_new_metric(returns)
    assert isinstance(result, float)
    # The result may be 0.0 due to the NaN guard or the exception fallback

def test_new_metric_with_nan_values():
    """Test that NaN values are stripped before calculation."""
    import numpy as np
    returns = [0.01, float('nan'), 0.02, float('nan'), 0.03]
    result = calculate_new_metric(returns)
    assert isinstance(result, float)
    assert not np.isnan(result)

def test_new_metric_exception_returns_zero():
    """calculate_new_metric should return 0.0 on internal exception."""
    from unittest.mock import patch
    with patch("metrics.core.metrics.qs.stats.some_quantstats_function",
               side_effect=Exception("qs error")):
        result = calculate_new_metric([0.01, 0.02, 0.03])
        assert result == 0.0
```

Also update `test_calculate_performance_metrics_basic` to assert the new field is present:

```python
def test_calculate_performance_metrics_basic(mixed_returns):
    """Test basic performance metrics calculation."""
    metrics = calculate_performance_metrics(mixed_returns)

    assert "sharpe_ratio" in metrics
    assert "max_drawdown" in metrics
    assert "cagr" in metrics
    assert "calmar_ratio" in metrics
    assert "win_rate" in metrics
    assert "new_metric" in metrics       # add this assertion
    assert "metadata" in metrics
    assert "interpretation" in metrics
```

### Integration tests via the endpoint

**File:** `tests/metrics/test_endpoints.py`

Add a test block for the new `metric="new_metric"` route. Place it after the existing `test_compute_win_rate_all_losers` test and before the error handling section:

```python
# --- Compute Endpoint: metric="new_metric" ---

def test_compute_new_metric_only(client):
    """Test compute endpoint with metric='new_metric'."""
    payload = {
        "returns": [0.01, -0.02, 0.03, 0.02, -0.01],
        "metric": "new_metric",
        "periods_per_year": 252
    }

    response = client.post("/metrics/v1/compute/", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "new_metric" in data
    assert isinstance(data["new_metric"], float)
    assert len(data) == 1   # Only the requested metric in the response


def test_compute_all_includes_new_metric(client):
    """Test that metric='all' includes new_metric in the response."""
    payload = {
        "returns": [0.01, -0.02, 0.03, 0.02, -0.01],
        "metric": "all"
    }

    response = client.post("/metrics/v1/compute/", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "new_metric" in data
    assert isinstance(data["new_metric"], float)
    # Response count increases by 1 after adding new_metric
    assert len(data) == 6   # was 5 before adding new_metric


def test_compute_performance_includes_new_metric(client):
    """Test that metric='performance' includes new_metric in the response."""
    payload = {
        "returns": [0.01, -0.02, 0.03, 0.02, -0.01],
        "metric": "performance",
        "include_interpretation": False
    }

    response = client.post("/metrics/v1/compute/", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "new_metric" in data


def test_compute_new_metric_empty_returns(client):
    """Test that empty returns returns 400 for new_metric."""
    payload = {
        "returns": [],
        "metric": "new_metric"
    }

    response = client.post("/metrics/v1/compute/", json=payload)
    assert response.status_code == 400
    body = response.json()
    assert "empty" in body.get("message", body.get("detail", "")).lower()


def test_compute_new_metric_single_return(client):
    """Test that a single return value returns 400 for new_metric."""
    payload = {
        "returns": [0.01],
        "metric": "new_metric"
    }

    response = client.post("/metrics/v1/compute/", json=payload)
    assert response.status_code == 400


def test_compute_new_metric_all_zeros(client):
    """Test that all-zero returns does not crash the endpoint."""
    payload = {
        "returns": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        "metric": "new_metric"
    }

    response = client.post("/metrics/v1/compute/", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "new_metric" in data
    assert isinstance(data["new_metric"], float)
```

Note: the `test_compute_all_metrics` test currently asserts `len(data) == 5`. Update it to `len(data) == 6` after adding the new metric.

---

## Running the Tests

Run the full metrics test suite from the repository root:

```bash
pytest tests/metrics/ -v
```

Run only the new metric tests:

```bash
pytest tests/metrics/test_metrics.py -v -k "new_metric"
pytest tests/metrics/test_endpoints.py -v -k "new_metric"
```

Run with coverage to verify the new code paths are exercised:

```bash
pytest tests/metrics/ --cov=metrics --cov-report=term-missing
```

---

## Checklist

Before opening a pull request, verify all of the following:

- [ ] `calculate_new_metric()` function added to `metrics/core/metrics.py`
- [ ] Function calls `_validate_returns()` as the first statement
- [ ] Function has a `try/except` returning `0.0` on failure
- [ ] Function added to `calculate_performance_metrics()` call block
- [ ] Field added to `result` dict in `calculate_performance_metrics()`
- [ ] `"new_metric"` added to `Literal` in `ComputeRequest.metric`
- [ ] `elif` branch added to `compute_metrics()` in `endpoints.py`
- [ ] `new_metric: float` field added to `MetricsResponse` dataclass
- [ ] `from_dict()` updated with `new_metric=data.get("new_metric", 0.0)`
- [ ] `to_dict()` updated with `"new_metric": self.new_metric`
- [ ] `_get_fallback_metrics()` updated with `new_metric=0.0`
- [ ] `MetricsResponse` struct in `datatypes/evaluator.go` updated with json tag
- [ ] Unit tests for the calculation function pass
- [ ] Endpoint tests for `metric="new_metric"` pass
- [ ] `metric="all"` test updated to expect the new field count
- [ ] All existing tests still pass (no regressions)
