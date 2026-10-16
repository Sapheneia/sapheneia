"""
Strategy configuration models.

Pydantic models for validating strategy YAML config files.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class StrategyConfig:
    """Parsed and validated strategy configuration."""

    # Core identifiers
    strategy_id: str
    version: str

    # Evaluation parameters
    ticker: str
    start_date: str  # YYYY-MM-DD format
    end_date: str  # YYYY-MM-DD format

    # Forecast parameters
    model: str
    context_size: int = 90
    horizon_size: int = 10

    # Trading parameters
    initial_capital: float = 100000.0
    strategy_type: str = "threshold"
    strategy_params: dict[str, Any] = field(default_factory=dict)

    # Optional metadata
    description: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StrategyConfig":
        """
        Create StrategyConfig from a dictionary (parsed YAML).

        Raises:
            ValueError: If required fields are missing or invalid
        """
        # Extract metadata
        metadata = data.get("metadata", {})
        strategy_id = metadata.get("id")
        if not strategy_id:
            raise ValueError("metadata.id is required")
        version = metadata.get("version", "1.0.0")
        description = metadata.get("description", "")

        # Extract evaluation
        evaluation = data.get("evaluation", {})
        ticker = evaluation.get("ticker")
        if not ticker:
            raise ValueError("evaluation.ticker is required")

        start_date = evaluation.get("start_date")
        if not start_date:
            raise ValueError("evaluation.start_date is required")
        start_date = cls._normalize_date(start_date)

        end_date = evaluation.get("end_date")
        if not end_date:
            raise ValueError("evaluation.end_date is required")
        end_date = cls._normalize_date(end_date)

        # Validate date range
        if start_date >= end_date:
            raise ValueError(f"start_date ({start_date}) must be before end_date ({end_date})")

        # Extract forecast
        forecast = data.get("forecast", {})
        model = forecast.get("model")
        if not model:
            raise ValueError("forecast.model is required")
        context_size = forecast.get("context_size", 90)
        horizon_size = forecast.get("horizon_size", 10)

        # Validate sizes
        if context_size <= 0:
            raise ValueError("forecast.context_size must be positive")
        if horizon_size <= 0:
            raise ValueError("forecast.horizon_size must be positive")

        # Extract trading
        trading = data.get("trading", {})
        initial_capital = trading.get("initial_capital", 100000.0)
        strategy_type = trading.get("strategy_type", "threshold")
        strategy_params = trading.get("params", {})

        # Validate capital
        if initial_capital <= 0:
            raise ValueError("trading.initial_capital must be positive")

        # Validate strategy type
        valid_strategies = ["threshold", "return", "quantile"]
        if strategy_type.lower() not in valid_strategies:
            raise ValueError(f"trading.strategy_type must be one of: {valid_strategies}")

        return cls(
            strategy_id=strategy_id,
            version=version,
            description=description,
            ticker=ticker,
            start_date=start_date,
            end_date=end_date,
            model=model,
            context_size=context_size,
            horizon_size=horizon_size,
            initial_capital=initial_capital,
            strategy_type=strategy_type.lower(),
            strategy_params=strategy_params,
        )

    @staticmethod
    def _normalize_date(date_str: str) -> str:
        """
        Normalize date string to YYYY-MM-DD format.

        Accepts:
        - YYYY-MM-DD
        - YYYYMMDD
        """
        date_str = str(date_str).strip()

        # Try YYYYMMDD format
        if len(date_str) == 8 and date_str.isdigit():
            try:
                dt = datetime.strptime(date_str, "%Y%m%d")
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                pass

        # Try YYYY-MM-DD format
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            raise ValueError(
                f"Invalid date format: {date_str}. Expected YYYY-MM-DD or YYYYMMDD"
            ) from None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "metadata": {
                "id": self.strategy_id,
                "version": self.version,
                "description": self.description,
            },
            "evaluation": {
                "ticker": self.ticker,
                "start_date": self.start_date,
                "end_date": self.end_date,
            },
            "forecast": {
                "model": self.model,
                "context_size": self.context_size,
                "horizon_size": self.horizon_size,
            },
            "trading": {
                "initial_capital": self.initial_capital,
                "strategy_type": self.strategy_type,
                "params": self.strategy_params,
            },
        }
