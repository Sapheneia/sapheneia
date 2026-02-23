# GAP-01: Connect Metrics Service to Orchestration

**Priority:** HIGH
**Severity:** HIGH
**Category:** Architecture
**Effort:** 3-4 days

---

## Architecture Review

### Reliability
- **Current Risk:** Metrics computation is manual, error-prone
- **Mitigation:** Add circuit breaker pattern for metrics service calls
- **Retry Strategy:** Implement exponential backoff (3 retries, 1s/2s/4s delays)
- **Fallback:** If metrics service unavailable, return partial results with warning flag

### Continuity
- **State Management:** Metrics are stateless (pure function of returns[])
- **Idempotency:** Same input always produces same output - safe to retry
- **Recovery:** No recovery needed - recompute on failure

### Integrity
- **Data Validation:** Validate returns[] is non-empty, contains valid floats
- **Bounds Checking:** Ensure periods_per_year is reasonable (12-365)
- **NaN Handling:** Handle edge cases (all zeros, single return, infinite values)

### Optimization
- **Batching:** Metrics service already computes all 5 metrics in single call
- **Caching:** Consider caching metrics for same run_id (immutable after completion)
- **Async:** Metrics computation can run in parallel with result storage

### Separation (Scalability)
- **Service Boundary:** Metrics service is already separate microservice
- **Interface Contract:** Use existing `/metrics/v1/compute/` endpoint
- **No Shared State:** Stateless computation enables horizontal scaling

---

## Summary

The metrics service exists and is functional but has no code path connecting it to the orchestration layer. After a backtest completes, there's no automatic calculation of Sharpe ratio, max drawdown, or other performance metrics.

## Current State

- `metrics/` service exists at port 12702
- `metrics/main.py` and `metrics/routes/endpoints.py` are functional
- Endpoint: `POST /metrics/v1/compute/` with `metric="all"` for clean response
- **No integration** with `orchestration/service.py`
- Metrics must be computed manually after backtests

## Service Contract Analysis

### Metrics Service Endpoint
```
POST /metrics/v1/compute/
Content-Type: application/json

Request:
{
  "returns": [0.01, -0.02, 0.03, ...],  // Period returns (not prices!)
  "metric": "all",                       // or "performance" for interpretation
  "risk_free_rate": 0.04,               // Annual (default: 0.0)
  "periods_per_year": 252               // Trading days (default: 252)
}

Response:
{
  "sharpe_ratio": 1.85,
  "max_drawdown": -0.12,
  "cagr": 0.18,
  "calmar_ratio": 1.5,
  "win_rate": 0.58
}
```

### Critical: Returns vs Prices
The metrics service expects **returns**, not prices. The orchestrator must compute:
```python
returns = [(prices[i] - prices[i-1]) / prices[i-1] for i in range(1, len(prices))]
```

## Expected Behavior (from design)

```
orchestration → metrics: Pass trading execution results (as returns)
metrics → orchestration: Return evaluation metrics
```

## Acceptance Criteria

- [ ] Create `MetricsClient` class in orchestration layer
- [ ] Implement retry logic with exponential backoff
- [ ] Add circuit breaker for resilience
- [ ] Convert portfolio equity curve to returns before calling metrics
- [ ] Integrate metrics computation into backtest workflow
- [ ] Add unit tests for metrics integration
- [ ] Handle metrics service unavailability gracefully
- [ ] End-to-end flow: forecast → trading → metrics works automatically

## Implementation

### File: `orchestration/clients/metrics_client.py`

```python
"""
Metrics Service Client

Handles communication with the metrics microservice.
Implements retry logic and circuit breaker for reliability.
"""

import httpx
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
import os

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class MetricsResponse:
    """Response from metrics service."""
    sharpe_ratio: float
    max_drawdown: float
    cagr: float
    calmar_ratio: float
    win_rate: float

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MetricsResponse":
        return cls(
            sharpe_ratio=data.get("sharpe_ratio", 0.0),
            max_drawdown=data.get("max_drawdown", 0.0),
            cagr=data.get("cagr", 0.0),
            calmar_ratio=data.get("calmar_ratio", 0.0),
            win_rate=data.get("win_rate", 0.0),
        )


class MetricsClient:
    """
    Client for the metrics microservice.

    Features:
    - Retry with exponential backoff
    - Circuit breaker pattern
    - Timeout handling
    - Graceful degradation
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        self.base_url = base_url or os.getenv(
            "METRICS_SERVICE_URL",
            "http://sapheneia-metrics:8000"
        )
        self.timeout = timeout
        self.max_retries = max_retries

        # Circuit breaker state
        self._circuit_state = CircuitState.CLOSED
        self._failure_count = 0
        self._failure_threshold = 5
        self._recovery_timeout = 30.0  # seconds
        self._last_failure_time: Optional[float] = None

    async def compute_metrics(
        self,
        returns: List[float],
        risk_free_rate: float = 0.0,
        periods_per_year: int = 252,
    ) -> MetricsResponse:
        """
        Compute all performance metrics for a return series.

        Args:
            returns: List of period returns (not prices!)
            risk_free_rate: Annual risk-free rate (e.g., 0.04 for 4%)
            periods_per_year: Trading periods per year (252 for daily)

        Returns:
            MetricsResponse with all computed metrics

        Raises:
            MetricsServiceError: If service unavailable after retries
        """
        # Validate input
        if not returns or len(returns) < 2:
            logger.warning("Insufficient returns data, returning zero metrics")
            return MetricsResponse(
                sharpe_ratio=0.0,
                max_drawdown=0.0,
                cagr=0.0,
                calmar_ratio=0.0,
                win_rate=0.0,
            )

        # Check circuit breaker
        if not self._check_circuit():
            logger.warning("Circuit breaker OPEN, returning cached/default metrics")
            return self._get_fallback_metrics()

        # Prepare request
        payload = {
            "returns": returns,
            "metric": "all",
            "risk_free_rate": risk_free_rate,
            "periods_per_year": periods_per_year,
        }

        # Retry with exponential backoff
        last_error = None
        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        f"{self.base_url}/metrics/v1/compute/",
                        json=payload,
                    )
                    response.raise_for_status()

                    # Success - reset circuit breaker
                    self._on_success()

                    data = response.json()
                    logger.info(f"Metrics computed: sharpe={data.get('sharpe_ratio', 0):.2f}")
                    return MetricsResponse.from_dict(data)

            except httpx.HTTPStatusError as e:
                last_error = e
                logger.warning(f"Metrics service HTTP error (attempt {attempt + 1}): {e}")

            except httpx.RequestError as e:
                last_error = e
                logger.warning(f"Metrics service connection error (attempt {attempt + 1}): {e}")

            # Exponential backoff: 1s, 2s, 4s
            if attempt < self.max_retries - 1:
                import asyncio
                await asyncio.sleep(2 ** attempt)

        # All retries failed
        self._on_failure()
        logger.error(f"Metrics service unavailable after {self.max_retries} attempts")
        return self._get_fallback_metrics()

    def _check_circuit(self) -> bool:
        """Check if circuit breaker allows request."""
        import time

        if self._circuit_state == CircuitState.CLOSED:
            return True

        if self._circuit_state == CircuitState.OPEN:
            # Check if recovery timeout has passed
            if self._last_failure_time and \
               (time.time() - self._last_failure_time) > self._recovery_timeout:
                self._circuit_state = CircuitState.HALF_OPEN
                return True
            return False

        # HALF_OPEN - allow one request to test
        return True

    def _on_success(self):
        """Handle successful request."""
        self._failure_count = 0
        self._circuit_state = CircuitState.CLOSED

    def _on_failure(self):
        """Handle failed request."""
        import time

        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._failure_count >= self._failure_threshold:
            self._circuit_state = CircuitState.OPEN
            logger.warning("Circuit breaker OPENED due to repeated failures")

    def _get_fallback_metrics(self) -> MetricsResponse:
        """Return fallback metrics when service unavailable."""
        return MetricsResponse(
            sharpe_ratio=0.0,
            max_drawdown=0.0,
            cagr=0.0,
            calmar_ratio=0.0,
            win_rate=0.0,
        )


def prices_to_returns(prices: List[float]) -> List[float]:
    """
    Convert price series to return series.

    Args:
        prices: List of prices (oldest first)

    Returns:
        List of period returns
    """
    if len(prices) < 2:
        return []

    returns = []
    for i in range(1, len(prices)):
        if prices[i-1] != 0:
            ret = (prices[i] - prices[i-1]) / prices[i-1]
            returns.append(ret)
        else:
            returns.append(0.0)

    return returns
```

### Integration in Backtest Flow

```python
# In orchestration/backtest.py

async def run_backtest(config: BacktestConfig) -> BacktestResult:
    """Run complete backtest with metrics computation."""

    metrics_client = MetricsClient()

    # ... run backtest loop, collect trades ...

    # Compute equity curve from trades
    equity_curve = compute_equity_curve(trades, config.initial_capital)

    # Convert to returns for metrics
    returns = prices_to_returns(equity_curve)

    # Compute metrics (handles failures gracefully)
    metrics = await metrics_client.compute_metrics(
        returns=returns,
        risk_free_rate=config.risk_free_rate,
        periods_per_year=252,  # Daily trading
    )

    return BacktestResult(
        trades=trades,
        equity_curve=equity_curve,
        metrics=metrics,
    )
```

## Docker Compose Update

Uncomment metrics service in `docker-compose.yml`:

```yaml
sapheneia-metrics:
  build:
    context: .
    dockerfile: Dockerfile.metrics
  container_name: sapheneia-metrics
  ports:
    - "${METRICS_PORT:-12702}:8000"
  environment:
    - PYTHONPATH=/app
  networks:
    - aleutian-shared
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
    interval: 30s
    timeout: 10s
    retries: 3
```

## Environment Variables

Add to `.env.template`:
```bash
# Metrics Service
METRICS_SERVICE_URL=http://sapheneia-metrics:8000
METRICS_PORT=12702
```

## Dependencies

- GAP-02 (Trading feedback loop) should be completed first or in parallel
- GAP-05 (Python tests) for test coverage

## Test Cases

1. **Happy path**: Returns array → all metrics computed
2. **Empty returns**: Handle gracefully with zero metrics
3. **Service unavailable**: Circuit breaker opens, returns fallback
4. **Timeout**: Retry with backoff, eventually fallback
5. **Invalid returns**: NaN/Inf handling

## Related Files

- `orchestration/service.py`
- `metrics/main.py`
- `metrics/routes/endpoints.py`
- `metrics/core/metrics.py`
- `docker-compose.yml`
- New: `orchestration/clients/metrics_client.py`
