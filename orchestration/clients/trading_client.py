"""
Trading Service Client

Handles communication with the trading microservice.
"""

import httpx
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum
import os

logger = logging.getLogger(__name__)


class TradeAction(str, Enum):
    """Trade action decision from the trading service."""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class StrategyType(str, Enum):
    """Available trading strategy types for signal generation."""
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
    def from_dict(cls, data: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None) -> "TradeResult":
        """Create TradeResult from trading service response dict and optional metadata."""
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

    def to_dict(self) -> Dict[str, Any]:
        """Serialize trade result to dict for storage or transmission."""
        return {
            "action": self.action.value,
            "size": self.size,
            "value": self.value,
            "reason": self.reason,
            "available_cash": self.available_cash,
            "position_after": self.position_after,
            "stopped": self.stopped,
            "forecast_price": self.forecast_price,
            "current_price": self.current_price,
            "timestamp": self.timestamp,
        }


@dataclass
class PortfolioState:
    """Current portfolio state."""
    position: float  # Number of shares/units held
    cash: float      # Available cash
    initial_capital: float

    def calculate_total_value(self, current_price: float) -> float:
        """Calculate total portfolio value at given price."""
        return self.cash + (self.position * current_price)

    def to_dict(self) -> Dict[str, float]:
        """Serialize portfolio state to dict for checkpointing."""
        return {
            "position": self.position,
            "cash": self.cash,
            "initial_capital": self.initial_capital,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PortfolioState":
        """Restore portfolio state from checkpoint dict."""
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

    def _build_headers(self, request_id: Optional[str] = None) -> Dict[str, str]:
        """Build HTTP headers with optional request ID."""
        headers = {"Content-Type": "application/json"}
        if request_id:
            headers["X-Request-ID"] = request_id
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def execute_signal(
        self,
        forecast_price: float,
        current_price: float,
        portfolio: PortfolioState,
        strategy_type: StrategyType = StrategyType.THRESHOLD,
        strategy_params: Optional[Dict[str, Any]] = None,
        timestamp: str = "",
        request_id: Optional[str] = None,
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
            request_id: Optional request ID for distributed tracing

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
                response = await client.post(
                    f"{self.base_url}/trading/execute",
                    json=payload,
                    headers=self._build_headers(request_id),
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

    def __init__(self, initial_capital: float, checkpoint_interval: int = 10):
        """Initialize portfolio manager with starting capital and checkpoint frequency."""
        self.portfolio = PortfolioState(
            position=0.0,
            cash=initial_capital,
            initial_capital=initial_capital,
        )
        self.trades: List[TradeResult] = []
        self.equity_curve: List[float] = [initial_capital]
        self._checkpoint_interval = checkpoint_interval
        self._iteration_count = 0

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
        self._iteration_count += 1

        # Update equity curve
        total_value = self.portfolio.calculate_total_value(current_price)
        self.equity_curve.append(total_value)

        # Validate portfolio integrity
        self._validate_portfolio(current_price)

    def _validate_portfolio(self, current_price: float):
        """
        Validate portfolio state is consistent.

        Uses warnings (not assertions) for production resilience.
        Invalid states are logged but don't crash the backtest, allowing
        partial results to be collected even when issues occur.

        This is intentional: assertions can be disabled with -O flag,
        and crashing mid-backtest loses all computed results.
        """
        if self.portfolio.position < 0:
            logger.warning(f"Negative position detected: {self.portfolio.position}")

        if self.portfolio.cash < 0:
            logger.warning(f"Negative cash detected: {self.portfolio.cash}")

        # Verify total value is reasonable
        total_value = self.portfolio.calculate_total_value(current_price)
        if total_value <= 0:
            logger.warning(f"Total value not positive: {total_value}")

    def get_checkpoint(self) -> Dict[str, Any]:
        """Get checkpoint data for recovery."""
        return {
            "portfolio": self.portfolio.to_dict(),
            "trades_count": len(self.trades),
            "equity_curve_length": len(self.equity_curve),
            "last_equity": self.equity_curve[-1] if self.equity_curve else 0,
            "iteration": self._iteration_count,
        }

    def should_checkpoint(self) -> bool:
        """Check if we should save a checkpoint."""
        return self._iteration_count > 0 and \
               self._iteration_count % self._checkpoint_interval == 0

    def restore_from_checkpoint(self, checkpoint: Dict[str, Any]):
        """Restore state from checkpoint."""
        if "portfolio" in checkpoint:
            self.portfolio = PortfolioState.from_dict(checkpoint["portfolio"])
        if "last_equity" in checkpoint:
            self.equity_curve = [checkpoint["last_equity"]]
        self._iteration_count = checkpoint.get("iteration", 0)
        logger.info(f"Restored from checkpoint at iteration {self._iteration_count}")

    def get_trade_summary(self) -> Dict[str, Any]:
        """Get summary of all trades."""
        if not self.trades:
            return {"total_trades": 0}

        buys = [t for t in self.trades if t.action == TradeAction.BUY]
        sells = [t for t in self.trades if t.action == TradeAction.SELL]
        holds = [t for t in self.trades if t.action == TradeAction.HOLD]

        return {
            "total_trades": len(self.trades),
            "buys": len(buys),
            "sells": len(sells),
            "holds": len(holds),
            "total_buy_value": sum(t.value for t in buys),
            "total_sell_value": sum(t.value for t in sells),
        }
