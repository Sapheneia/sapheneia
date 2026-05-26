from typing import List, Optional, Dict
from pydantic import BaseModel, Field


class DataFetchRequest(BaseModel):
    names: List[str] = Field(default_factory=list)
    start_date: str = ""
    interval: str = ""


class DataFetchResponse(BaseModel):
    status: str
    message: str
    details: Dict[str, str]


class DataQueryRequest(BaseModel):
    ticker: str = ""
    days: int = 0
    end_date: str = ""


class DataPoint(BaseModel):
    time: str = ""
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: int = 0
    adj_close: float = 0.0


class DataQueryResponse(BaseModel):
    ticker: str
    data: List[DataPoint]
    count: int


class SimulationResultPoint(BaseModel):
    date: str
    forecast: float
    actual: float
    signal: str
    position: float
    cash: float
    portfolio_value: float


class SimulationMetrics(BaseModel):
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    cagr: float = 0.0
    calmar_ratio: float = 0.0
    win_rate: float = 0.0


class WriteResultsRequest(BaseModel):
    run_id: str = ""
    ticker: str = ""
    model: str = ""
    strategy: str = ""
    results: List[SimulationResultPoint] = Field(default_factory=list)
    metrics: SimulationMetrics = Field(default_factory=SimulationMetrics)


class WriteResultsResponse(BaseModel):
    status: str
    points_written: int
    run_id: str
