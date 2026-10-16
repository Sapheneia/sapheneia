"""In-memory portfolio state for one backtest run."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Portfolio:
    cash: float
    position: float
    initial_capital: float

    def equity(self, price: float) -> float:
        return self.cash + self.position * price

    def apply_trade(self, action: str, size: float, value: float) -> None:
        action = (action or "").upper()
        if action == "BUY":
            self.cash -= value
            self.position += size
        elif action == "SELL":
            self.cash += value
            self.position -= size
        # HOLD or unknown: no-op
