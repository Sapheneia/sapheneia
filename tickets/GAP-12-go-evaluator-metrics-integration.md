# GAP-12: Go Evaluator Metrics Integration

**Priority:** HIGH
**Severity:** HIGH
**Category:** Architecture
**Effort:** 1-2 days
**Codebase:** AleutianFOSS (Go)
**Status:** ✅ IMPLEMENTED (2026-02-02)

---

## Architecture Review

### Reliability
- **Current Risk:** Backtest completes but no performance metrics are calculated
- **Mitigation:** Non-blocking metrics call - backtest completes even if metrics fails
- **Retry Strategy:** Use existing `retryWithBackoff` helper (3 retries with jitter)
- **Fallback:** Log warning, return zero metrics, backtest still succeeds

### Continuity
- **State Management:** Portfolio values tracked in-memory during loop
- **Persistence:** Metrics stored to InfluxDB after computation
- **Idempotency:** Same run produces same metrics - safe to recompute

### Integrity
- **Data Validation:** Validate portfolio values are positive, returns are bounded
- **Bounds Checking:** Cap extreme returns at [-1.0, 10.0] (same as Python client)
- **Schema Versioning:** Include schema version in InfluxDB measurement

### Optimization
- **Single Call:** Metrics service computes all 5 metrics in one request
- **Post-Loop:** Metrics computed once after loop, not per-iteration
- **Async Potential:** Could run metrics call in goroutine (future enhancement)

### Separation (Scalability)
- **Service Boundary:** Uses existing Sapheneia metrics service at port 12702
- **Interface Contract:** `POST /metrics/v1/compute/` with returns array
- **No Shared State:** Stateless computation, Go and Python independent

---

## Summary

The `aleutian evaluate run` Go CLI runs backtests but never calls the metrics service. The Python orchestration has metrics integration, but the Go CLI has its own backtest implementation that bypasses it. This ticket adds metrics integration directly to the Go evaluator.

## Current State

- Go CLI (`aleutian evaluate run`) runs full backtests
- Tracks `currentCash` and `currentPosition` during loop
- Stores results to InfluxDB (`forecast_evaluations` measurement)
- **No metrics calculation** - Sharpe, MaxDD, CAGR, etc. are never computed
- Metrics service exists at `localhost:12702` but is never called

## Expected Behavior

After backtest completes:
1. Calculate portfolio values for each day: `value = cash + position * price`
2. Convert portfolio values to returns: `return[i] = (value[i] - value[i-1]) / value[i-1]`
3. Call metrics service: `POST http://localhost:12702/metrics/v1/compute/`
4. Store metrics to InfluxDB under `backtest_metrics` measurement
5. Return metrics to CLI for display

```
┌─────────────────────────────────────────────────────────────────────┐
│                    BACKTEST FLOW WITH METRICS                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  RunScenario() -> (*MetricsResponse, error)                         │
│       │                                                             │
│       ├─► Data Fetch (InfluxDB)                                     │
│       │                                                             │
│       ├─► Parallel Forecast Loop ──► Sapheneia Forecast Service     │
│       │                                                             │
│       ├─► Sequential Trading Loop ──► Sapheneia Trading Service     │
│       │       │                                                     │
│       │       └─► Track portfolioValues[] each iteration            │
│       │                                                             │
│       ├─► Convert portfolioValues to returns[]                      │
│       │                                                             │
│       ├─► CallMetricsService(returns) ──► Sapheneia Metrics         │
│       │                                                             │
│       ├─► StoreMetrics(metrics) ──► InfluxDB                        │
│       │                                                             │
│       └─► Return (*MetricsResponse, nil)                            │
│                                                                     │
│  cmd_evaluation.go                                                  │
│       │                                                             │
│       └─► Display metrics table to user                             │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## Acceptance Criteria

- [x] Add `MetricsResponse` type to `datatypes/evaluator.go`
- [x] Add `metricsServiceURL` field to Evaluator struct
- [x] Initialize metrics URL in `NewEvaluator()` with env var support
- [x] Add deployment mode URL configuration in `cmd_evaluation.go`
- [x] Implement `CallMetricsService()` using existing `retryWithBackoff` helper
- [x] Implement `portfolioValuesToReturns()` helper function
- [x] Track portfolio values during backtest loop
- [x] Change `RunScenario` signature to return `(*datatypes.MetricsResponse, error)`
- [x] Update `cmd_evaluation.go` to handle new return type and display metrics
- [x] Store metrics to InfluxDB `backtest_metrics` measurement
- [x] Handle metrics service unavailability gracefully (non-blocking)

---

## Implementation

### File: `services/orchestrator/datatypes/evaluator.go`

#### 1. Add MetricsResponse type (after TradingSignalResponse, ~line 64)

```go
// MetricsResponse contains computed performance metrics from the metrics service.
type MetricsResponse struct {
	SharpeRatio float64 `json:"sharpe_ratio"`
	MaxDrawdown float64 `json:"max_drawdown"`
	CAGR        float64 `json:"cagr"`
	CalmarRatio float64 `json:"calmar_ratio"`
	WinRate     float64 `json:"win_rate"`
}
```

---

### File: `services/orchestrator/handlers/evaluator.go`

#### 2. Add metricsRequest type and update Evaluator struct (~line 50)

```go
// metricsRequest is the request payload for the metrics service.
type metricsRequest struct {
	Returns        []float64 `json:"returns"`
	Metric         string    `json:"metric"`
	RiskFreeRate   float64   `json:"risk_free_rate"`
	PeriodsPerYear int       `json:"periods_per_year"`
}

// Evaluator handles the logic of running forecasts and checking trading signals
type Evaluator struct {
	httpClient        *http.Client
	orchestratorURL   string
	tradingServiceURL string
	metricsServiceURL string  // NEW
	storage           *InfluxDBStorage
}
```

#### 3. Update NewEvaluator() (~line 68)

```go
func NewEvaluator() (*Evaluator, error) {
	orchestratorURL := os.Getenv("ORCHESTRATOR_URL")
	if orchestratorURL == "" {
		orchestratorURL = "http://localhost:12210"
	}

	tradingURL := os.Getenv("SAPHENEIA_TRADING_SERVICE_URL")
	if tradingURL == "" {
		tradingURL = "http://localhost:12132"
	}

	// NEW: Metrics service URL
	metricsURL := os.Getenv("SAPHENEIA_METRICS_SERVICE_URL")
	if metricsURL == "" {
		metricsURL = "http://localhost:12702"
	}

	storage, err := NewInfluxDBStorage()
	if err != nil {
		return nil, fmt.Errorf("failed to create storage: %w", err)
	}

	return &Evaluator{
		httpClient:        &http.Client{Timeout: 5 * time.Minute},
		orchestratorURL:   orchestratorURL,
		tradingServiceURL: tradingURL,
		metricsServiceURL: metricsURL,  // NEW
		storage:           storage,
	}, nil
}
```

#### 4. Add helper function for returns calculation (after retryWithBackoff, ~line 712)

```go
// portfolioValuesToReturns converts a series of portfolio values to period returns.
// Returns are capped to [-1.0, 10.0] to handle extreme values.
func portfolioValuesToReturns(values []float64) []float64 {
	if len(values) < 2 {
		return []float64{}
	}

	returns := make([]float64, 0, len(values)-1)
	for i := 1; i < len(values); i++ {
		if values[i-1] <= 0 {
			returns = append(returns, 0.0)
			continue
		}
		ret := (values[i] - values[i-1]) / values[i-1]
		// Cap extreme returns (same bounds as Python MetricsClient)
		if ret < -1.0 {
			ret = -1.0
		} else if ret > 10.0 {
			ret = 10.0
		}
		returns = append(returns, ret)
	}
	return returns
}
```

#### 5. Add CallMetricsService method (after CallTradingService, ~line 983)

```go
// CallMetricsService sends portfolio returns to the metrics service and returns computed metrics.
// Uses the existing retryWithBackoff helper for consistency.
// This is a non-blocking operation - errors are logged but don't fail the backtest.
func (e *Evaluator) CallMetricsService(ctx context.Context, returns []float64, runID string) (*datatypes.MetricsResponse, error) {
	if len(returns) < 2 {
		slog.Warn("Insufficient returns data for metrics", "count", len(returns))
		return &datatypes.MetricsResponse{}, nil
	}

	url := fmt.Sprintf("%s/metrics/v1/compute/", e.metricsServiceURL)

	reqBody := metricsRequest{
		Returns:        returns,
		Metric:         "all",
		RiskFreeRate:   0.0,
		PeriodsPerYear: 252,
	}

	body, err := json.Marshal(reqBody)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal metrics request: %w", err)
	}

	var result datatypes.MetricsResponse

	err = retryWithBackoff(ctx, "metrics_service", func() error {
		httpReq, err := http.NewRequestWithContext(ctx, "POST", url, bytes.NewBuffer(body))
		if err != nil {
			return fmt.Errorf("failed to create metrics request: %w", err)
		}
		httpReq.Header.Set("Content-Type", "application/json")
		httpReq.Header.Set("X-Run-ID", runID)

		resp, err := e.httpClient.Do(httpReq)
		if err != nil {
			return err
		}

		// Read and close body immediately to avoid leaks on retry
		respBody, readErr := io.ReadAll(resp.Body)
		closeErr := resp.Body.Close()
		if closeErr != nil {
			slog.Debug("Failed to close response body", "error", closeErr)
		}

		if readErr != nil {
			return fmt.Errorf("failed to read response: %w", readErr)
		}

		if resp.StatusCode != http.StatusOK {
			return fmt.Errorf("metrics service returned %d: %s", resp.StatusCode, string(respBody))
		}

		if err := json.Unmarshal(respBody, &result); err != nil {
			return fmt.Errorf("failed to decode metrics response: %w", err)
		}

		return nil
	})

	if err != nil {
		return nil, err
	}

	slog.Info("Metrics computed successfully",
		"sharpe_ratio", fmt.Sprintf("%.3f", result.SharpeRatio),
		"max_drawdown", fmt.Sprintf("%.2f%%", result.MaxDrawdown*100),
		"cagr", fmt.Sprintf("%.2f%%", result.CAGR*100),
		"win_rate", fmt.Sprintf("%.1f%%", result.WinRate*100))

	return &result, nil
}
```

#### 6. Update RunScenario signature and add portfolio tracking (~line 261)

**Change function signature:**

```go
// RunScenario executes a backtest based on the YAML scenario file.
// Returns computed metrics on success, or nil metrics with error on failure.
func (e *Evaluator) RunScenario(ctx context.Context, scenario *datatypes.BacktestScenario, runID string) (*datatypes.MetricsResponse, error) {
```

**Add portfolio tracking after initializing portfolio state (~line 494):**

```go
	// 4. Initialize Portfolio
	currentPosition := scenario.Trading.InitialPosition
	currentCash := scenario.Trading.InitialCash

	// NEW: Track portfolio values for metrics calculation
	// Pre-allocate slice with capacity for all iterations + initial value
	portfolioValues := make([]float64, 0, endIndex-startIndex+2)

	// Record initial portfolio value BEFORE trading begins
	initialValue := currentCash + currentPosition*fullHistory.Close[startIndex]
	portfolioValues = append(portfolioValues, initialValue)

	// 5. Sequential trading loop using pre-fetched forecasts
	for i := startIndex; i <= endIndex; i++ {
		// ... existing loop code through state update ...

		// Update State
		currentPosition = signal.PositionAfter
		currentCash = signal.AvailableCash

		// NEW: Track portfolio value AFTER trade execution
		portfolioValue := currentCash + currentPosition*currentSimulatedPrice
		portfolioValues = append(portfolioValues, portfolioValue)

		// ... rest of existing loop (StoreResult, Progress log) ...
	}
```

#### 7. Add metrics computation after loop (~line 579, before return)

**Replace the existing return statement:**

```go
	}  // end of trading loop

	// --- Compute and Store Performance Metrics ---
	slog.Info("Computing performance metrics", "portfolio_values", len(portfolioValues))

	returns := portfolioValuesToReturns(portfolioValues)

	metrics, err := e.CallMetricsService(ctx, returns, runID)
	if err != nil {
		// Non-blocking: log warning but don't fail the backtest
		slog.Warn("Metrics calculation failed", "error", err)
		// Return zero metrics instead of nil
		metrics = &datatypes.MetricsResponse{}
	} else {
		// Store metrics to InfluxDB
		if err := e.storage.StoreMetrics(ctx, runID, ticker, scenario.Forecast.Model, metrics); err != nil {
			slog.Error("Failed to store metrics to InfluxDB", "error", err)
			// Continue - metrics are still returned to caller
		}
	}

	return metrics, nil
}
```

#### 8. Add StoreMetrics method to InfluxDBStorage (~line 1432, after StoreResult)

```go
// StoreMetrics writes backtest performance metrics to InfluxDB.
func (s *InfluxDBStorage) StoreMetrics(ctx context.Context, runID, ticker, model string, metrics *datatypes.MetricsResponse) error {
	if metrics == nil {
		return nil
	}

	p := influxdb2.NewPointWithMeasurement("backtest_metrics").
		AddTag("run_id", runID).
		AddTag("ticker", ticker).
		AddTag("model", model).
		AddField("sharpe_ratio", metrics.SharpeRatio).
		AddField("max_drawdown", metrics.MaxDrawdown).
		AddField("cagr", metrics.CAGR).
		AddField("calmar_ratio", metrics.CalmarRatio).
		AddField("win_rate", metrics.WinRate).
		SetTime(time.Now())

	if err := s.writeAPI.WritePoint(ctx, p); err != nil {
		return fmt.Errorf("failed to write metrics to InfluxDB: %w", err)
	}

	slog.Info("Metrics stored to InfluxDB",
		"run_id", runID,
		"measurement", "backtest_metrics")

	return nil
}
```

---

### File: `cmd/aleutian/cmd_evaluation.go`

#### 9. Add metrics service URL to deployment mode configuration (~line 102, after trading URL)

```go
		// Set trading URL based on deployment mode if not already set
		if os.Getenv("SAPHENEIA_TRADING_URL") == "" {
			switch evalDeploymentMode {
			case "standalone":
				_ = os.Setenv("SAPHENEIA_TRADING_URL", "http://localhost:12132")
			case "distributed":
				_ = os.Setenv("SAPHENEIA_TRADING_URL", "http://sapheneia-trading:8000")
			}
		}

		// NEW: Set metrics URL based on deployment mode if not already set
		if os.Getenv("SAPHENEIA_METRICS_SERVICE_URL") == "" {
			switch evalDeploymentMode {
			case "standalone":
				_ = os.Setenv("SAPHENEIA_METRICS_SERVICE_URL", "http://localhost:12702")
			case "distributed":
				_ = os.Setenv("SAPHENEIA_METRICS_SERVICE_URL", "http://sapheneia-metrics:8000")
			}
		}
	}
```

#### 10. Update RunScenario call and display metrics (~line 151)

```go
	// 6. Execute the Run using RunScenario
	ctx := context.Background()
	metrics, err := evaluator.RunScenario(ctx, scenario, runID)
	if err != nil {
		slog.Error("Evaluation failed", "error", err)
		return
	}

	fmt.Printf("\n✅ Evaluation completed successfully.\n")
	fmt.Printf("   Run ID: %s\n", runID)

	// NEW: Display performance metrics
	if metrics != nil && (metrics.SharpeRatio != 0 || metrics.MaxDrawdown != 0) {
		fmt.Println()
		fmt.Println("═══════════════════════════════════════════════════════════════")
		fmt.Println("                     PERFORMANCE METRICS                        ")
		fmt.Println("═══════════════════════════════════════════════════════════════")
		fmt.Printf("  Sharpe Ratio:    %8.3f\n", metrics.SharpeRatio)
		fmt.Printf("  Max Drawdown:    %8.2f%%\n", metrics.MaxDrawdown*100)
		fmt.Printf("  CAGR:            %8.2f%%\n", metrics.CAGR*100)
		fmt.Printf("  Calmar Ratio:    %8.3f\n", metrics.CalmarRatio)
		fmt.Printf("  Win Rate:        %8.1f%%\n", metrics.WinRate*100)
		fmt.Println("═══════════════════════════════════════════════════════════════")
	}
}
```

---

## InfluxDB Schema

### Measurement: `backtest_metrics`

| Type | Name | Description |
|------|------|-------------|
| Tag | run_id | Unique backtest run identifier |
| Tag | ticker | Stock symbol (e.g., SPY) |
| Tag | model | Model name (e.g., amazon/chronos-t5-tiny) |
| Field | sharpe_ratio | Risk-adjusted return (float) |
| Field | max_drawdown | Maximum peak-to-trough decline (float, negative) |
| Field | cagr | Compound Annual Growth Rate (float) |
| Field | calmar_ratio | CAGR / MaxDrawdown (float) |
| Field | win_rate | Percentage of positive returns (float, 0-1) |
| Time | timestamp | When metrics were computed |

### Query Examples

**Get metrics for a specific run:**
```flux
from(bucket: "financial-data")
  |> range(start: -30d)
  |> filter(fn: (r) => r._measurement == "backtest_metrics")
  |> filter(fn: (r) => r.run_id == "spy-chronos-t5-tiny_v1.0.0_20260202_190045")
  |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
```

**Compare metrics across models:**
```flux
from(bucket: "financial-data")
  |> range(start: -30d)
  |> filter(fn: (r) => r._measurement == "backtest_metrics")
  |> filter(fn: (r) => r.ticker == "SPY")
  |> filter(fn: (r) => r._field == "sharpe_ratio")
  |> group(columns: ["model"])
  |> last()
```

---

## Environment Variables

| Variable | Default (standalone) | Default (distributed) | Description |
|----------|---------------------|----------------------|-------------|
| `SAPHENEIA_METRICS_SERVICE_URL` | `http://localhost:12702` | `http://sapheneia-metrics:8000` | Metrics service endpoint |

---

## Test Cases

**File:** `services/orchestrator/handlers/evaluator_test.go`

### 1. TestPortfolioValuesToReturns
```go
func TestPortfolioValuesToReturns(t *testing.T) {
	tests := []struct {
		name     string
		values   []float64
		expected []float64
	}{
		{"normal", []float64{100, 110, 105}, []float64{0.1, -0.0454545}},
		{"empty", []float64{}, []float64{}},
		{"single", []float64{100}, []float64{}},
		{"zero_value", []float64{100, 0, 50}, []float64{-1.0, 0.0}},
		{"extreme_gain", []float64{100, 1500}, []float64{10.0}}, // capped
		{"extreme_loss", []float64{100, -50}, []float64{-1.0}},  // capped
	}
	// ... implementation
}
```

### 2. TestCallMetricsService_Success
```go
func TestCallMetricsService_Success(t *testing.T) {
	// Mock HTTP server returning valid metrics
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		json.NewEncoder(w).Encode(datatypes.MetricsResponse{
			SharpeRatio: 1.5,
			MaxDrawdown: -0.15,
			CAGR:        0.12,
			CalmarRatio: 0.8,
			WinRate:     0.55,
		})
	}))
	defer server.Close()
	// ... test implementation
}
```

### 3. TestCallMetricsService_Unavailable
```go
func TestCallMetricsService_Unavailable(t *testing.T) {
	// Mock server that always returns 500
	// Verify retries occur and error is returned
}
```

### 4. TestRunScenario_WithMetrics (Integration)
```go
func TestRunScenario_WithMetrics(t *testing.T) {
	// Full integration test with mock services
	// Verify metrics are computed and stored
}
```

---

## Dependencies

- GAP-01: Metrics service must be running (COMPLETED - service exists)
- docker-compose.yml: Metrics service uncommented (DONE)
- Network: Metrics service reachable from evaluator

## Files Changed

**AleutianFOSS:**
| File | Changes |
|------|---------|
| `services/orchestrator/datatypes/evaluator.go` | Add `MetricsResponse` type |
| `services/orchestrator/handlers/evaluator.go` | Add metrics integration (struct, methods, loop tracking) |
| `cmd/aleutian/cmd_evaluation.go` | Update `RunScenario` call, add metrics display, add env var config |

**Sapheneia:**
| File | Changes |
|------|---------|
| `metrics/routes/endpoints.py` | None (existing, no changes needed) |
| `docker-compose.yml` | Metrics service already enabled |

## Rollback Plan

If metrics integration causes issues:
1. Revert `RunScenario` signature to return only `error`
2. Remove metrics call and storage
3. Keep `portfolioValuesToReturns` helper (useful for future)

The backtest functionality remains unchanged - metrics is additive.
