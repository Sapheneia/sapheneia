# GAP-02: Complete Trading Feedback Loop

**Priority:** HIGH
**Severity:** MEDIUM
**Category:** Architecture
**Effort:** 2-3 days

---

## Architecture Review

### Reliability
- **Current Risk:** Trading state can be lost mid-backtest
- **Mitigation:** Implement checkpointing every N iterations
- **Retry Strategy:** Trading calls should be idempotent (same input → same output)
- **Failure Mode:** If trading service fails, log and continue with HOLD action

### Continuity
- **State Management:** Portfolio state must persist across iterations
- **Checkpointing:** Save state to disk every 10 iterations for recovery
- **Resume Capability:** Support resuming backtest from last checkpoint
- **Atomic Updates:** Portfolio update should be transactional (all or nothing)

### Integrity
- **Portfolio Validation:** Validate position ≥ 0, cash ≥ 0 after each trade
- **Trade Reconciliation:** Verify position_after matches expected calculation
- **Audit Trail:** Log every trade with timestamp, prices, and portfolio state
- **Consistency Check:** Ensure cash + position_value = total_value

### Optimization
- **Batch Dates:** Process evaluation dates in batches for better throughput
- **Parallel Data Fetch:** Prefetch data for next N dates while processing current
- **Connection Pooling:** Reuse HTTP connections across trading calls
- **Memory Management:** Stream results instead of collecting all in memory

### Separation (Scalability)
- **Trading Client:** Separate client class with clear interface
- **Portfolio Manager:** Separate class for portfolio state management
- **Event Sourcing:** Consider event log for complete trade history
- **Horizontal Scaling:** Backtest loop is inherently sequential, but can run multiple backtests in parallel

---

## Summary

Trading integration is currently one-way. The orchestration layer can send forecasts to the trading service but there's no feedback loop for iterative portfolio state management during backtests.

## Current State

- Trading service exists at port 12132
- Endpoint: `POST /trading/execute`
- Supports three strategies: threshold, return, quantile
- Go orchestrator can call trading via HTTP
- **No feedback loop** in Python orchestration layer
- No iterative portfolio state management in Python
- `orchestration/service.py` only handles forecasts, not trading

## Service Contract Analysis

### Trading Service Request
```json
POST /trading/execute
Authorization: Bearer {TRADING_API_KEY}

{
  "strategy_type": "threshold",
  "forecast_price": 452.1,
  "current_price": 450.0,
  "current_position": 100.0,
  "available_cash": 50000.0,
  "initial_capital": 100000.0,
  "threshold_type": "absolute",
  "threshold_value": 2.0,
  "execution_size": 10.0
}
```

### Trading Service Response
```json
{
  "action": "buy",
  "size": 10.0,
  "value": 4521.0,
  "reason": "Forecast 452.10 > Price 450.00, magnitude 2.1000 > threshold 2.0000",
  "available_cash": 45479.0,
  "position_after": 110.0,
  "stopped": false
}
```

## Expected Behavior (from design)

```
loop Trading Orchestration:
    orchestration → data: Query historical data with temporal bounds
    data → orchestration: Return bounded data
    orchestration → forecast: Pass data, get predictions
    forecast → orchestration: Return predictions
    orchestration → trading: Pass forecast + portfolio state
    trading → orchestration: Return trade signal + updated portfolio
    orchestration: Update portfolio state
end loop
orchestration → metrics: Compute final metrics
```

## Acceptance Criteria

- [ ] Create `TradingClient` class for trading service communication
- [ ] Create `PortfolioManager` class for state management
- [ ] Create `orchestration/backtest.py` with full loop implementation
- [ ] Implement checkpointing for recovery
- [ ] Portfolio state persists across iterations
- [ ] Trading signals (BUY/SELL/HOLD) properly handled
- [ ] Audit trail for all trades
- [ ] Unit tests for trading integration and portfolio management

## Implementation

### File: `orchestration/clients/trading_client.py`

```python
"""
Trading Service Client

Handles communication with the trading microservice.
"""

import httpx
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum
import os

logger = logging.getLogger(__name__)


class TradeAction(str, Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class StrategyType(str, Enum):
    THRESHOLD = "threshold"
    RETURN = "return"
    QUANTILE = "quantile"


@dataclass
class TradeResult:
    """Result from trading service."""
    action: TradeAction
    size: float
    value: float
    reason: str
    available_cash: float
    position_after: float
    stopped: bool

    # Metadata for audit
    forecast_price: float = 0.0
    current_price: float = 0.0
    timestamp: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any], metadata: Dict[str, Any] = None) -> "TradeResult":
        metadata = metadata or {}
        return cls(
            action=TradeAction(data.get("action", "hold")),
            size=data.get("size", 0.0),
            value=data.get("value", 0.0),
            reason=data.get("reason", ""),
            available_cash=data.get("available_cash", 0.0),
            position_after=data.get("position_after", 0.0),
            stopped=data.get("stopped", False),
            forecast_price=metadata.get("forecast_price", 0.0),
            current_price=metadata.get("current_price", 0.0),
            timestamp=metadata.get("timestamp", ""),
        )

    @classmethod
    def hold(cls, portfolio: "PortfolioState", reason: str = "Default hold") -> "TradeResult":
        """Create a HOLD result."""
        return cls(
            action=TradeAction.HOLD,
            size=0.0,
            value=0.0,
            reason=reason,
            available_cash=portfolio.cash,
            position_after=portfolio.position,
            stopped=False,
        )


@dataclass
class PortfolioState:
    """Current portfolio state."""
    position: float  # Number of shares/units held
    cash: float      # Available cash
    initial_capital: float

    @property
    def total_value(self) -> float:
        """Total portfolio value (requires current price)."""
        return self.cash  # Note: position value needs price

    def calculate_total_value(self, current_price: float) -> float:
        """Calculate total portfolio value at given price."""
        return self.cash + (self.position * current_price)

    def to_dict(self) -> Dict[str, float]:
        return {
            "position": self.position,
            "cash": self.cash,
            "initial_capital": self.initial_capital,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PortfolioState":
        return cls(
            position=data.get("position", 0.0),
            cash=data.get("cash", 0.0),
            initial_capital=data.get("initial_capital", 0.0),
        )


class TradingClient:
    """
    Client for the trading microservice.

    Features:
    - Connection pooling
    - Timeout handling
    - Graceful degradation (return HOLD on failure)
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = 30.0,
    ):
        self.base_url = base_url or os.getenv(
            "TRADING_SERVICE_URL",
            "http://sapheneia-trading:9000"
        )
        self.api_key = api_key or os.getenv("TRADING_API_KEY", "")
        self.timeout = timeout

    async def execute_signal(
        self,
        forecast_price: float,
        current_price: float,
        portfolio: PortfolioState,
        strategy_type: StrategyType = StrategyType.THRESHOLD,
        strategy_params: Optional[Dict[str, Any]] = None,
        timestamp: str = "",
    ) -> TradeResult:
        """
        Execute trading strategy and return trade decision.

        Args:
            forecast_price: Predicted price from model
            current_price: Current market price
            portfolio: Current portfolio state
            strategy_type: Which strategy to use
            strategy_params: Strategy-specific parameters
            timestamp: Evaluation timestamp for audit

        Returns:
            TradeResult with action and updated state

        Note:
            On failure, returns HOLD to avoid disrupting backtest
        """
        strategy_params = strategy_params or {}

        # Build request payload
        payload = {
            "strategy_type": strategy_type.value,
            "forecast_price": forecast_price,
            "current_price": current_price,
            "current_position": portfolio.position,
            "available_cash": portfolio.cash,
            "initial_capital": portfolio.initial_capital,
            **strategy_params,
        }

        # Add default strategy params if not provided
        if strategy_type == StrategyType.THRESHOLD:
            payload.setdefault("threshold_type", "absolute")
            payload.setdefault("threshold_value", 2.0)
            payload.setdefault("execution_size", 10.0)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                headers = {"Content-Type": "application/json"}
                if self.api_key:
                    headers["Authorization"] = f"Bearer {self.api_key}"

                response = await client.post(
                    f"{self.base_url}/trading/execute",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()

                data = response.json()
                result = TradeResult.from_dict(
                    data,
                    metadata={
                        "forecast_price": forecast_price,
                        "current_price": current_price,
                        "timestamp": timestamp,
                    }
                )

                logger.info(
                    f"Trade executed: {result.action.value} "
                    f"size={result.size:.2f} value=${result.value:.2f}"
                )

                return result

        except httpx.HTTPStatusError as e:
            logger.error(f"Trading service HTTP error: {e}")
            return TradeResult.hold(portfolio, f"Trading service error: {e}")

        except httpx.RequestError as e:
            logger.error(f"Trading service connection error: {e}")
            return TradeResult.hold(portfolio, f"Trading service unavailable: {e}")

        except Exception as e:
            logger.exception(f"Unexpected trading error: {e}")
            return TradeResult.hold(portfolio, f"Unexpected error: {e}")


class PortfolioManager:
    """
    Manages portfolio state with checkpointing and audit trail.
    """

    def __init__(self, initial_capital: float):
        self.portfolio = PortfolioState(
            position=0.0,
            cash=initial_capital,
            initial_capital=initial_capital,
        )
        self.trades: list[TradeResult] = []
        self.equity_curve: list[float] = [initial_capital]
        self._checkpoint_interval = 10

    def apply_trade(self, trade: TradeResult, current_price: float):
        """
        Apply trade result to portfolio state.

        Args:
            trade: Result from trading service
            current_price: Price at which trade executed
        """
        # Update portfolio state
        self.portfolio.position = trade.position_after
        self.portfolio.cash = trade.available_cash

        # Record trade
        self.trades.append(trade)

        # Update equity curve
        total_value = self.portfolio.calculate_total_value(current_price)
        self.equity_curve.append(total_value)

        # Validate portfolio integrity
        self._validate_portfolio(current_price)

    def _validate_portfolio(self, current_price: float):
        """Validate portfolio state is consistent."""
        assert self.portfolio.position >= 0, "Position cannot be negative (long-only)"
        assert self.portfolio.cash >= 0, "Cash cannot be negative"

        # Verify total value is reasonable
        total_value = self.portfolio.calculate_total_value(current_price)
        assert total_value > 0, "Total value must be positive"

    def get_checkpoint(self) -> Dict[str, Any]:
        """Get checkpoint data for recovery."""
        return {
            "portfolio": self.portfolio.to_dict(),
            "trades_count": len(self.trades),
            "equity_curve_length": len(self.equity_curve),
            "last_equity": self.equity_curve[-1] if self.equity_curve else 0,
        }

    def should_checkpoint(self) -> bool:
        """Check if we should save a checkpoint."""
        return len(self.trades) % self._checkpoint_interval == 0
```

### File: `orchestration/backtest.py`

```python
"""
Backtest Orchestrator

Implements the complete backtest loop:
data → forecast → trading → state update → metrics
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field

from .clients.trading_client import (
    TradingClient,
    PortfolioManager,
    TradeResult,
    StrategyType,
)
from .clients.metrics_client import MetricsClient, MetricsResponse, prices_to_returns
from .service import InferenceService
from .schema import InferenceRequest, ContextData, HorizonSpec, Period, DataSource

logger = logging.getLogger(__name__)


@dataclass
class BacktestConfig:
    """Configuration for backtest run."""
    ticker: str
    model: str
    start_date: str  # YYYY-MM-DD
    end_date: str    # YYYY-MM-DD
    initial_capital: float = 100000.0
    context_size: int = 90  # Days of context
    horizon_size: int = 10  # Days to forecast
    strategy_type: StrategyType = StrategyType.THRESHOLD
    strategy_params: Dict[str, Any] = field(default_factory=dict)
    risk_free_rate: float = 0.0
    step_days: int = 1  # Days between evaluations


@dataclass
class BacktestResult:
    """Result of a complete backtest."""
    config: BacktestConfig
    trades: List[TradeResult]
    equity_curve: List[float]
    metrics: MetricsResponse
    evaluation_dates: List[str]
    run_id: str = ""

    @property
    def total_return(self) -> float:
        """Calculate total return."""
        if len(self.equity_curve) < 2:
            return 0.0
        return (self.equity_curve[-1] - self.equity_curve[0]) / self.equity_curve[0]


async def run_backtest(
    config: BacktestConfig,
    data_provider,  # Callable to get historical data
    run_id: Optional[str] = None,
) -> BacktestResult:
    """
    Run complete backtest with trading feedback loop.

    Args:
        config: Backtest configuration
        data_provider: Async function to fetch historical data
        run_id: Optional run identifier

    Returns:
        BacktestResult with trades, equity curve, and metrics
    """
    import uuid
    run_id = run_id or str(uuid.uuid4())[:8]

    logger.info(f"Starting backtest run_id={run_id}")
    logger.info(f"  Ticker: {config.ticker}")
    logger.info(f"  Model: {config.model}")
    logger.info(f"  Period: {config.start_date} to {config.end_date}")
    logger.info(f"  Capital: ${config.initial_capital:,.2f}")

    # Initialize services
    inference_service = InferenceService()
    trading_client = TradingClient()
    metrics_client = MetricsClient()
    portfolio_manager = PortfolioManager(config.initial_capital)

    # Generate evaluation dates
    evaluation_dates = generate_evaluation_dates(
        config.start_date,
        config.end_date,
        config.step_days,
    )

    logger.info(f"  Evaluation dates: {len(evaluation_dates)}")

    # Main backtest loop
    for i, eval_date in enumerate(evaluation_dates):
        logger.info(f"[{run_id}] Evaluating {eval_date} ({i+1}/{len(evaluation_dates)})")

        try:
            # PHASE 1: Get historical data (with temporal bound)
            context_data = await data_provider(
                ticker=config.ticker,
                end_date=eval_date,
                days=config.context_size,
            )

            if not context_data or len(context_data) < 10:
                logger.warning(f"Insufficient data for {eval_date}, skipping")
                continue

            current_price = context_data[-1]

            # PHASE 2: Run forecast
            inference_request = InferenceRequest(
                ticker=config.ticker,
                model=config.model,
                context=ContextData(
                    values=context_data,
                    period=Period.DAY_1,
                    source=DataSource.INFLUXDB,
                    start_date=calculate_start_date(eval_date, len(context_data)),
                    end_date=eval_date,
                ),
                horizon=HorizonSpec(
                    length=config.horizon_size,
                    period=Period.DAY_1,
                ),
            )

            inference_response = await inference_service.predict(inference_request)
            forecast_values = inference_response.forecast.values

            # Use mean of forecast as expected price
            forecast_price = sum(forecast_values) / len(forecast_values)

            # PHASE 3: Execute trading decision
            trade_result = await trading_client.execute_signal(
                forecast_price=forecast_price,
                current_price=current_price,
                portfolio=portfolio_manager.portfolio,
                strategy_type=config.strategy_type,
                strategy_params=config.strategy_params,
                timestamp=eval_date,
            )

            # PHASE 4: Update portfolio state
            portfolio_manager.apply_trade(trade_result, current_price)

            # Checkpoint if needed
            if portfolio_manager.should_checkpoint():
                checkpoint = portfolio_manager.get_checkpoint()
                logger.debug(f"Checkpoint: {checkpoint}")

        except Exception as e:
            logger.error(f"Error on {eval_date}: {e}")
            # Continue with next date - don't fail entire backtest
            continue

    # PHASE 5: Compute metrics
    returns = prices_to_returns(portfolio_manager.equity_curve)
    metrics = await metrics_client.compute_metrics(
        returns=returns,
        risk_free_rate=config.risk_free_rate,
        periods_per_year=252,
    )

    result = BacktestResult(
        config=config,
        trades=portfolio_manager.trades,
        equity_curve=portfolio_manager.equity_curve,
        metrics=metrics,
        evaluation_dates=evaluation_dates,
        run_id=run_id,
    )

    logger.info(f"Backtest complete run_id={run_id}")
    logger.info(f"  Total trades: {len(result.trades)}")
    logger.info(f"  Total return: {result.total_return:.2%}")
    logger.info(f"  Sharpe ratio: {metrics.sharpe_ratio:.2f}")
    logger.info(f"  Max drawdown: {metrics.max_drawdown:.2%}")

    return result


def generate_evaluation_dates(
    start_date: str,
    end_date: str,
    step_days: int = 1,
) -> List[str]:
    """Generate list of evaluation dates."""
    from datetime import datetime, timedelta

    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    dates = []
    current = start
    while current <= end:
        dates.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=step_days)

    return dates


def calculate_start_date(end_date: str, days: int) -> str:
    """Calculate start date given end date and number of days."""
    from datetime import datetime, timedelta

    end = datetime.strptime(end_date, "%Y-%m-%d")
    start = end - timedelta(days=days)
    return start.strftime("%Y-%m-%d")
```

## Environment Variables

Add to `.env.template`:
```bash
# Trading Service
TRADING_SERVICE_URL=http://sapheneia-trading:9000
TRADING_API_KEY=your_secure_trading_key_min_32_chars
```

## Dependencies

- GAP-01 (Metrics integration) for complete flow
- GAP-05 (Python tests) for test coverage

## Test Cases

1. **Happy path**: Full backtest loop completes successfully
2. **Trading service failure**: Returns HOLD, continues backtest
3. **Insufficient data**: Skips evaluation date, continues
4. **Portfolio validation**: Catches invalid states
5. **Checkpointing**: Saves state periodically
6. **Resume from checkpoint**: Recovery after failure

## Related Files

- `orchestration/service.py`
- `trading/main.py`
- `trading/routes/endpoints.py`
- `trading/services/trading.py`
- New: `orchestration/clients/trading_client.py`
- New: `orchestration/backtest.py`
