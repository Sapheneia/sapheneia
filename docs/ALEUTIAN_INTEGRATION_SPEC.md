# Aleutian Integration Spec

**Date:** 2025-12-31
**Status:** Ready for Implementation
**Target:** AleutianLocal Go Codebase

---

## Overview

This spec defines the changes needed in Aleutian to integrate with Sapheneia's new unified inference API. The new API provides:

- Full request/response tracing via UUIDs
- Data provenance (source, period, timestamps)
- Standardized contracts across all model families

---

## New Endpoint

### `POST /orchestration/v1/predict`

**Replaces:** `/v1/timeseries/forecast` (deprecated but still working)

---

## Go Type Definitions

Add these to `services/orchestrator/datatypes/inference.go`:

```go
package datatypes

import "time"

// =============================================================================
// ENUMS
// =============================================================================

// Period represents the time frequency of data
type Period string

const (
    Period1m  Period = "1m"
    Period5m  Period = "5m"
    Period15m Period = "15m"
    Period30m Period = "30m"
    Period1h  Period = "1h"
    Period4h  Period = "4h"
    Period1d  Period = "1d"
    Period1w  Period = "1w"
    Period1M  Period = "1M"
)

// DataSource represents where the data originated
type DataSource string

const (
    SourceYahoo     DataSource = "yahoo"
    SourceAlpaca    DataSource = "alpaca"
    SourceBinance   DataSource = "binance"
    SourcePolygon   DataSource = "polygon"
    SourceCoinbase  DataSource = "coinbase"
    SourceKraken    DataSource = "kraken"
    SourceInfluxDB  DataSource = "influxdb"
    SourceSynthetic DataSource = "synthetic"
    SourceUnknown   DataSource = "unknown"
)

// DataField represents which OHLCV field the values are
type DataField string

const (
    FieldOpen     DataField = "open"
    FieldHigh     DataField = "high"
    FieldLow      DataField = "low"
    FieldClose    DataField = "close"
    FieldAdjClose DataField = "adj_close"
    FieldVolume   DataField = "volume"
)

// =============================================================================
// REQUEST STRUCTURES
// =============================================================================

// ContextData holds historical time-series data with full provenance
type ContextData struct {
    Values    []float64  `json:"values"`
    Period    Period     `json:"period"`
    Source    DataSource `json:"source"`
    StartDate string     `json:"start_date"` // YYYY-MM-DD
    EndDate   string     `json:"end_date"`   // YYYY-MM-DD
    Field     DataField  `json:"field"`
}

// HorizonSpec defines what to forecast
type HorizonSpec struct {
    Length int    `json:"length"`
    Period Period `json:"period"`
}

// ModelParams holds model-specific inference parameters
type ModelParams struct {
    NumSamples  int       `json:"num_samples,omitempty"`
    Temperature float64   `json:"temperature,omitempty"`
    TopK        int       `json:"top_k,omitempty"`
    TopP        float64   `json:"top_p,omitempty"`
    Quantiles   []float64 `json:"quantiles,omitempty"`
}

// InferenceRequest is the unified request for all forecasting models
type InferenceRequest struct {
    RequestID string    `json:"request_id"`
    Timestamp time.Time `json:"timestamp"`

    Ticker  string       `json:"ticker"`
    Model   string       `json:"model"`
    Context ContextData  `json:"context"`
    Horizon HorizonSpec  `json:"horizon"`
    Params  *ModelParams `json:"params,omitempty"`
}

// =============================================================================
// RESPONSE STRUCTURES
// =============================================================================

// ForecastData holds the forecast output
type ForecastData struct {
    Values    []float64 `json:"values"`
    Period    Period    `json:"period"`
    StartDate string    `json:"start_date"`
    EndDate   string    `json:"end_date"`
}

// ContextSummary echoes back what context was used
type ContextSummary struct {
    Length    int        `json:"length"`
    Period    Period     `json:"period"`
    Source    DataSource `json:"source"`
    StartDate string     `json:"start_date"`
    EndDate   string     `json:"end_date"`
    Field     DataField  `json:"field"`
}

// InferenceMetadata provides execution details
type InferenceMetadata struct {
    InferenceTimeMs int    `json:"inference_time_ms"`
    ModelVersion    string `json:"model_version,omitempty"`
    Device          string `json:"device,omitempty"`
    ModelFamily     string `json:"model_family,omitempty"`
}

// QuantileForecast holds a single quantile forecast
type QuantileForecast struct {
    Quantile float64   `json:"quantile"`
    Values   []float64 `json:"values"`
}

// InferenceResponse is the unified response from all forecasting models
type InferenceResponse struct {
    RequestID  string    `json:"request_id"`
    ResponseID string    `json:"response_id"`
    Timestamp  time.Time `json:"timestamp"`

    Ticker  string `json:"ticker"`
    Model   string `json:"model"`

    Forecast       ForecastData       `json:"forecast"`
    ContextSummary ContextSummary     `json:"context_summary"`
    Quantiles      []QuantileForecast `json:"quantiles,omitempty"`
    Metadata       InferenceMetadata  `json:"metadata"`
}
```

---

## Evaluator Changes

Update `services/orchestrator/handlers/evaluator.go`:

### New Helper Function

```go
import (
    "github.com/google/uuid"
)

// BuildInferenceRequest creates a new InferenceRequest with full metadata
func BuildInferenceRequest(
    ticker string,
    model string,
    contextData []float64,
    contextStartDate string,
    contextEndDate string,
    horizonLength int,
    source DataSource,
    period Period,
) datatypes.InferenceRequest {
    return datatypes.InferenceRequest{
        RequestID: uuid.New().String(),
        Timestamp: time.Now().UTC(),
        Ticker:    ticker,
        Model:     model,
        Context: datatypes.ContextData{
            Values:    contextData,
            Period:    period,
            Source:    source,
            StartDate: contextStartDate,
            EndDate:   contextEndDate,
            Field:     datatypes.FieldClose,
        },
        Horizon: datatypes.HorizonSpec{
            Length: horizonLength,
            Period: period,
        },
        Params: &datatypes.ModelParams{
            NumSamples:  20,
            Temperature: 1.0,
        },
    }
}
```

### Updated CallForecastServiceAsOf

```go
func (e *Evaluator) CallInferenceService(
    ctx context.Context,
    ticker, model string,
    contextData []float64,
    contextStartDate, contextEndDate string,
    horizonLength int,
    source datatypes.DataSource,
    period datatypes.Period,
) (*datatypes.InferenceResponse, error) {
    var result *datatypes.InferenceResponse

    err := retryWithBackoff(ctx, "inference", func() error {
        // Use new endpoint
        url := fmt.Sprintf("%s/orchestration/v1/predict", e.orchestrationURL)

        // Build request with full metadata
        request := BuildInferenceRequest(
            ticker, model, contextData,
            contextStartDate, contextEndDate,
            horizonLength, source, period,
        )

        reqBody, _ := json.Marshal(request)
        req, err := http.NewRequestWithContext(ctx, "POST", url, bytes.NewBuffer(reqBody))
        if err != nil {
            return err
        }
        req.Header.Set("Content-Type", "application/json")

        // Add API key
        apiKey := os.Getenv("SAPHENEIA_API_KEY")
        if apiKey != "" {
            req.Header.Set("Authorization", "Bearer "+apiKey)
        }

        resp, err := e.httpClient.Do(req)
        if err != nil {
            return err
        }
        defer resp.Body.Close()

        if resp.StatusCode != http.StatusOK {
            body, _ := io.ReadAll(resp.Body)
            if resp.StatusCode >= 400 && resp.StatusCode < 500 {
                return fmt.Errorf("inference error status %d: %s (not retryable)", resp.StatusCode, string(body))
            }
            return fmt.Errorf("inference error status %d: %s", resp.StatusCode, string(body))
        }

        result = &datatypes.InferenceResponse{}
        return json.NewDecoder(resp.Body).Decode(result)
    })

    return result, err
}
```

### Updated RunScenario

In the backtest loop, update how data is tracked:

```go
// Before calling inference, capture date range from fullHistory
contextStartDate := fullHistory.Time[sliceStart].Format("2006-01-02")
contextEndDate := fullHistory.Time[i].Format("2006-01-02")

// Determine data source (from scenario config or default)
source := datatypes.SourceInfluxDB  // We fetched from InfluxDB
period := datatypes.Period1d        // Daily data

// Call new inference service
response, err := e.CallInferenceService(
    ctx, ticker, model,
    contextSlice,
    contextStartDate, contextEndDate,
    scenario.Forecast.HorizonSize,
    source, period,
)
if err != nil {
    // handle error
}

// Use forecast from response
forecastValues := response.Forecast.Values

// Log with request/response IDs for tracing
slog.Info("Inference complete",
    "request_id", response.RequestID,
    "response_id", response.ResponseID,
    "inference_time_ms", response.Metadata.InferenceTimeMs,
    "forecast_len", len(forecastValues),
)
```

---

## Trading Signal Changes

Update `services/orchestrator/datatypes/trading.go`:

```go
// PriceInfo holds current and forecast prices with metadata
type PriceInfo struct {
    Current    float64    `json:"current"`
    Forecast   float64    `json:"forecast"`
    Period     Period     `json:"period"`
    Source     DataSource `json:"source"`
    AsOfDate   string     `json:"as_of_date"`
}

// InferenceRef links trading signal to its inference request
type InferenceRef struct {
    RequestID  string `json:"request_id"`
    ResponseID string `json:"response_id"`
}

// TradingSignalRequestV2 is the new trading signal request with full metadata
type TradingSignalRequestV2 struct {
    RequestID string    `json:"request_id"`
    Timestamp time.Time `json:"timestamp"`

    Ticker       string `json:"ticker"`
    StrategyType string `json:"strategy_type"`

    Prices    PriceInfo    `json:"prices"`
    Portfolio PortfolioState `json:"portfolio"`

    StrategyParams map[string]interface{} `json:"strategy_params"`

    // Link to inference that generated the forecast
    InferenceRef InferenceRef `json:"inference_ref"`
}

type PortfolioState struct {
    Position       float64 `json:"position"`
    Cash           float64 `json:"cash"`
    InitialCapital float64 `json:"initial_capital"`
}
```

---

## CLI Flag Changes

Update `cmd/aleutian/commands.go`:

```go
// Replace
forecastMode string // standalone/sapheneia

// With
computeMode string // standalone/distributed
```

Update `cmd/aleutian/cmd_stack.go`:

```go
case "standalone":
    config.Global.Compute.Mode = config.ComputeModeStandalone
    fmt.Println("Overriding compute mode to: standalone")
case "distributed":
    config.Global.Compute.Mode = config.ComputeModeDistributed
    fmt.Println("Overriding compute mode to: distributed")
```

---

## Environment Variables

Update environment variable names for clarity:

| Old | New | Purpose |
|-----|-----|---------|
| `ALEUTIAN_FORECAST_MODE` | `ALEUTIAN_COMPUTE_MODE` | standalone/distributed |
| `ALEUTIAN_TIMESERIES_TOOL` | `SAPHENEIA_ORCHESTRATION_URL` | Orchestration service URL |
| `SAPHENEIA_TRADING_SERVICE_URL` | `SAPHENEIA_TRADING_URL` | Trading service URL |

---

## Routing Changes

Update `services/orchestrator/handlers/timeseries.go`:

The `getServiceURL` function should route to `/orchestration/v1/predict` instead of `/v1/timeseries/forecast`:

```go
func getOrchestrationURL(computeMode string) string {
    if computeMode == "standalone" {
        // Local unified service
        url := os.Getenv("SAPHENEIA_ORCHESTRATION_URL")
        if url == "" {
            url = "http://forecast-service:8000"
        }
        return url
    }

    // Distributed mode - all go to same endpoint, model routing is internal
    url := os.Getenv("SAPHENEIA_ORCHESTRATION_URL")
    if url == "" {
        url = "http://sapheneia-orchestration:8000"
    }
    return url
}
```

---

## Migration Path

### Phase 1: Add New Code (Non-Breaking)
1. Add new type definitions to `datatypes/inference.go`
2. Add `CallInferenceService` method alongside existing `CallForecastService`
3. Add `--compute-mode` flag alongside `--forecast-mode`
4. Both old and new code paths work

### Phase 2: Switch to New API
1. Update `RunScenario` to use `CallInferenceService`
2. Update `EvaluateTickerModel` to use new API
3. Deprecate `--forecast-mode` flag (print warning, still works)

### Phase 3: Cleanup
1. Remove old `CallForecastService` method
2. Remove `--forecast-mode` flag
3. Remove legacy type definitions

---

## Testing

### Unit Test: InferenceRequest Serialization

```go
func TestInferenceRequestSerialization(t *testing.T) {
    req := datatypes.InferenceRequest{
        RequestID: "test-uuid",
        Timestamp: time.Now().UTC(),
        Ticker:    "SPY",
        Model:     "amazon/chronos-t5-tiny",
        Context: datatypes.ContextData{
            Values:    []float64{450.0, 451.2, 449.8},
            Period:    datatypes.Period1d,
            Source:    datatypes.SourceYahoo,
            StartDate: "2025-09-01",
            EndDate:   "2025-12-30",
            Field:     datatypes.FieldClose,
        },
        Horizon: datatypes.HorizonSpec{
            Length: 10,
            Period: datatypes.Period1d,
        },
    }

    body, err := json.Marshal(req)
    require.NoError(t, err)

    // Verify required fields present
    var parsed map[string]interface{}
    json.Unmarshal(body, &parsed)

    assert.Contains(t, parsed, "request_id")
    assert.Contains(t, parsed, "timestamp")
    assert.Contains(t, parsed, "context")
    assert.Contains(t, parsed, "horizon")
}
```

### Integration Test: End-to-End Inference

```go
func TestInferenceEndToEnd(t *testing.T) {
    // Start test server or use mock
    ctx := context.Background()

    evaluator, _ := NewEvaluator()
    defer evaluator.Close()

    response, err := evaluator.CallInferenceService(
        ctx,
        "SPY",
        "amazon/chronos-t5-tiny",
        []float64{450.0, 451.2, 449.8, 452.1, 453.5},
        "2025-09-01",
        "2025-12-30",
        10,
        datatypes.SourceYahoo,
        datatypes.Period1d,
    )

    require.NoError(t, err)
    assert.NotEmpty(t, response.RequestID)
    assert.NotEmpty(t, response.ResponseID)
    assert.Len(t, response.Forecast.Values, 10)
    assert.Equal(t, "SPY", response.Ticker)
}
```

---

## Example Request/Response

### Request

```json
{
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2025-12-31T14:30:00Z",
  "ticker": "SPY",
  "model": "amazon/chronos-t5-tiny",
  "context": {
    "values": [450.0, 451.2, 449.8, 452.1, 453.5],
    "period": "1d",
    "source": "yahoo",
    "start_date": "2025-09-01",
    "end_date": "2025-12-30",
    "field": "close"
  },
  "horizon": {
    "length": 10,
    "period": "1d"
  },
  "params": {
    "num_samples": 20,
    "temperature": 1.0
  }
}
```

### Response

```json
{
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "response_id": "660f9511-f30c-52e5-b827-557766551111",
  "timestamp": "2025-12-31T14:30:02Z",
  "ticker": "SPY",
  "model": "amazon/chronos-t5-tiny",
  "forecast": {
    "values": [452.1, 453.0, 451.8, 454.2, 455.0, 453.8, 456.1, 457.2, 455.9, 458.0],
    "period": "1d",
    "start_date": "2025-12-31",
    "end_date": "2026-01-13"
  },
  "context_summary": {
    "length": 5,
    "period": "1d",
    "source": "yahoo",
    "start_date": "2025-09-01",
    "end_date": "2025-12-30",
    "field": "close"
  },
  "metadata": {
    "inference_time_ms": 245,
    "model_version": "1.0.0",
    "device": "cuda:0",
    "model_family": "chronos"
  }
}
```

---

## Checklist for Implementation

- [ ] Create `datatypes/inference.go` with new type definitions
- [ ] Add `BuildInferenceRequest` helper function
- [ ] Implement `CallInferenceService` in evaluator
- [ ] Update `RunScenario` to use new API
- [ ] Add `--compute-mode` CLI flag
- [ ] Add new environment variables
- [ ] Update routing logic
- [ ] Write unit tests for serialization
- [ ] Write integration tests for end-to-end
- [ ] Update documentation
- [ ] Deprecate old code paths
