"""
Metrics Service Client

Handles communication with the metrics microservice.
Implements retry logic and circuit breaker for reliability.
"""

import asyncio
import httpx
import logging
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
import os

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states for metrics service resilience."""
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
        """Create MetricsResponse from compute endpoint response dict."""
        return cls(
            sharpe_ratio=data.get("sharpe_ratio", 0.0),
            max_drawdown=data.get("max_drawdown", 0.0),
            cagr=data.get("cagr", 0.0),
            calmar_ratio=data.get("calmar_ratio", 0.0),
            win_rate=data.get("win_rate", 0.0),
        )

    def to_dict(self) -> Dict[str, float]:
        """Serialize metrics to dict for storage or transmission."""
        return {
            "sharpe_ratio": self.sharpe_ratio,
            "max_drawdown": self.max_drawdown,
            "cagr": self.cagr,
            "calmar_ratio": self.calmar_ratio,
            "win_rate": self.win_rate,
        }


class MetricsServiceError(Exception):
    """Error communicating with metrics service."""
    pass


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

    def _build_headers(self, request_id: Optional[str] = None) -> Dict[str, str]:
        """Build HTTP headers with optional request ID."""
        headers = {"Content-Type": "application/json"}
        if request_id:
            headers["X-Request-ID"] = request_id
        return headers

    async def compute_metrics(
        self,
        returns: List[float],
        risk_free_rate: float = 0.0,
        periods_per_year: int = 252,
        request_id: Optional[str] = None,
    ) -> MetricsResponse:
        """
        Compute all performance metrics for a return series.

        Args:
            returns: List of period returns (not prices!)
            risk_free_rate: Annual risk-free rate (e.g., 0.04 for 4%)
            periods_per_year: Trading periods per year (252 for daily)
            request_id: Optional request ID for distributed tracing

        Returns:
            MetricsResponse with all computed metrics

        Note:
            Returns fallback metrics on failure instead of raising
        """
        # Validate input
        if not returns or len(returns) < 2:
            logger.warning("Insufficient returns data, returning zero metrics")
            return self._get_fallback_metrics()

        # Filter out NaN/Inf values
        clean_returns = [r for r in returns if r == r and abs(r) != float('inf')]
        if len(clean_returns) < 2:
            logger.warning("Too many invalid returns, returning zero metrics")
            return self._get_fallback_metrics()

        # Check circuit breaker
        if not self._check_circuit():
            logger.warning("Circuit breaker OPEN, returning fallback metrics")
            return self._get_fallback_metrics()

        # Prepare request
        payload = {
            "returns": clean_returns,
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
                        headers=self._build_headers(request_id),
                    )
                    response.raise_for_status()

                    # Success - reset circuit breaker
                    self._on_success()

                    data = response.json()
                    result = MetricsResponse.from_dict(data)
                    logger.info(
                        f"Metrics computed: sharpe={result.sharpe_ratio:.2f}, "
                        f"max_dd={result.max_drawdown:.2%}"
                    )
                    return result

            except httpx.HTTPStatusError as e:
                last_error = e
                logger.warning(f"Metrics service HTTP error (attempt {attempt + 1}): {e}")

            except httpx.RequestError as e:
                last_error = e
                logger.warning(f"Metrics service connection error (attempt {attempt + 1}): {e}")

            except Exception as e:
                last_error = e
                logger.warning(f"Unexpected error (attempt {attempt + 1}): {e}")

            # Exponential backoff: 1s, 2s, 4s
            if attempt < self.max_retries - 1:
                await asyncio.sleep(2 ** attempt)

        # All retries failed
        self._on_failure()
        logger.error(f"Metrics service unavailable after {self.max_retries} attempts: {last_error}")
        return self._get_fallback_metrics()

    def _check_circuit(self) -> bool:
        """Check if circuit breaker allows request."""
        if self._circuit_state == CircuitState.CLOSED:
            return True

        if self._circuit_state == CircuitState.OPEN:
            # Check if recovery timeout has passed
            if self._last_failure_time and \
               (time.time() - self._last_failure_time) > self._recovery_timeout:
                self._circuit_state = CircuitState.HALF_OPEN
                logger.info("Circuit breaker transitioning to HALF_OPEN")
                return True
            return False

        # HALF_OPEN - allow one request to test
        return True

    def _on_success(self):
        """Handle successful request."""
        self._failure_count = 0
        if self._circuit_state != CircuitState.CLOSED:
            logger.info("Circuit breaker CLOSED after successful request")
        self._circuit_state = CircuitState.CLOSED

    def _on_failure(self):
        """Handle failed request."""
        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._failure_count >= self._failure_threshold:
            if self._circuit_state != CircuitState.OPEN:
                logger.warning(
                    f"Circuit breaker OPENED after {self._failure_count} failures"
                )
            self._circuit_state = CircuitState.OPEN

    def _get_fallback_metrics(self) -> MetricsResponse:
        """Return fallback metrics when service unavailable."""
        return MetricsResponse(
            sharpe_ratio=0.0,
            max_drawdown=0.0,
            cagr=0.0,
            calmar_ratio=0.0,
            win_rate=0.0,
        )

    @property
    def circuit_state(self) -> CircuitState:
        """Get current circuit breaker state."""
        return self._circuit_state


def prices_to_returns(prices: List[float]) -> List[float]:
    """
    Convert price series to return series.

    Args:
        prices: List of prices (oldest first)

    Returns:
        List of period returns

    Note:
        Returns are capped to [-1.0, 10.0] to prevent Inf/NaN values
        from breaking downstream calculations (e.g., Sharpe ratio).

        - Minimum: -1.0 (-100%, total loss) - can't lose more than invested
        - Maximum: 10.0 (+1000%) - prevents extreme outliers from dominating

        For highly volatile assets (crypto, penny stocks) where >1000%
        single-period gains are possible, consider adjusting the cap.
    """
    if len(prices) < 2:
        return []

    returns = []
    for i in range(1, len(prices)):
        if prices[i-1] != 0 and prices[i-1] == prices[i-1]:  # Check for NaN
            ret = (prices[i] - prices[i-1]) / prices[i-1]
            # Cap extreme returns to avoid Inf
            ret = max(min(ret, 10.0), -1.0)
            returns.append(ret)
        else:
            returns.append(0.0)

    return returns
