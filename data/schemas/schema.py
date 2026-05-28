"""Request and response schemas for the data service."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator


class FetchRequest(BaseModel):
    tickers: list[str] = Field(min_length=1, max_length=100)
    start: date
    end: date
    interval: str = Field(default="1d")

    @field_validator("interval")
    @classmethod
    def _check_interval(cls, v: str) -> str:
        allowed = {"1m", "5m", "15m", "30m", "1h", "1d", "1wk", "1mo"}
        if v not in allowed:
            raise ValueError(f"interval must be one of {sorted(allowed)}")
        return v

    @field_validator("end")
    @classmethod
    def _end_after_start(cls, v: date, info) -> date:
        start = info.data.get("start")
        if start is not None and v < start:
            raise ValueError("end must be on or after start")
        return v


class PriceBar(BaseModel):
    time: datetime
    ticker: str
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    adj_close: float | None = None
    volume: int | None = None


class FetchResponse(BaseModel):
    tickers: list[str]
    interval: str
    bars: list[PriceBar]


class PricesQueryResponse(BaseModel):
    ticker: str
    interval: str
    bars: list[PriceBar]
