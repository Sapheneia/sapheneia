# Aleutian + Sapheneia Evaluation Framework Integration Plan

**Date:** 2025-12-18
**Project:** Sapheneia Time-Series Forecasting & Trading Evaluation
**Integration:** AleutianLocal (Go Orchestrator) + Sapheneia (Python Services)

---

## Executive Summary

Great news! **You already have a working evaluation framework** in AleutianLocal. However, it's designed for **single-point evaluation** (one forecast at current time), not **historical backtesting** (rolling window over years of data).

This document outlines the complete plan to transform the existing evaluation framework into a comprehensive backtesting system that:
1. Fetches historical data from Yahoo Finance → InfluxDB
2. Runs rolling window forecasts for every trading day after the context period
3. Generates trading signals for each forecast
4. Tracks portfolio state across the entire backtest
5. Stores all results in InfluxDB for analysis

---

## Current State Analysis

### What Exists ✅

| Component          | Status                | Location                                     |
|--------------------|-----------------------|----------------------------------------------|
| CLI Command        | ✅ Working            | `/cmd/aleutian/cmd_evaluation.go`            |
| Evaluator Logic    | ✅ Basic              | `/services/orchestrator/handlers/evaluator.go` |
| InfluxDB Storage   | ✅ Single measurement | `forecast_evaluations` measurement           |
| Portfolio Tracking | ✅ In-memory only     | Maintained during evaluation loop            |
| Forecast API Call  | ✅ Working            | Calls orchestrator `/v1/timeseries/forecast` |
| Trading API Call   | ✅ Working            | Calls sapheneia `/trading/execute`           |

**Current CLI Usage:**
```bash
./aleutian evaluate run --ticker SPY --model "google/timesfm-2.0-500m-pytorch"
```

**Current Behavior:**
- Fetches current price from InfluxDB
- Generates ONE forecast at current time
- Loops through forecast horizons (1-20 days)
- Calls trading service for each horizon
- Stores results in `forecast_evaluations` measurement

### What's Missing for Your Flow ❌

| Requirement                    | Current State                   | Needed                                         |
|--------------------------------|---------------------------------|------------------------------------------------|
| **Historical rolling windows** | ❌ Only evaluates current time  | ✅ Loop through every day after context period |
| **Data fetching step**         | ❌ Assumes data exists          | ✅ Auto-fetch from Yahoo Finance               |
| **Separate InfluxDB measurements** | ❌ Single `forecast_evaluations`  | ✅ `forecasts`, `trading_signals`, `portfolio_state` |
| **Full forecast storage**      | ❌ Only stores final results    | ✅ Store all 20-day forecasts                  |
| **Portfolio state in InfluxDB** | ❌ Memory only                  | ✅ Write to InfluxDB after each signal         |
| **Start/end date params**      | ❌ Only `--date` flag           | ✅ `--start-date`, `--end-date`, `--backtest-years` |
| **Historical data reading**    | ❌ No InfluxDB read for windows | ✅ Query historical windows for forecasts      |
| **Batched parallel execution** | ❌ Sequential only              | ✅ Process 2-3 tickers simultaneously          |

---

## Proposed InfluxDB Schema

Based on your requirements (full 20-day forecasts + portfolio state), here's the comprehensive schema:

### Measurement 1: `stock_prices` (ALREADY EXISTS)

```
Measurement: "stock_prices"
Tags:
  - ticker: "SPY"
Time: 2024-01-15 (trading day)
Fields:
  - open: 575.20
  - high: 578.50
  - low: 574.10
  - close: 577.30
  - adj_close: 577.30
  - volume: 65432100.0
```

**Purpose:** Raw OHLCV data from Yahoo Finance
**Written by:** Data service (Go) `/v1/data/fetch` endpoint
**Read by:** Forecast service (needs historical context windows)

---

### Measurement 2: `forecasts` (NEW)

```
Measurement: "forecasts"
Tags:
  - ticker: "SPY"
  - model: "google/timesfm-2.0-500m-pytorch"
  - run_id: "20250118_abc123"
  - context_size: "252"
Time: 2024-01-15 (forecast generation date)
Fields:
  // Mean forecasts
  - day_01_mean, day_02_mean, ..., day_20_mean: float64

  // Quantiles (for uncertainty)
  - day_01_q10, day_01_q50, day_01_q90: float64
  - day_02_q10, day_02_q50, day_02_q90: float64
  ...
  - day_20_q10, day_20_q50, day_20_q90: float64

  // Metadata
  - horizon_size: 20
  - actual_context_used: 252
```

**Purpose:** Store complete 20-day forecast for each rolling window
**Written by:** Evaluator (Go) after calling forecast service
**Read by:** Analysis tools, Grafana dashboards
**Storage Cost:** ~80 fields per forecast (20 means + 60 quantiles)

**Example Query:**
```flux
from(bucket: "financial-data")
  |> range(start: 2024-01-01, stop: 2024-12-31)
  |> filter(fn: (r) => r._measurement == "forecasts")
  |> filter(fn: (r) => r.ticker == "SPY")
  |> filter(fn: (r) => r.model == "google/timesfm-2.0-500m-pytorch")
  |> filter(fn: (r) => r._field == "day_01_mean")
```

---

### Measurement 3: `trading_signals` (NEW)

```
Measurement: "trading_signals"
Tags:
  - ticker: "SPY"
  - model: "google/timesfm-2.0-500m-pytorch"
  - strategy_type: "threshold"
  - run_id: "20250118_abc123"
  - action: "BUY" | "SELL" | "HOLD"
Time: 2024-01-15 (signal generation date)
Fields:
  - forecast_price: 580.0
  - current_price: 575.0
  - signal_strength: 0.75
  - size: 10.0
  - value: 5750.0
  - reason: "Forecast exceeds threshold"
  - threshold_value: 2.0
  - execution_size: 10.0
```

**Purpose:** Trading decisions for each forecast
**Written by:** Evaluator (Go) after calling trading service
**Read by:** Portfolio tracker, performance analysis
**Cardinality:** One signal per trading day per ticker per model

**Example Query:**
```flux
// Find all BUY signals
from(bucket: "financial-data")
  |> range(start: 2024-01-01, stop: 2024-12-31)
  |> filter(fn: (r) => r._measurement == "trading_signals")
  |> filter(fn: (r) => r.action == "BUY")
  |> filter(fn: (r) => r.ticker == "SPY")
```

---

### Measurement 4: `portfolio_state` (NEW)

```
Measurement: "portfolio_state"
Tags:
  - ticker: "SPY"
  - model: "google/timesfm-2.0-500m-pytorch"
  - strategy_type: "threshold"
  - run_id: "20250118_abc123"
Time: 2024-01-15 (state snapshot date)
Fields:
  - position: 110.0
  - cash: 44250.0
  - portfolio_value: 107930.0  (position * current_price + cash)
  - total_return: 0.0793  (7.93%)
  - daily_return: 0.0023
  - max_drawdown: -0.05
  - num_trades: 15
  - win_rate: 0.60
  - sharpe_ratio: 1.25 (calculated over window)
```

**Purpose:** Portfolio evolution over time for backtesting
**Written by:** Evaluator (Go) after each signal execution
**Read by:** Performance metrics calculator, Grafana dashboards
**Benefits:** Enables resume/replay, time-series analysis of strategy performance

**Example Query:**
```flux
// Calculate portfolio equity curve
from(bucket: "financial-data")
  |> range(start: 2024-01-01, stop: 2024-12-31)
  |> filter(fn: (r) => r._measurement == "portfolio_state")
  |> filter(fn: (r) => r._field == "portfolio_value")
  |> filter(fn: (r) => r.ticker == "SPY")
  |> sort(columns: ["_time"])
```

---

## Implementation Plan

This is a significant refactor broken into 4 phases:

### Phase 1: Schema & Storage Layer (Foundation)

**Files to modify:**
- `/services/orchestrator/handlers/evaluator.go`
- `/services/orchestrator/datatypes/evaluator.go`

**New data structures:**

```go
// Add to datatypes/evaluator.go

type ForecastData struct {
    Ticker         string
    Model          string
    RunID          string
    GenerationDate time.Time
    MeanForecasts  []float64     // 20 values
    Quantiles      []QuantileSet // 20 sets of Q10/Q50/Q90
    ContextSize    int
    HorizonSize    int
}

type QuantileSet struct {
    Q10 float64
    Q50 float64
    Q90 float64
}

type TradingSignalData struct {
    Ticker         string
    Model          string
    StrategyType   string
    RunID          string
    SignalDate     time.Time
    Action         string
    ForecastPrice  float64
    CurrentPrice   float64
    Size           float64
    Value          float64
    Reason         string
    ThresholdValue float64
    ExecutionSize  float64
}

type PortfolioState struct {
    Ticker         string
    Model          string
    StrategyType   string
    RunID          string
    SnapshotDate   time.Time
    Position       float64
    Cash           float64
    PortfolioValue float64
    TotalReturn    float64
    DailyReturn    float64
    NumTrades      int
    WinRate        float64
    MaxDrawdown    float64
    SharpeRatio    float64
}

type HistoricalDataPoint struct {
    Time      time.Time
    Open      float64
    High      float64
    Low       float64
    Close     float64
    AdjClose  float64
    Volume    float64
}
```

**New storage methods:**

```go
// Add to handlers/evaluator.go

// StoreForecast writes full 20-day forecast to InfluxDB
func (s *InfluxDBStorage) StoreForecast(ctx context.Context, forecast *ForecastData) error {
    p := influxdb2.NewPointWithMeasurement("forecasts").
        AddTag("ticker", forecast.Ticker).
        AddTag("model", forecast.Model).
        AddTag("run_id", forecast.RunID).
        AddTag("context_size", fmt.Sprintf("%d", forecast.ContextSize)).
        SetTime(forecast.GenerationDate)

    // Store all 20 forecast values
    for i, val := range forecast.MeanForecasts {
        p = p.AddField(fmt.Sprintf("day_%02d_mean", i+1), val)
    }

    // Store quantiles if available
    for i, quantiles := range forecast.Quantiles {
        p = p.AddField(fmt.Sprintf("day_%02d_q10", i+1), quantiles.Q10)
        p = p.AddField(fmt.Sprintf("day_%02d_q50", i+1), quantiles.Q50)
        p = p.AddField(fmt.Sprintf("day_%02d_q90", i+1), quantiles.Q90)
    }

    p = p.AddField("horizon_size", forecast.HorizonSize)
    p = p.AddField("actual_context_used", forecast.ContextSize)

    return s.writeAPI.WritePoint(ctx, p)
}

// StoreTradingSignal writes trading signal to InfluxDB
func (s *InfluxDBStorage) StoreTradingSignal(ctx context.Context, signal *TradingSignalData) error {
    p := influxdb2.NewPointWithMeasurement("trading_signals").
        AddTag("ticker", signal.Ticker).
        AddTag("model", signal.Model).
        AddTag("strategy_type", signal.StrategyType).
        AddTag("run_id", signal.RunID).
        AddTag("action", signal.Action).
        AddField("forecast_price", signal.ForecastPrice).
        AddField("current_price", signal.CurrentPrice).
        AddField("size", signal.Size).
        AddField("value", signal.Value).
        AddField("reason", signal.Reason).
        AddField("threshold_value", signal.ThresholdValue).
        AddField("execution_size", signal.ExecutionSize).
        SetTime(signal.SignalDate)

    return s.writeAPI.WritePoint(ctx, p)
}

// StorePortfolioState writes portfolio snapshot to InfluxDB
func (s *InfluxDBStorage) StorePortfolioState(ctx context.Context, state *PortfolioState) error {
    p := influxdb2.NewPointWithMeasurement("portfolio_state").
        AddTag("ticker", state.Ticker).
        AddTag("model", state.Model).
        AddTag("strategy_type", state.StrategyType).
        AddTag("run_id", state.RunID).
        AddField("position", state.Position).
        AddField("cash", state.Cash).
        AddField("portfolio_value", state.PortfolioValue).
        AddField("total_return", state.TotalReturn).
        AddField("daily_return", state.DailyReturn).
        AddField("num_trades", state.NumTrades).
        AddField("win_rate", state.WinRate).
        AddField("max_drawdown", state.MaxDrawdown).
        AddField("sharpe_ratio", state.SharpeRatio).
        SetTime(state.SnapshotDate)

    return s.writeAPI.WritePoint(ctx, p)
}
```

**Testing strategy:**
```bash
# Test Phase 1
go test -v ./services/orchestrator/handlers -run TestStoreForecast
go test -v ./services/orchestrator/handlers -run TestStoreTradingSignal
go test -v ./services/orchestrator/handlers -run TestStorePortfolioState
```

---

### Phase 2: Rolling Window Data Reader (Historical Context)

**Files to modify:**
- `/services/orchestrator/handlers/evaluator.go`

**New query methods:**

```go
// GetHistoricalWindow reads a specific window of historical data for forecasting
func (s *InfluxDBStorage) GetHistoricalWindow(
    ctx context.Context,
    ticker string,
    endDate time.Time,
    windowSize int,
) ([]HistoricalDataPoint, error) {
    // Add buffer for weekends/holidays
    startDate := endDate.AddDate(0, 0, -(windowSize + 30))

    query := fmt.Sprintf(`
        from(bucket: "%s")
          |> range(start: %s, stop: %s)
          |> filter(fn: (r) => r._measurement == "stock_prices")
          |> filter(fn: (r) => r.ticker == "%s")
          |> filter(fn: (r) => r._field == "close" or r._field == "open" or r._field == "high" or r._field == "low" or r._field == "volume")
          |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
          |> sort(columns: ["_time"])
          |> limit(n: %d, offset: -1)
    `, s.bucket, startDate.Format(time.RFC3339), endDate.Format(time.RFC3339), ticker, windowSize)

    queryAPI := s.client.QueryAPI(s.org)
    result, err := queryAPI.Query(ctx, query)
    if err != nil {
        return nil, fmt.Errorf("query failed: %w", err)
    }

    var dataPoints []HistoricalDataPoint
    for result.Next() {
        record := result.Record()
        dataPoint := HistoricalDataPoint{
            Time: record.Time(),
        }

        // Parse fields from pivoted result
        if v, ok := record.ValueByKey("open").(float64); ok {
            dataPoint.Open = v
        }
        if v, ok := record.ValueByKey("high").(float64); ok {
            dataPoint.High = v
        }
        if v, ok := record.ValueByKey("low").(float64); ok {
            dataPoint.Low = v
        }
        if v, ok := record.ValueByKey("close").(float64); ok {
            dataPoint.Close = v
        }
        if v, ok := record.ValueByKey("volume").(float64); ok {
            dataPoint.Volume = v
        }

        dataPoints = append(dataPoints, dataPoint)
    }

    if len(dataPoints) < windowSize {
        return nil, fmt.Errorf("insufficient data: got %d points, need %d", len(dataPoints), windowSize)
    }

    // Return exactly windowSize points (most recent)
    return dataPoints[len(dataPoints)-windowSize:], nil
}

// GetTradingDays returns all trading days between start and end
func (s *InfluxDBStorage) GetTradingDays(
    ctx context.Context,
    ticker string,
    startDate, endDate time.Time,
) ([]time.Time, error) {
    query := fmt.Sprintf(`
        from(bucket: "%s")
          |> range(start: %s, stop: %s)
          |> filter(fn: (r) => r._measurement == "stock_prices")
          |> filter(fn: (r) => r.ticker == "%s")
          |> filter(fn: (r) => r._field == "close")
          |> keep(columns: ["_time"])
          |> distinct(column: "_time")
          |> sort(columns: ["_time"])
    `, s.bucket, startDate.Format(time.RFC3339), endDate.Format(time.RFC3339), ticker)

    queryAPI := s.client.QueryAPI(s.org)
    result, err := queryAPI.Query(ctx, query)
    if err != nil {
        return nil, fmt.Errorf("query failed: %w", err)
    }

    var tradingDays []time.Time
    for result.Next() {
        tradingDays = append(tradingDays, result.Record().Time())
    }

    return tradingDays, nil
}
```

**Testing strategy:**
```bash
# First, ensure you have test data in InfluxDB
./aleutian timeseries fetch SPY --days 3650  # 10 years

# Then test the query methods
go test -v ./services/orchestrator/handlers -run TestGetHistoricalWindow
go test -v ./services/orchestrator/handlers -run TestGetTradingDays
```

---

### Phase 3: Refactored Evaluation Flow (Core Logic)

**Files to modify:**
- `/services/orchestrator/handlers/evaluator.go`
- `/cmd/aleutian/cmd_evaluation.go`
- `/services/orchestrator/datatypes/evaluator.go`

**Updated EvaluationConfig:**

```go
// Update in datatypes/evaluator.go
type EvaluationConfig struct {
    Tickers        []TickerInfo
    Models         []string
    EvaluationDate string // Deprecated, use BacktestEndDate
    RunID          string

    // NEW: Backtest date range
    BacktestStartDate time.Time
    BacktestEndDate   time.Time
    BacktestYears     int  // Alternative to explicit dates

    // Strategy configuration
    StrategyType   string
    StrategyParams map[string]interface{}

    // Forecast configuration
    ContextSize int
    HorizonSize int

    // Portfolio configuration
    InitialCapital  float64
    InitialPosition float64
    InitialCash     float64

    // NEW: Execution options
    SkipDataFetch   bool
    ParallelBatches int  // Number of tickers to process in parallel (default: 3)
}
```

**New main orchestration flow:**

```go
func (e *Evaluator) RunEvaluation(ctx context.Context, config *datatypes.EvaluationConfig) error {
    slog.Info("Starting evaluation run",
        "run_id", config.RunID,
        "tickers", len(config.Tickers),
        "models", len(config.Models),
        "start_date", config.BacktestStartDate.Format("2006-01-02"),
        "end_date", config.BacktestEndDate.Format("2006-01-02"))

    // === Phase 1: Data Fetching ===
    if !config.SkipDataFetch {
        slog.Info("Phase 1: Fetching historical data")
        if err := e.FetchHistoricalData(ctx, config); err != nil {
            return fmt.Errorf("data fetch failed: %w", err)
        }
    } else {
        slog.Info("Phase 1: Skipping data fetch (--skip-fetch flag)")
    }

    // === Phase 2: Get Trading Days ===
    // Use SPY as reference for trading calendar
    tradingDays, err := e.storage.GetTradingDays(
        ctx,
        "SPY",
        config.BacktestStartDate,
        config.BacktestEndDate,
    )
    if err != nil {
        return fmt.Errorf("failed to get trading days: %w", err)
    }

    slog.Info("Phase 2: Loaded trading calendar",
        "total_days", len(tradingDays),
        "after_context", len(tradingDays)-config.ContextSize)

    // === Phase 3: Batched Parallel Execution ===
    slog.Info("Phase 3: Running rolling window forecasts")

    batchSize := config.ParallelBatches
    if batchSize == 0 {
        batchSize = 3  // Default
    }

    tickerBatches := batchTickers(config.Tickers, batchSize)
    totalBatches := len(tickerBatches)

    for batchIdx, batch := range tickerBatches {
        slog.Info("Processing batch",
            "batch", fmt.Sprintf("%d/%d", batchIdx+1, totalBatches),
            "tickers", len(batch))

        var wg sync.WaitGroup
        errChan := make(chan error, len(batch))

        for _, tickerInfo := range batch {
            wg.Add(1)
            go func(ti datatypes.TickerInfo) {
                defer wg.Done()
                err := e.EvaluateTickerRolling(ctx, ti.Ticker, config, tradingDays)
                if err != nil {
                    errChan <- fmt.Errorf("%s: %w", ti.Ticker, err)
                }
            }(tickerInfo)
        }

        wg.Wait()
        close(errChan)

        // Log any errors from this batch
        for err := range errChan {
            slog.Error("Batch evaluation error", "error", err)
        }
    }

    // === Phase 4: Performance Metrics ===
    slog.Info("Phase 4: Calculating performance metrics")
    if err := e.CalculatePerformanceMetrics(ctx, config); err != nil {
        slog.Error("Failed to calculate metrics", "error", err)
    }

    slog.Info("✅ Evaluation completed successfully",
        "run_id", config.RunID,
        "total_days", len(tradingDays))

    return nil
}
```

**New rolling window evaluation:**

```go
// EvaluateTickerRolling runs backtesting for a single ticker across all models
func (e *Evaluator) EvaluateTickerRolling(
    ctx context.Context,
    ticker string,
    config *datatypes.EvaluationConfig,
    tradingDays []time.Time,
) error {

    for _, model := range config.Models {
        slog.Info("Evaluating", "ticker", ticker, "model", model)

        // Initialize portfolio state
        portfolio := &PortfolioState{
            Ticker:       ticker,
            Model:        model,
            StrategyType: config.StrategyType,
            RunID:        config.RunID,
            Position:     config.InitialPosition,
            Cash:         config.InitialCash,
        }

        previousPortfolioValue := config.InitialCapital
        contextDays := config.ContextSize

        // Progress tracking
        totalDays := len(tradingDays) - contextDays
        processedDays := 0

        // === Loop through all trading days ===
        for dayIdx, currentDay := range tradingDays {
            // Skip until we have enough context
            if dayIdx < contextDays {
                continue
            }

            processedDays++
            if processedDays%50 == 0 {
                slog.Info("Progress",
                    "ticker", ticker,
                    "model", model,
                    "progress", fmt.Sprintf("%d/%d (%.1f%%)",
                        processedDays, totalDays,
                        float64(processedDays)/float64(totalDays)*100))
            }

            // === Step 1: Read historical window ===
            windowData, err := e.storage.GetHistoricalWindow(
                ctx, ticker, currentDay, contextDays)
            if err != nil {
                slog.Error("Failed to read window",
                    "ticker", ticker,
                    "date", currentDay.Format("2006-01-02"),
                    "error", err)
                continue
            }

            // === Step 2: Generate forecast ===
            forecast, err := e.CallForecastServiceWithData(
                ctx, ticker, model, windowData, config.HorizonSize)
            if err != nil {
                slog.Error("Forecast failed",
                    "ticker", ticker,
                    "date", currentDay.Format("2006-01-02"),
                    "error", err)
                continue
            }

            if len(forecast.Forecast) == 0 {
                slog.Warn("Empty forecast received", "ticker", ticker)
                continue
            }

            // === Step 3: Store full 20-day forecast ===
            forecastData := &ForecastData{
                Ticker:         ticker,
                Model:          model,
                RunID:          config.RunID,
                GenerationDate: currentDay,
                MeanForecasts:  forecast.Forecast,
                ContextSize:    contextDays,
                HorizonSize:    config.HorizonSize,
            }

            // TODO: Parse quantiles from forecast response if available
            // forecastData.Quantiles = parseQuantiles(forecast)

            if err := e.storage.StoreForecast(ctx, forecastData); err != nil {
                slog.Error("Failed to store forecast", "error", err)
            }

            // === Step 4: Generate trading signal (day_1 forecast only) ===
            currentPrice := windowData[len(windowData)-1].Close
            forecastPrice := forecast.Forecast[0]  // Day 1 prediction

            tradingReq := TradingSignalRequest{
                Ticker:          ticker,
                StrategyType:    config.StrategyType,
                ForecastPrice:   forecastPrice,
                CurrentPrice:    &currentPrice,
                CurrentPosition: portfolio.Position,
                AvailableCash:   portfolio.Cash,
                InitialCapital:  config.InitialCapital,
                StrategyParams:  config.StrategyParams,
            }

            signal, err := e.CallTradingService(ctx, tradingReq)
            if err != nil {
                slog.Error("Trading signal failed",
                    "ticker", ticker,
                    "date", currentDay.Format("2006-01-02"),
                    "error", err)
                continue
            }

            // === Step 5: Store trading signal ===
            thresholdVal, _ := config.StrategyParams["threshold_value"].(float64)
            executionSize, _ := config.StrategyParams["execution_size"].(float64)

            signalData := &TradingSignalData{
                Ticker:         ticker,
                Model:          model,
                StrategyType:   config.StrategyType,
                RunID:          config.RunID,
                SignalDate:     currentDay,
                Action:         signal.Action,
                ForecastPrice:  forecastPrice,
                CurrentPrice:   currentPrice,
                Size:           signal.Size,
                Value:          signal.Value,
                Reason:         signal.Reason,
                ThresholdValue: thresholdVal,
                ExecutionSize:  executionSize,
            }

            if err := e.storage.StoreTradingSignal(ctx, signalData); err != nil {
                slog.Error("Failed to store signal", "error", err)
            }

            // === Step 6: Update portfolio state ===
            portfolio.Position = signal.PositionAfter
            portfolio.Cash = signal.AvailableCash
            portfolio.PortfolioValue = portfolio.Position*currentPrice + portfolio.Cash
            portfolio.TotalReturn = (portfolio.PortfolioValue - config.InitialCapital) / config.InitialCapital
            portfolio.DailyReturn = (portfolio.PortfolioValue - previousPortfolioValue) / previousPortfolioValue

            if signal.Action != "HOLD" {
                portfolio.NumTrades++
            }

            // Calculate max drawdown (running calculation)
            // TODO: Implement proper drawdown tracking

            // === Step 7: Store portfolio state ===
            portfolio.SnapshotDate = currentDay
            if err := e.storage.StorePortfolioState(ctx, portfolio); err != nil {
                slog.Error("Failed to store portfolio state", "error", err)
            }

            previousPortfolioValue = portfolio.PortfolioValue
        }

        slog.Info("Completed ticker/model",
            "ticker", ticker,
            "model", model,
            "final_return", fmt.Sprintf("%.2f%%", portfolio.TotalReturn*100),
            "total_trades", portfolio.NumTrades)
    }

    return nil
}
```

**Helper functions:**

```go
// batchTickers splits tickers into batches for parallel processing
func batchTickers(tickers []datatypes.TickerInfo, batchSize int) [][]datatypes.TickerInfo {
    var batches [][]datatypes.TickerInfo
    for i := 0; i < len(tickers); i += batchSize {
        end := i + batchSize
        if end > len(tickers) {
            end = len(tickers)
        }
        batches = append(batches, tickers[i:end])
    }
    return batches
}

// FetchHistoricalData calls the data service to fetch Yahoo Finance data
func (e *Evaluator) FetchHistoricalData(ctx context.Context, config *datatypes.EvaluationConfig) error {
    dataServiceURL := os.Getenv("ALEUTIAN_DATA_FETCHER_URL")
    if dataServiceURL == "" {
        dataServiceURL = "http://localhost:8001"
    }

    // Calculate number of days to fetch
    days := int(config.BacktestEndDate.Sub(config.BacktestStartDate).Hours() / 24)
    days += config.ContextSize + 50  // Add buffer for context + weekends

    for _, tickerInfo := range config.Tickers {
        slog.Info("Fetching data", "ticker", tickerInfo.Ticker, "days", days)

        payload := map[string]interface{}{
            "names":      []string{tickerInfo.Ticker},
            "start_date": config.BacktestStartDate.Format("2006-01-02"),
            "interval":   "1d",
        }

        reqBody, _ := json.Marshal(payload)
        req, _ := http.NewRequestWithContext(
            ctx,
            "POST",
            fmt.Sprintf("%s/v1/data/fetch", dataServiceURL),
            bytes.NewBuffer(reqBody),
        )
        req.Header.Set("Content-Type", "application/json")

        resp, err := e.httpClient.Do(req)
        if err != nil {
            return fmt.Errorf("fetch failed for %s: %w", tickerInfo.Ticker, err)
        }
        resp.Body.Close()

        if resp.StatusCode != http.StatusOK {
            return fmt.Errorf("fetch failed for %s: status %d", tickerInfo.Ticker, resp.StatusCode)
        }
    }

    return nil
}

// CalculatePerformanceMetrics aggregates results and calculates final metrics
func (e *Evaluator) CalculatePerformanceMetrics(ctx context.Context, config *datatypes.EvaluationConfig) error {
    // TODO: Implement
    // - Sharpe ratio calculation
    // - Max drawdown calculation
    // - Win rate calculation
    // - Average trade size
    // - etc.
    return nil
}
```

---

### Phase 4: CLI Flag Updates & UX Polish

**Files to modify:**
- `/cmd/aleutian/commands.go`
- `/cmd/aleutian/cmd_evaluation.go`

**Updated CLI flags:**

```go
// In commands.go init()
runEvaluationCmd.Flags().String("start-date", "", "Backtest start date (YYYY-MM-DD)")
runEvaluationCmd.Flags().String("end-date", "", "Backtest end date (YYYY-MM-DD, default: today)")
runEvaluationCmd.Flags().Int("backtest-years", 10, "Number of years to backtest (default: 10)")
runEvaluationCmd.Flags().Bool("skip-fetch", false, "Skip data fetching step")
runEvaluationCmd.Flags().Int("parallel", 3, "Number of tickers to process in parallel (default: 3)")
runEvaluationCmd.Flags().StringSlice("tickers", nil, "Comma-separated list of tickers (overrides --ticker)")
runEvaluationCmd.Flags().StringSlice("models", nil, "Comma-separated list of models (overrides --model)")
```

**Updated runEvaluation function:**

```go
func runEvaluation(cmd *cobra.Command, args []string) {
    // Parse flags
    startDateStr, _ := cmd.Flags().GetString("start-date")
    endDateStr, _ := cmd.Flags().GetString("end-date")
    backtestYears, _ := cmd.Flags().GetInt("backtest-years")
    skipFetch, _ := cmd.Flags().GetBool("skip-fetch")
    parallel, _ := cmd.Flags().GetInt("parallel")
    ticker, _ := cmd.Flags().GetString("ticker")
    model, _ := cmd.Flags().GetString("model")
    tickersFlag, _ := cmd.Flags().GetStringSlice("tickers")
    modelsFlag, _ := cmd.Flags().GetStringSlice("models")

    // Calculate date range
    var startDate, endDate time.Time
    if endDateStr == "" {
        endDate = time.Now()
    } else {
        var err error
        endDate, err = time.Parse("2006-01-02", endDateStr)
        if err != nil {
            slog.Error("Invalid end-date format", "error", err)
            return
        }
    }

    if startDateStr == "" {
        // Use backtest-years
        startDate = endDate.AddDate(-backtestYears, 0, 0)
    } else {
        var err error
        startDate, err = time.Parse("2006-01-02", startDateStr)
        if err != nil {
            slog.Error("Invalid start-date format", "error", err)
            return
        }
    }

    runID := fmt.Sprintf("%s_%s", endDate.Format("20060102"), uuid.New().String()[:8])

    // Select tickers
    var tickers []datatypes.TickerInfo
    if len(tickersFlag) > 0 {
        for _, t := range tickersFlag {
            tickers = append(tickers, datatypes.TickerInfo{Ticker: t})
        }
    } else if ticker != "" {
        tickers = []datatypes.TickerInfo{{Ticker: ticker}}
    } else {
        tickers = datatypes.DefaultTickers
    }

    // Select models
    var models []string
    if len(modelsFlag) > 0 {
        models = modelsFlag
    } else if model != "" {
        models = []string{model}
    } else {
        models = datatypes.DefaultModels
    }

    // Build config
    config := &datatypes.EvaluationConfig{
        Tickers:           tickers,
        Models:            models,
        RunID:             runID,
        BacktestStartDate: startDate,
        BacktestEndDate:   endDate,
        BacktestYears:     backtestYears,
        SkipDataFetch:     skipFetch,
        ParallelBatches:   parallel,
        StrategyType:      "threshold",
        StrategyParams: map[string]interface{}{
            "threshold_type":  "absolute",
            "threshold_value": 2.0,
            "execution_size":  10.0,
        },
        ContextSize:     252,
        HorizonSize:     20,
        InitialCapital:  100000.0,
        InitialPosition: 0.0,
        InitialCash:     100000.0,
    }

    fmt.Printf("🚀 Starting Backtest Evaluation\n")
    fmt.Printf("Run ID:     %s\n", runID)
    fmt.Printf("Date Range: %s to %s (%d days)\n",
        startDate.Format("2006-01-02"),
        endDate.Format("2006-01-02"),
        int(endDate.Sub(startDate).Hours()/24))
    fmt.Printf("Tickers:    %d (%v)\n", len(tickers), getTickers(tickers))
    fmt.Printf("Models:     %d\n", len(models))
    fmt.Printf("Parallel:   %d tickers at a time\n", parallel)
    fmt.Printf("Context:    %d days\n", config.ContextSize)
    fmt.Printf("Horizon:    %d days\n", config.HorizonSize)
    fmt.Printf("\n")

    if os.Getenv("SAPHENEIA_TRADING_API_KEY") == "" {
        err := os.Setenv("SAPHENEIA_TRADING_API_KEY", "default_trading_api_key_please_change")
        if err != nil {
            return
        }
        slog.Warn("SAPHENEIA_TRADING_API_KEY not set, using default")
    }

    // Create evaluator
    evaluator, err := handlers.NewEvaluator()
    if err != nil {
        slog.Error("Failed to create evaluator", "error", err)
        return
    }
    defer evaluator.Close()

    // Run evaluation
    ctx := context.Background()
    if err := evaluator.RunEvaluation(ctx, config); err != nil {
        slog.Error("Evaluation failed", "error", err)
        return
    }

    fmt.Printf("\n✅ Evaluation completed successfully.\n")
    fmt.Printf("Results stored in InfluxDB measurements:\n")
    fmt.Printf("  - forecasts\n")
    fmt.Printf("  - trading_signals\n")
    fmt.Printf("  - portfolio_state\n")
    fmt.Printf("\nQuery example:\n")
    fmt.Printf("  ./aleutian query --run-id %s\n", runID)
}

func getTickers(tickers []datatypes.TickerInfo) []string {
    var names []string
    for _, t := range tickers {
        names = append(names, t.Ticker)
    }
    if len(names) > 5 {
        return append(names[:5], "...")
    }
    return names
}
```

**Example CLI usage after Phase 4:**

```bash
# Simple backtest: 1 ticker, 1 model, 10 years
./aleutian evaluate run \
  --ticker SPY \
  --model "google/timesfm-2.0-500m-pytorch" \
  --backtest-years 10

# Custom date range
./aleutian evaluate run \
  --ticker SPY \
  --start-date 2020-01-01 \
  --end-date 2024-12-31 \
  --model "google/timesfm-2.0-500m-pytorch"

# Multiple tickers, batched parallel
./aleutian evaluate run \
  --tickers SPY,QQQ,IWM \
  --model "google/timesfm-2.0-500m-pytorch" \
  --parallel 3 \
  --backtest-years 5

# All default tickers, all default models (WARNING: LONG RUNNING)
./aleutian evaluate run --backtest-years 10

# Skip data fetch if already loaded
./aleutian evaluate run \
  --ticker SPY \
  --model "google/timesfm-2.0-500m-pytorch" \
  --skip-fetch
```

---

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                   PHASE 1: Data Fetching                        │
│                                                                   │
│  CLI --ticker SPY --start-date 2014-01-01 --end-date 2024-12-31 │
│         ↓                                                         │
│  Evaluator.FetchHistoricalData()                                │
│         ↓                                                         │
│  HTTP POST localhost:8001/v1/data/fetch                         │
│         ↓                                                         │
│  [Data Service] → Yahoo Finance API → InfluxDB                  │
│         ↓                                                         │
│  Measurement: stock_prices (OHLCV data for 10 years)            │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                   PHASE 2: Trading Calendar                      │
│                                                                   │
│  Evaluator.GetTradingDays(SPY, 2014-01-01, 2024-12-31)         │
│         ↓                                                         │
│  Query InfluxDB for all dates with data                         │
│         ↓                                                         │
│  Returns: [2014-01-02, 2014-01-03, ..., 2024-12-30]            │
│            (~2,500 trading days)                                 │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│              PHASE 3: Rolling Window Forecasts                   │
│                   (LOOP: 2,500 iterations)                       │
│                                                                   │
│  For each day D in trading_days[252:]:  # Skip first 252 days   │
│                                                                   │
│    STEP 1: Read Historical Window                               │
│    ├─ GetHistoricalWindow(SPY, D, context=252)                  │
│    ├─ Query: stock_prices WHERE ticker=SPY                      │
│    │         AND time BETWEEN (D-252) AND D                     │
│    └─ Returns: [252 OHLCV data points]                          │
│                                                                   │
│    STEP 2: Generate Forecast                                    │
│    ├─ CallForecastService(SPY, timesfm-2.0, window, horizon=20) │
│    ├─ HTTP POST localhost:12210/v1/timeseries/forecast          │
│    └─ Returns: [20 forecast values]                             │
│                                                                   │
│    STEP 3: Store Forecast                                       │
│    ├─ StoreForecast(forecasts measurement)                      │
│    └─ Tags: ticker=SPY, model=timesfm-2.0, run_id=...          │
│                                                                   │
│    STEP 4: Generate Trading Signal                              │
│    ├─ currentPrice = window[251].Close                          │
│    ├─ forecastPrice = forecast[0]  # Day 1 prediction           │
│    ├─ CallTradingService(SPY, forecast, portfolio_state)        │
│    ├─ HTTP POST localhost:12132/trading/execute                 │
│    └─ Returns: {action: "BUY", size: 10, ...}                   │
│                                                                   │
│    STEP 5: Store Trading Signal                                 │
│    ├─ StoreTradingSignal(trading_signals measurement)           │
│    └─ Tags: ticker=SPY, action=BUY, strategy=threshold          │
│                                                                   │
│    STEP 6: Update Portfolio State                               │
│    ├─ portfolio.position += signal.size                         │
│    ├─ portfolio.cash -= signal.value                            │
│    └─ portfolio.value = position * price + cash                 │
│                                                                   │
│    STEP 7: Store Portfolio State                                │
│    ├─ StorePortfolioState(portfolio_state measurement)          │
│    └─ Fields: position, cash, value, return, drawdown           │
│                                                                   │
│  End loop                                                        │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                PHASE 4: Performance Metrics                      │
│                                                                   │
│  CalculatePerformanceMetrics(run_id)                            │
│         ↓                                                         │
│  Query portfolio_state for final metrics:                       │
│    - Sharpe Ratio                                                │
│    - Max Drawdown                                                │
│    - Total Return                                                │
│    - Win Rate                                                    │
│    - Average Trade Size                                          │
│         ↓                                                         │
│  Display summary to user                                         │
└─────────────────────────────────────────────────────────────────┘
```

---

## Storage Estimates

For a **10-year backtest** with **1 ticker** and **1 model**:

| Measurement | Records | Fields/Record | Approx Size |
|-------------|---------|---------------|-------------|
| `stock_prices` | 2,500 | 6 (OHLCV) | ~150 KB |
| `forecasts` | 2,248 | 80 (20×4) | ~18 MB |
| `trading_signals` | 2,248 | 8 | ~180 KB |
| `portfolio_state` | 2,248 | 10 | ~225 KB |
| **Total** | **9,244** | - | **~18.5 MB** |

For **10 tickers × 5 models × 10 years**:
- Total storage: ~925 MB
- Total records: ~462,000

**Retention policy recommendation:**
```flux
// Keep detailed data for 1 year
CREATE RETENTION POLICY "one_year" ON "financial-data" DURATION 365d REPLICATION 1

// Downsample to daily aggregates after 1 year
CREATE CONTINUOUS QUERY "downsample_portfolio" ON "financial-data"
BEGIN
  SELECT mean(portfolio_value) AS portfolio_value,
         mean(total_return) AS total_return,
         max(max_drawdown) AS max_drawdown
  INTO "financial-data"."one_year"."portfolio_state_daily"
  FROM "portfolio_state"
  GROUP BY time(1d), ticker, model, strategy_type, run_id
END
```

---

## Testing Strategy

### Unit Tests

```go
// handlers/evaluator_test.go

func TestStoreForecast(t *testing.T) {
    storage, _ := NewInfluxDBStorage()
    defer storage.Close()

    forecast := &ForecastData{
        Ticker: "SPY",
        Model: "google/timesfm-2.0-500m-pytorch",
        RunID: "test_123",
        GenerationDate: time.Now(),
        MeanForecasts: make([]float64, 20),
        ContextSize: 252,
        HorizonSize: 20,
    }

    err := storage.StoreForecast(context.Background(), forecast)
    assert.NoError(t, err)
}

func TestGetHistoricalWindow(t *testing.T) {
    storage, _ := NewInfluxDBStorage()
    defer storage.Close()

    // Assumes test data is loaded
    window, err := storage.GetHistoricalWindow(
        context.Background(),
        "SPY",
        time.Date(2024, 1, 15, 0, 0, 0, 0, time.UTC),
        252,
    )

    assert.NoError(t, err)
    assert.Equal(t, 252, len(window))
}
```

### Integration Tests

```bash
# 1. Load test data
./aleutian timeseries fetch SPY --days 3650

# 2. Run short backtest (1 month)
./aleutian evaluate run \
  --ticker SPY \
  --model "google/timesfm-2.0-500m-pytorch" \
  --start-date 2024-11-01 \
  --end-date 2024-12-01

# 3. Verify data in InfluxDB
influx query 'from(bucket:"financial-data")
  |> range(start: 2024-11-01, stop: 2024-12-01)
  |> filter(fn: (r) => r._measurement == "forecasts")
  |> count()'

# Should return ~22 trading days

# 4. Check portfolio state
influx query 'from(bucket:"financial-data")
  |> range(start: 2024-11-01, stop: 2024-12-01)
  |> filter(fn: (r) => r._measurement == "portfolio_state")
  |> filter(fn: (r) => r._field == "portfolio_value")
  |> last()'

# Should show final portfolio value
```

---

## Performance Optimizations

### 1. Batch InfluxDB Writes

Instead of writing each point individually, batch them:

```go
// Collect points in memory
var forecastPoints []*influxdb2.Point
var signalPoints []*influxdb2.Point
var portfolioPoints []*influxdb2.Point

// ... loop through days ...
forecastPoints = append(forecastPoints, forecastPoint)
signalPoints = append(signalPoints, signalPoint)
portfolioPoints = append(portfolioPoints, portfolioPoint)

// Write in batches of 100
if len(forecastPoints) >= 100 {
    for _, p := range forecastPoints {
        s.writeAPI.WritePoint(ctx, p)
    }
    forecastPoints = forecastPoints[:0]  // Reset
}
```

### 2. Forecast Service Caching

Add model caching to avoid reloading on every request:

```python
# In sapheneia forecast service
@lru_cache(maxsize=5)
def get_model(model_name: str):
    # Model stays loaded in memory
    return load_timesfm_model(model_name)
```

### 3. Parallel Model Evaluation

If evaluating multiple models for the same ticker, parallelize the forecast calls:

```go
var wg sync.WaitGroup
for _, model := range config.Models {
    wg.Add(1)
    go func(m string) {
        defer wg.Done()
        evaluateModel(ctx, ticker, m, tradingDays)
    }(model)
}
wg.Wait()
```

---

## Summary & Next Steps

Your flow **makes perfect sense** for a comprehensive backtesting framework. The current implementation is a great foundation, but needs these key enhancements:

1. ✅ **Historical rolling windows** instead of single-point evaluation
2. ✅ **Separate InfluxDB measurements** for forecasts, signals, and portfolio state
3. ✅ **Data fetching integration** as Phase 1
4. ✅ **Batched parallel execution** for efficiency (2-3 tickers)
5. ✅ **Portfolio state persistence** for analysis and resume capability

### Recommended Phased Approach

**Week 1: Phase 1** - Update InfluxDB schema and storage methods
**Week 2: Phase 2** - Add historical data readers and test with 1 month of data
**Week 3: Phase 3** - Refactor evaluation to rolling windows, test with 1 year
**Week 4: Phase 4** - Add CLI flags, parallel execution, run full 10-year backtest

### Quick Start (Minimal Viable Product)

If you want to start testing ASAP, implement just these 3 changes:

1. Add `GetHistoricalWindow()` to read context windows from InfluxDB
2. Modify `EvaluateTickerModel()` to loop through trading days
3. Update CLI to accept `--start-date` and `--end-date`

This gets you 80% of the functionality with 20% of the work.

---

## Appendix: Full Example End-to-End

```bash
# 1. Start services
cd /Users/jin/GolandProjects/AleutianLocal
podman-compose up -d

cd /Users/jin/PycharmProjects/sapheneia
docker-compose up -d

# 2. Run 10-year backtest
cd /Users/jin/GolandProjects/AleutianLocal
./aleutian evaluate run \
  --ticker SPY \
  --model "google/timesfm-2.0-500m-pytorch" \
  --backtest-years 10 \
  --parallel 1

# Expected output:
# 🚀 Starting Backtest Evaluation
# Run ID:     20250118_abc123
# Date Range: 2014-01-01 to 2024-12-31 (3,652 days)
# Tickers:    1 (SPY)
# Models:     1
# Parallel:   1 ticker at a time
# Context:    252 days
# Horizon:    20 days
#
# Phase 1: Fetching historical data
# ✓ Fetched SPY (3,652 days)
#
# Phase 2: Loaded trading calendar
# ✓ Total days: 2,520, After context: 2,268
#
# Phase 3: Running rolling window forecasts
# Progress: 500/2268 (22.0%)
# Progress: 1000/2268 (44.1%)
# Progress: 1500/2268 (66.1%)
# Progress: 2000/2268 (88.2%)
# ✓ Completed SPY/google/timesfm-2.0-500m-pytorch
#   Final return: 87.32%
#   Total trades: 156
#
# Phase 4: Calculating performance metrics
# ✓ Sharpe Ratio: 1.42
# ✓ Max Drawdown: -18.5%
#
# ✅ Evaluation completed successfully.
# Results stored in InfluxDB measurements:
#   - forecasts (2,268 records)
#   - trading_signals (2,268 records)
#   - portfolio_state (2,268 records)

# 3. Query results
influx query 'from(bucket:"financial-data")
  |> range(start: 2014-01-01)
  |> filter(fn: (r) => r._measurement == "portfolio_state")
  |> filter(fn: (r) => r._field == "portfolio_value")
  |> filter(fn: (r) => r.run_id == "20250118_abc123")'
```

---

**End of Integration Plan**
