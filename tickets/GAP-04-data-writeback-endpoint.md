# GAP-04: Add Data Storage Write-Back Endpoint

**Priority:** MEDIUM
**Severity:** MEDIUM
**Category:** Data
**Effort:** 1-2 days

---

## Architecture Review

### Reliability
- **Current Risk:** Results only in file system, not queryable
- **Mitigation:** Write to both InfluxDB and file system (dual write)
- **Retry Strategy:** Batch writes with retry on failure
- **Idempotency:** Use run_id as unique key, upsert semantics

### Continuity
- **Atomic Writes:** Use InfluxDB batch write API for atomicity
- **Partial Failure:** Log failed points, continue with rest
- **Recovery:** Re-run write from checkpoint if interrupted
- **Deduplication:** run_id + timestamp should be unique

### Integrity
- **Data Validation:** Validate all required fields before write
- **Schema Enforcement:** Use strict InfluxDB tags and fields
- **Referential Integrity:** Ensure run_id exists in run metadata
- **Timestamp Ordering:** Write points in chronological order

### Optimization
- **Batch Writes:** Collect points and write in batches of 1000
- **Compression:** InfluxDB handles compression automatically
- **Async Writes:** Use non-blocking write API for better throughput
- **Connection Pooling:** Reuse InfluxDB client connection

### Separation (Scalability)
- **Write Interface:** Abstract interface for different storage backends
- **File + DB:** Support both file system and InfluxDB simultaneously
- **Query Interface:** Separate read from write paths
- **Horizontal Scaling:** InfluxDB supports clustering

---

## Summary

After trading execution, results should be written back to InfluxDB for historical analysis. Currently results are only stored to the file system (`simulations/` directory), making them not queryable via InfluxDB.

## Current State

- `data/main.go` has `/v1/data/fetch` (write from Yahoo) and `/v1/data/query` (read)
- **No endpoint** for writing simulation results back to InfluxDB
- Results stored to `simulations/` directory (file-based)
- Cannot query historical simulation results via InfluxDB

## Expected Behavior

### Write Results Endpoint
```
POST /v1/data/write_results
Content-Type: application/json

{
  "run_id": "spy-chronos-t5-tiny-20260126",
  "ticker": "SPY",
  "model": "amazon/chronos-t5-tiny",
  "strategy": "threshold",
  "results": [
    {
      "date": "2023-01-15",
      "forecast": 385.2,
      "actual": 383.0,
      "signal": "hold",
      "position": 100.0,
      "cash": 50000.0,
      "portfolio_value": 88300.0
    },
    ...
  ],
  "metrics": {
    "sharpe_ratio": 1.85,
    "max_drawdown": -0.12,
    "cagr": 0.18,
    "calmar_ratio": 1.5,
    "win_rate": 0.58
  }
}

Response:
{
  "status": "success",
  "points_written": 252,
  "run_id": "spy-chronos-t5-tiny-20260126"
}
```

### Query Results
Results queryable via InfluxDB:
```flux
from(bucket: "financial-data")
  |> range(start: -1y)
  |> filter(fn: (r) => r._measurement == "backtest_results")
  |> filter(fn: (r) => r.run_id == "spy-chronos-t5-tiny-20260126")
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
```

## Acceptance Criteria

- [ ] Add `POST /v1/data/write_results` endpoint to Go data service
- [ ] Results written to InfluxDB with proper tags (run_id, ticker, model, strategy)
- [ ] Support batch writes for efficiency (up to 5000 points)
- [ ] Write metrics as separate measurement
- [ ] Add Go tests for the new endpoint
- [ ] Python client wrapper for calling the endpoint
- [ ] Support idempotent writes (re-running doesn't duplicate)

## Implementation

### Go Data Service Updates

#### File: `data/main.go` (additions)

```go
// --- Simulation Result Structs ---

type SimulationResultPoint struct {
    Date           string  `json:"date"`
    Forecast       float64 `json:"forecast"`
    Actual         float64 `json:"actual"`
    Signal         string  `json:"signal"`
    Position       float64 `json:"position"`
    Cash           float64 `json:"cash"`
    PortfolioValue float64 `json:"portfolio_value"`
}

type SimulationMetrics struct {
    SharpeRatio  float64 `json:"sharpe_ratio"`
    MaxDrawdown  float64 `json:"max_drawdown"`
    CAGR         float64 `json:"cagr"`
    CalmarRatio  float64 `json:"calmar_ratio"`
    WinRate      float64 `json:"win_rate"`
}

type WriteResultsRequest struct {
    RunID    string                  `json:"run_id"`
    Ticker   string                  `json:"ticker"`
    Model    string                  `json:"model"`
    Strategy string                  `json:"strategy"`
    Results  []SimulationResultPoint `json:"results"`
    Metrics  SimulationMetrics       `json:"metrics"`
}

type WriteResultsResponse struct {
    Status        string `json:"status"`
    PointsWritten int    `json:"points_written"`
    RunID         string `json:"run_id"`
}

// handleWriteResults writes simulation results to InfluxDB
func (s *Server) handleWriteResults(c *gin.Context) {
    var req WriteResultsRequest
    if err := c.ShouldBindJSON(&req); err != nil {
        c.JSON(http.StatusBadRequest, gin.H{
            "error":   "Invalid request body",
            "details": err.Error(),
        })
        return
    }

    // Validate required fields
    if req.RunID == "" {
        c.JSON(http.StatusBadRequest, gin.H{"error": "run_id is required"})
        return
    }
    if req.Ticker == "" {
        c.JSON(http.StatusBadRequest, gin.H{"error": "ticker is required"})
        return
    }
    if len(req.Results) == 0 {
        c.JSON(http.StatusBadRequest, gin.H{"error": "results cannot be empty"})
        return
    }

    slog.Info("Writing simulation results",
        "run_id", req.RunID,
        "ticker", req.Ticker,
        "model", req.Model,
        "points", len(req.Results),
    )

    // Prepare batch of points
    points := make([]*write.Point, 0, len(req.Results)+1)

    // Common tags for all points
    tags := map[string]string{
        "run_id":   req.RunID,
        "ticker":   req.Ticker,
        "model":    req.Model,
        "strategy": req.Strategy,
    }

    // Convert result points
    for _, result := range req.Results {
        // Parse date
        t, err := time.Parse("2006-01-02", result.Date)
        if err != nil {
            slog.Warn("Invalid date format, skipping point",
                "date", result.Date,
                "error", err,
            )
            continue
        }

        point := write.NewPoint(
            "backtest_results",
            tags,
            map[string]interface{}{
                "forecast":        result.Forecast,
                "actual":          result.Actual,
                "signal":          result.Signal,
                "position":        result.Position,
                "cash":            result.Cash,
                "portfolio_value": result.PortfolioValue,
            },
            t,
        )
        points = append(points, point)
    }

    // Write metrics as a separate point (at the end date)
    if len(req.Results) > 0 {
        lastDate := req.Results[len(req.Results)-1].Date
        t, _ := time.Parse("2006-01-02", lastDate)

        metricsPoint := write.NewPoint(
            "backtest_metrics",
            tags,
            map[string]interface{}{
                "sharpe_ratio":  req.Metrics.SharpeRatio,
                "max_drawdown":  req.Metrics.MaxDrawdown,
                "cagr":          req.Metrics.CAGR,
                "calmar_ratio":  req.Metrics.CalmarRatio,
                "win_rate":      req.Metrics.WinRate,
                "total_points":  len(req.Results),
            },
            t,
        )
        points = append(points, metricsPoint)
    }

    // Batch write to InfluxDB
    ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
    defer cancel()

    for i := 0; i < len(points); i += 1000 {
        end := i + 1000
        if end > len(points) {
            end = len(points)
        }

        batch := points[i:end]
        for _, p := range batch {
            if err := s.WriteAPI.WritePoint(ctx, p); err != nil {
                slog.Error("Failed to write point", "error", err)
                c.JSON(http.StatusInternalServerError, gin.H{
                    "error":   "Failed to write to InfluxDB",
                    "details": err.Error(),
                })
                return
            }
        }
    }

    slog.Info("Successfully wrote simulation results",
        "run_id", req.RunID,
        "points_written", len(points),
    )

    c.JSON(http.StatusOK, WriteResultsResponse{
        Status:        "success",
        PointsWritten: len(points),
        RunID:         req.RunID,
    })
}
```

#### Register Endpoint

```go
// In main()
router.POST("/v1/data/write_results", server.handleWriteResults)
```

### Python Client Wrapper

#### File: `orchestration/clients/data_client.py`

```python
"""
Data Service Client

Handles communication with the Go data service for
reading and writing time-series data.
"""

import httpx
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import os

logger = logging.getLogger(__name__)


@dataclass
class ResultPoint:
    """Single backtest result point."""
    date: str
    forecast: float
    actual: float
    signal: str
    position: float
    cash: float
    portfolio_value: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "date": self.date,
            "forecast": self.forecast,
            "actual": self.actual,
            "signal": self.signal,
            "position": self.position,
            "cash": self.cash,
            "portfolio_value": self.portfolio_value,
        }


@dataclass
class MetricsSummary:
    """Metrics summary for storage."""
    sharpe_ratio: float
    max_drawdown: float
    cagr: float
    calmar_ratio: float
    win_rate: float

    def to_dict(self) -> Dict[str, float]:
        return {
            "sharpe_ratio": self.sharpe_ratio,
            "max_drawdown": self.max_drawdown,
            "cagr": self.cagr,
            "calmar_ratio": self.calmar_ratio,
            "win_rate": self.win_rate,
        }


class DataClient:
    """
    Client for the Go data service.

    Handles both reading historical data and writing backtest results.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: float = 60.0,
    ):
        self.base_url = base_url or os.getenv(
            "DATA_SERVICE_URL",
            "http://sapheneia-data:8000"
        )
        self.timeout = timeout

    async def write_results(
        self,
        run_id: str,
        ticker: str,
        model: str,
        strategy: str,
        results: List[ResultPoint],
        metrics: MetricsSummary,
    ) -> bool:
        """
        Write backtest results to InfluxDB.

        Args:
            run_id: Unique identifier for this backtest run
            ticker: Ticker symbol
            model: Model used for forecasting
            strategy: Trading strategy type
            results: List of result points
            metrics: Summary metrics

        Returns:
            True if successful, False otherwise
        """
        payload = {
            "run_id": run_id,
            "ticker": ticker,
            "model": model,
            "strategy": strategy,
            "results": [r.to_dict() for r in results],
            "metrics": metrics.to_dict(),
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/v1/data/write_results",
                    json=payload,
                )
                response.raise_for_status()

                data = response.json()
                logger.info(
                    f"Wrote {data.get('points_written', 0)} points "
                    f"for run_id={run_id}"
                )
                return True

        except httpx.HTTPStatusError as e:
            logger.error(f"Data service HTTP error: {e}")
            return False

        except httpx.RequestError as e:
            logger.error(f"Data service connection error: {e}")
            return False

    async def query_data(
        self,
        ticker: str,
        days: int = 90,
        end_date: Optional[str] = None,
    ) -> List[float]:
        """
        Query historical data from InfluxDB.

        Args:
            ticker: Ticker symbol
            days: Number of days of history
            end_date: Optional end date (for backtest mode)

        Returns:
            List of close prices
        """
        payload = {
            "ticker": ticker,
            "days": days,
        }
        if end_date:
            payload["end_date"] = end_date

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/v1/data/query",
                    json=payload,
                )
                response.raise_for_status()

                data = response.json()
                # Extract close prices from response
                return [point.get("close", 0.0) for point in data.get("data", [])]

        except httpx.HTTPStatusError as e:
            logger.error(f"Data service HTTP error: {e}")
            return []

        except httpx.RequestError as e:
            logger.error(f"Data service connection error: {e}")
            return []
```

## InfluxDB Schema

### Measurement: `backtest_results`

| Type | Name | Description |
|------|------|-------------|
| Tag | run_id | Unique backtest run identifier |
| Tag | ticker | Stock/crypto ticker |
| Tag | model | Model used (e.g., chronos-t5-tiny) |
| Tag | strategy | Trading strategy type |
| Field | forecast | Forecasted price |
| Field | actual | Actual price |
| Field | signal | Trading signal (buy/sell/hold) |
| Field | position | Current position size |
| Field | cash | Available cash |
| Field | portfolio_value | Total portfolio value |
| Time | _time | Evaluation date |

### Measurement: `backtest_metrics`

| Type | Name | Description |
|------|------|-------------|
| Tag | run_id | Unique backtest run identifier |
| Tag | ticker | Stock/crypto ticker |
| Tag | model | Model used |
| Tag | strategy | Trading strategy type |
| Field | sharpe_ratio | Sharpe ratio |
| Field | max_drawdown | Maximum drawdown |
| Field | cagr | CAGR |
| Field | calmar_ratio | Calmar ratio |
| Field | win_rate | Win rate |
| Field | total_points | Number of evaluation points |
| Time | _time | End date of backtest |

## Test Cases

### Go Tests

```go
func TestHandleWriteResults_ValidRequest(t *testing.T) {
    // Test successful write
}

func TestHandleWriteResults_MissingRunID(t *testing.T) {
    // Test validation error
}

func TestHandleWriteResults_EmptyResults(t *testing.T) {
    // Test validation error
}

func TestHandleWriteResults_InvalidDate(t *testing.T) {
    // Test date parsing error handling
}

func TestHandleWriteResults_BatchWrite(t *testing.T) {
    // Test large batch (>1000 points)
}
```

## Dependencies

- None (can be developed independently)

## Related Files

- `data/main.go`
- `data/main_test.go`
- New: `orchestration/clients/data_client.py`
