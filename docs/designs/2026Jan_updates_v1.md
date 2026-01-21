# Sapheneia-Aleutian Integration Updates - January 2026 v1

**Date:** 2026-01-20
**Status:** Design Complete, Ready for Implementation
**Scope:** Port migration, simulation storage, unified API

---

## Table of Contents

1. [Overview](#overview)
2. [Port Allocation](#port-allocation)
3. [Data Flow](#data-flow)
4. [Network Architecture](#network-architecture)
5. [Changes to Sapheneia](#changes-to-sapheneia)
6. [Changes to Aleutian](#changes-to-aleutian)
7. [New API Contract](#new-api-contract)
8. [Simulation Storage](#simulation-storage)
9. [Implementation Checklist](#implementation-checklist)

---

## Overview

This document outlines the January 2026 integration updates between Sapheneia (Python forecasting platform) and Aleutian (Go orchestration layer). Key changes:

1. **Port Migration**: Move from 8xxx ports to 127xx range to avoid collisions
2. **Unified API**: New `/orchestration/v1/predict` endpoint with request tracing
3. **Simulation Storage**: Partitioned storage for forecasts and backtests
4. **Centralized Configuration**: All ports defined in `.env` file

---

## Port Allocation

### Complete Port Mapping

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PORT ALLOCATION SCHEME                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ALEUTIAN PORTS (existing)          SAPHENEIA PORTS (new 127xx scheme)      │
│  ─────────────────────────          ──────────────────────────────────      │
│                                                                              │
│  12001  Data Fetcher                12700  Orchestration Gateway            │
│  12130  InfluxDB                    12701  Data Service                     │
│  12132  Trading API ◄───────────►  12702  Metrics API                      │
│  12210  Go Orchestrator                                                     │
│                                     12710  Chronos T5 Tiny                  │
│                                     12711  Chronos T5 Mini                  │
│                                     12712  Chronos T5 Small                 │
│                                     12713  Chronos T5 Base                  │
│                                     12714  Chronos T5 Large                 │
│                                                                              │
│                                     12715  Chronos Bolt Mini                │
│                                     12716  Chronos Bolt Small               │
│                                     12717  Chronos Bolt Base                │
│                                                                              │
│                                     12720  TimesFM 2.0                      │
│                                     12721  TimesFM 2.5                      │
│                                                                              │
│                                     12730  Moirai 1.0 Small                 │
│                                     12731  Moirai 1.0 Base                  │
│                                     12732  Moirai 1.0 Large                 │
│                                     12733  Moirai 1.1 Small                 │
│                                     12734  Moirai 1.1 Base                  │
│                                     12735  Moirai 1.1 Large                 │
│                                                                              │
│                                     12740  Granite TTM-R1                   │
│                                     12741  Granite TTM-R2                   │
│                                     12742  Granite FlowState                │
│                                     12743  Granite PatchTSMixer             │
│                                     12744  Granite PatchTST                 │
│                                                                              │
│                                     12750  Moment Small                     │
│                                     12751  Moment Base                      │
│                                     12752  Moment Large                     │
│                                                                              │
│                                     12760  Yinglong 6M                      │
│                                     12761  Yinglong 50M                     │
│                                     12762  Yinglong 110M                    │
│                                     12763  Yinglong 300M                    │
│                                                                              │
│                                     12770  Lag-Llama                        │
│                                     12771  Kairos                           │
│                                     12772  TimeMOE                          │
│                                     12773  Timer                            │
│                                     12774  Sundial                          │
│                                                                              │
│                                     12780  Web UI                           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Port Range Summary

| Range | Family | Services |
|-------|--------|----------|
| 12700-12709 | Core | Gateway (12700), Data (12701), Metrics (12702) |
| 12710-12719 | Chronos | T5 Tiny-Large (12710-12714), Bolt Mini-Base (12715-12717) |
| 12720-12729 | TimesFM | 2.0 (12720), 2.5 (12721) |
| 12730-12739 | Moirai | 1.0 (12730-12732), 1.1 (12733-12735) |
| 12740-12749 | Granite | TTM-R1/R2, FlowState, PatchTSMixer, PatchTST |
| 12750-12759 | Moment | Small, Base, Large |
| 12760-12769 | Yinglong | 6M, 50M, 110M, 300M |
| 12770-12779 | Other | Lag-Llama, Kairos, TimeMOE, Timer, Sundial |
| 12780 | UI | Web Interface |
| 12132 | Trading | Trading API (unchanged) |

### Why 127xx?

- Avoids common service ports (80, 443, 3000, 5000, 8000, 8080, 9000)
- Consistent with Aleutian's existing 12xxx scheme
- Groups all Sapheneia services in contiguous range
- Easy to remember: 127xx = Sapheneia forecast services

---

## Data Flow

### Request Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              REQUEST FLOW                                            │
└─────────────────────────────────────────────────────────────────────────────────────┘

  USER                    ALEUTIAN                         SAPHENEIA
  ────                    ────────                         ─────────

  ./aleutian timeseries
  forecast SPY
  --model chronos-t5-tiny
         │
         ▼
  ┌──────────────┐
  │   CLI        │
  │  (Go Binary) │
  └──────┬───────┘
         │
         ▼
  ┌──────────────────────────────────────┐
  │  Go Orchestrator (:12210)            │
  │  ┌────────────────────────────────┐  │
  │  │ timeseries.go                  │  │
  │  │ - Normalize model name         │  │
  │  │ - Resolve service URL          │  │
  │  │ - Inject InfluxDB history      │  │
  │  │ - Add auth headers             │  │
  │  └────────────────────────────────┘  │
  └──────────────┬───────────────────────┘
                 │
                 │  POST /v1/timeseries/forecast
                 │  or POST /orchestration/v1/predict
                 │
                 ▼
  ┌──────────────────────────────────────┐      ┌────────────────────────────┐
  │  Sapheneia Gateway (:12700)          │      │  Model Containers          │
  │  ┌────────────────────────────────┐  │      │                            │
  │  │ orchestration/router.py        │  │      │  forecast-chronos-t5-tiny  │
  │  │ - Parse model parameter        │──┼──────▶  (:12710)                  │
  │  │ - Route to model container     │  │      │                            │
  │  │ - Aggregate response           │  │      │  forecast-chronos-t5-base  │
  │  └────────────────────────────────┘  │      │  (:12713)                  │
  └──────────────────────────────────────┘      │                            │
                 │                              │  forecast-timesfm-2-0      │
                 │                              │  (:12720)                  │
                 ▼                              │                            │
  ┌──────────────────────────────────────┐      │  ...                       │
  │  Response                            │      └────────────────────────────┘
  │  {                                   │
  │    "request_id": "...",              │
  │    "forecast": [454.2, 455.0, ...],  │
  │    "metadata": {...}                 │
  │  }                                   │
  └──────────────────────────────────────┘
```

### Backtest Flow

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              BACKTEST FLOW                                           │
└─────────────────────────────────────────────────────────────────────────────────────┘

  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
  │  1. LOAD     │     │  2. FORECAST │     │  3. TRADE    │     │  4. STORE    │
  │  HISTORY     │────▶│  LOOP        │────▶│  SIGNALS     │────▶│  RESULTS     │
  └──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
         │                    │                    │                    │
         ▼                    ▼                    ▼                    ▼
  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
  │ InfluxDB     │     │ Sapheneia    │     │ Trading API  │     │ simulations/ │
  │ :12130       │     │ :12700       │     │ :12132       │     │ backtests/   │
  │              │     │              │     │              │     │ {run_id}/    │
  │ GET OHLC     │     │ POST predict │     │ POST execute │     │ summary.json │
  │ 2+ years     │     │ per day      │     │ per forecast │     │ trades.jsonl │
  └──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
```

---

## Network Architecture

### Container Network Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            aleutian-shared network                               │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│   ALEUTIAN CONTAINERS                      SAPHENEIA CONTAINERS                  │
│   ═══════════════════                      ════════════════════                  │
│                                                                                  │
│   ┌─────────────────────┐                  ┌─────────────────────────┐          │
│   │ aleutian-go-        │                  │ sapheneia-forecast      │          │
│   │ orchestrator        │─────────────────▶│ :8000 int / :12700 ext  │          │
│   │ :12210              │                  └───────────┬─────────────┘          │
│   └─────────────────────┘                              │                         │
│                                                        │                         │
│   ┌─────────────────────┐                  ┌───────────▼─────────────┐          │
│   │ user-influxdb       │                  │ Model Containers        │          │
│   │ :8086 int / :12130  │                  │                         │          │
│   └─────────────────────┘                  │ chronos-t5-tiny         │          │
│                                            │ :8000 int / :12710 ext  │          │
│   ┌─────────────────────┐                  │                         │          │
│   │ aleutian-data-      │                  │ chronos-t5-base         │          │
│   │ fetcher             │                  │ :8000 int / :12713 ext  │          │
│   │ :8001 int / :12001  │                  │                         │          │
│   └─────────────────────┘                  │ timesfm-2-0             │          │
│                                            │ :8000 int / :12720 ext  │          │
│   ┌─────────────────────┐                  │                         │          │
│   │ aleutian-jaeger     │                  │ ...                     │          │
│   │ :16686              │                  └─────────────────────────┘          │
│   └─────────────────────┘                                                       │
│                                            ┌─────────────────────────┐          │
│   ┌─────────────────────┐                  │ sapheneia-trading       │          │
│   │ aleutian-prometheus │                  │ :9000 int / :12132 ext  │          │
│   │ :9090               │                  └─────────────────────────┘          │
│   └─────────────────────┘                                                       │
│                                            ┌─────────────────────────┐          │
│   ┌─────────────────────┐                  │ sapheneia-data          │          │
│   │ aleutian-grafana    │                  │ :8000 int / :12701 ext  │          │
│   │ :3000               │                  └─────────────────────────┘          │
│   └─────────────────────┘                                                       │
│                                            ┌─────────────────────────┐          │
│                                            │ sapheneia-ui            │          │
│                                            │ :8080 int / :12780 ext  │          │
│                                            └─────────────────────────┘          │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘

Legend:
  :XXXX int  = Internal container port (container-to-container)
  :XXXXX ext = External host port (host machine access)
```

### Key Networking Points

1. **Internal ports stay at 8000** - All model containers listen on port 8000 internally
2. **External ports use 127xx** - Host machine accesses services via 127xx ports
3. **Container-to-container uses names** - `http://forecast-chronos-t5-tiny:8000`
4. **Single shared network** - All services on `aleutian-shared`

---

## Changes to Sapheneia

### Files to Modify

| File | Change Type | Description |
|------|-------------|-------------|
| `.env` | **UPDATE** | Update port values to 127xx scheme |
| `.env.template` | **DONE** | Already updated with new ports |
| `docker-compose.yml` | **UPDATE** | Change port mappings to use .env variables |
| `RUNBOOK.md` | **DONE** | Already updated |
| `forecast/core/config.py` | **UPDATE** | Read new port env vars |
| `orchestration/router.py` | **NEW/UPDATE** | Implement model routing |
| `orchestration/service.py` | **NEW/UPDATE** | Implement `/orchestration/v1/predict` |

### New Directory Structure

```
sapheneia/
├── simulations/                    ◄── NEW: Create this folder
│   ├── forecasts/                  ◄── NEW: Date/ticker/model partitioned
│   ├── backtests/                  ◄── NEW: Run outputs
│   ├── strategies/                 ◄── NEW: Strategy configs
│   ├── models/                     ◄── NEW: Model metadata
│   └── index/                      ◄── NEW: Search indices
│
├── .env                            ◄── UPDATE: New port scheme
├── .env.template                   ✓ DONE
├── docker-compose.yml              ◄── UPDATE: Port variables
├── RUNBOOK.md                      ✓ DONE
└── docs/designs/
    ├── aleutian_integration_v2.md  ✓ DONE
    └── 2026Jan_updates_v1.md       ✓ THIS FILE
```

### docker-compose.yml Changes

```yaml
# ═══════════════════════════════════════════════════════════════════════════
# BEFORE (hardcoded ports)
# ═══════════════════════════════════════════════════════════════════════════

services:
  forecast:
    ports:
      - "8000:8000"

  forecast-chronos-t5-tiny:
    ports:
      - "8100:8000"

  forecast-chronos-t5-base:
    ports:
      - "8103:8000"

  trading:
    ports:
      - "9000:9000"

  ui:
    ports:
      - "8080:8080"

# ═══════════════════════════════════════════════════════════════════════════
# AFTER (from .env variables)
# ═══════════════════════════════════════════════════════════════════════════

services:
  forecast:
    ports:
      - "${ORCHESTRATION_PORT:-12700}:8000"

  forecast-chronos-t5-tiny:
    ports:
      - "${CHRONOS_T5_TINY_PORT:-12710}:8000"

  forecast-chronos-t5-base:
    ports:
      - "${CHRONOS_T5_BASE_PORT:-12713}:8000"

  trading:
    ports:
      - "${TRADING_API_PORT:-12132}:9000"

  ui:
    ports:
      - "${UI_PORT:-12780}:8080"
```

### .env Configuration

```bash
# =============================================================================
# SAPHENEIA PORT CONFIGURATION (127xx range)
# =============================================================================

# Core Services
ORCHESTRATION_PORT=12700
DATA_API_PORT=12701
METRICS_PORT=12702

# Amazon Chronos T5 Series
CHRONOS_T5_TINY_PORT=12710
CHRONOS_T5_MINI_PORT=12711
CHRONOS_T5_SMALL_PORT=12712
CHRONOS_T5_BASE_PORT=12713
CHRONOS_T5_LARGE_PORT=12714

# Amazon Chronos Bolt Series
CHRONOS_BOLT_MINI_PORT=12715
CHRONOS_BOLT_SMALL_PORT=12716
CHRONOS_BOLT_BASE_PORT=12717

# Google TimesFM
TIMESFM_2_0_PORT=12720
TIMESFM_2_5_PORT=12721

# Salesforce Moirai
MOIRAI_1_1_SMALL_PORT=12733
MOIRAI_1_1_BASE_PORT=12734
MOIRAI_1_1_LARGE_PORT=12735

# IBM Granite
GRANITE_TTM_R1_PORT=12740
GRANITE_TTM_R2_PORT=12741

# AutoLab Moment
MOMENT_SMALL_PORT=12750
MOMENT_BASE_PORT=12751
MOMENT_LARGE_PORT=12752

# Alibaba Yinglong
YINGLONG_50M_PORT=12761

# Other Services
TRADING_API_PORT=12132
UI_PORT=12780
```

---

## Changes to Aleutian

### Files to Modify

| File | Change Type | Description |
|------|-------------|-------------|
| `services/orchestrator/handlers/timeseries.go` | **UPDATE** | Update port mappings for Sapheneia mode |
| `services/orchestrator/handlers/evaluator.go` | **UPDATE** | Add `CallInferenceService()` method |
| `services/orchestrator/datatypes/inference.go` | **NEW** | New unified request/response types |
| `podman-compose.timeseries.yml` | **UPDATE** | Update Sapheneia service references |
| `cmd/aleutian/commands.go` | **UPDATE** | Add `--compute-mode` flag |

### timeseries.go - No Internal Port Changes

```go
// ═══════════════════════════════════════════════════════════════════════════
// IMPORTANT: Internal routing stays the same!
// Container names unchanged, internal port still 8000
// Only EXTERNAL ports change (in docker-compose)
// ═══════════════════════════════════════════════════════════════════════════

func getServiceURL(normalizedModel string) string {
    switch normalizedModel {
    case "chronos-t5-tiny":
        return "http://forecast-chronos-t5-tiny:8000"  // ◄── SAME (internal)
    case "chronos-t5-mini":
        return "http://forecast-chronos-t5-mini:8000"  // ◄── SAME (internal)
    case "chronos-t5-small":
        return "http://forecast-chronos-t5-small:8000" // ◄── SAME (internal)
    case "chronos-t5-base":
        return "http://forecast-chronos-t5-base:8000"  // ◄── SAME (internal)
    case "chronos-t5-large":
        return "http://forecast-chronos-t5-large:8000" // ◄── SAME (internal)
    // ... etc
    }
}
```

### New datatypes/inference.go

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
    SourceInfluxDB  DataSource = "influxdb"
    SourceAlpaca    DataSource = "alpaca"
    SourceBinance   DataSource = "binance"
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

    Ticker string `json:"ticker"`
    Model  string `json:"model"`

    Forecast       ForecastData       `json:"forecast"`
    ContextSummary ContextSummary     `json:"context_summary"`
    Quantiles      []QuantileForecast `json:"quantiles,omitempty"`
    Metadata       InferenceMetadata  `json:"metadata"`
}
```

### evaluator.go - New Method

```go
import (
    "github.com/google/uuid"
)

// CallInferenceService calls the new unified predict endpoint
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
        request := datatypes.InferenceRequest{
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
            return fmt.Errorf("inference error status %d: %s", resp.StatusCode, string(body))
        }

        result = &datatypes.InferenceResponse{}
        return json.NewDecoder(resp.Body).Decode(result)
    })

    return result, err
}
```

### podman-compose.timeseries.yml

```yaml
# ═══════════════════════════════════════════════════════════════════════════
# No changes needed for container-to-container routing!
# ═══════════════════════════════════════════════════════════════════════════

services:
  orchestrator:
    environment:
      # Internal routing uses container names, not external ports
      ALEUTIAN_TIMESERIES_TOOL: http://sapheneia-forecast:8000
      SAPHENEIA_TRADING_SERVICE_URL: http://sapheneia-trading:9000
      SAPHENEIA_TRADING_API_KEY: ${SAPHENEIA_TRADING_API_KEY}
```

---

## New API Contract

### Unified Predict Endpoint

**Endpoint:** `POST /orchestration/v1/predict`

### Request Schema

```json
{
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2026-01-20T14:30:00Z",
  "ticker": "SPY",
  "model": "amazon/chronos-t5-tiny",
  "context": {
    "values": [450.0, 451.2, 449.8, 452.1, 453.5],
    "period": "1d",
    "source": "influxdb",
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

### Response Schema

```json
{
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "response_id": "660f9511-f30c-52e5-b827-557766551111",
  "timestamp": "2026-01-20T14:30:02Z",
  "ticker": "SPY",
  "model": "amazon/chronos-t5-tiny",
  "forecast": {
    "values": [454.2, 455.0, 453.8, 456.1, 457.2, 455.9, 458.0, 459.1, 457.8, 460.2],
    "period": "1d",
    "start_date": "2026-01-20",
    "end_date": "2026-02-01"
  },
  "context_summary": {
    "length": 5,
    "period": "1d",
    "source": "influxdb",
    "start_date": "2025-09-01",
    "end_date": "2025-12-30",
    "field": "close"
  },
  "quantiles": [
    {"quantile": 0.1, "values": [452.1, 452.8, ...]},
    {"quantile": 0.5, "values": [454.2, 455.0, ...]},
    {"quantile": 0.9, "values": [456.3, 457.2, ...]}
  ],
  "metadata": {
    "inference_time_ms": 245,
    "model_version": "1.0.0",
    "device": "cpu",
    "model_family": "chronos"
  }
}
```

### Legacy Endpoint (Maintained)

**Endpoint:** `POST /v1/timeseries/forecast`

Still works for backwards compatibility:

```json
// Request
{
  "name": "SPY",
  "model": "amazon/chronos-t5-tiny",
  "context_period_size": 252,
  "forecast_period_size": 10
}

// Response
{
  "name": "SPY",
  "forecast": [454.2, 455.0, 453.8, ...],
  "message": "Success"
}
```

---

## Simulation Storage

### Directory Structure

```
simulations/
├── forecasts/                           # Individual forecast results
│   └── {YYYY}/                          # Year partition
│       └── {MM}/                        # Month partition
│           └── {DD}/                    # Day partition
│               └── {ticker}/            # Asset symbol (SPY, AAPL)
│                   └── {model}/         # Model (chronos-t5-tiny)
│                       └── {version}/   # Model version
│                           ├── forecast_{request_id}.json
│                           └── metadata.json
│
├── backtests/                           # Backtest run outputs
│   └── {run_id}/                        # UUID run identifier
│       ├── config.json                  # BacktestScenario
│       ├── summary.json                 # Aggregate metrics
│       ├── trades.jsonl                 # Trade-by-trade log
│       ├── equity_curve.csv             # Portfolio value over time
│       └── forecasts/                   # All forecasts used
│           └── {date}_{ticker}_{request_id}.json
│
├── strategies/                          # Strategy configurations
│   └── {strategy_id}/
│       ├── config.json
│       ├── performance.json
│       └── backtests/                   # Links to runs
│           └── {run_id}.link
│
├── models/                              # Model metadata
│   └── {model_family}/
│       └── {variant}/
│           ├── metadata.json
│           ├── performance.json
│           └── versions/
│               └── {version}/
│                   └── metrics.json
│
└── index/                               # Quick lookup
    ├── by_ticker.json
    ├── by_model.json
    ├── by_date.json
    └── runs.json
```

### Forecast File Schema

```json
{
  "request_id": "550e8400-e29b-...",
  "response_id": "660f9511-f30c-...",
  "timestamp": "2026-01-20T14:30:02Z",
  "ticker": "SPY",
  "model": "amazon/chronos-t5-tiny",
  "model_version": "1.0.0",

  "context": {
    "values": [450.0, 451.2, 449.8, 452.1, 453.5],
    "period": "1d",
    "source": "influxdb",
    "start_date": "2025-09-01",
    "end_date": "2025-12-30",
    "field": "close"
  },

  "forecast": {
    "values": [454.2, 455.0, 453.8, 456.1, 457.2],
    "period": "1d",
    "start_date": "2026-01-20",
    "end_date": "2026-01-24"
  },

  "quantiles": [
    {"quantile": 0.1, "values": [452.1, 452.8, ...]},
    {"quantile": 0.5, "values": [454.2, 455.0, ...]},
    {"quantile": 0.9, "values": [456.3, 457.2, ...]}
  ],

  "metadata": {
    "inference_time_ms": 245,
    "device": "cpu",
    "model_family": "chronos"
  }
}
```

### Backtest Summary Schema

```json
{
  "run_id": "abc123-def456",
  "created_at": "2026-01-20T15:00:00Z",
  "completed_at": "2026-01-20T15:30:00Z",

  "config": {
    "ticker": "SPY",
    "model": "amazon/chronos-t5-tiny",
    "strategy_type": "threshold",
    "start_date": "2025-01-01",
    "end_date": "2025-12-31",
    "initial_capital": 100000.0,
    "context_size": 252,
    "horizon_size": 5
  },

  "performance": {
    "total_return": 0.1523,
    "sharpe_ratio": 1.45,
    "max_drawdown": -0.0812,
    "win_rate": 0.58,
    "total_trades": 156
  },

  "forecast_accuracy": {
    "mae": 2.34,
    "rmse": 3.12,
    "mape": 0.0156,
    "directional_accuracy": 0.62
  }
}
```

---

## Design Decisions (Resolved 2026-01-20)

### Model Naming Convention

**Decision:** Use full canonical model names with vendor prefix.

| Format | Example | Status |
|--------|---------|--------|
| Short name | `chronos-t5-tiny` | NOT RECOMMENDED |
| Full name | `amazon/chronos-t5-tiny` | REQUIRED |

**Rationale:**
- Avoids ambiguity between vendors
- Consistent with HuggingFace naming
- Matches Sapheneia's internal routing

### Request Validation

**Decision:** `InferenceRequest` includes a `Validate()` method for runtime validation.

**Validations Performed:**
- `request_id` is non-empty UUID
- `ticker` is non-empty and valid format
- `model` contains "/" (full name format)
- `context.values` is non-empty array
- `horizon.length > 0`
- `params.quantiles` all in [0, 1] if provided

**Example (Go):**
```go
req := &datatypes.InferenceRequest{
    RequestID: uuid.New().String(),
    Ticker:    "SPY",
    Model:     "amazon/chronos-t5-tiny",  // Full name required
    Context:   contextData,
    Horizon:   datatypes.HorizonSpec{Length: 10, Period: datatypes.Period1d},
}

if err := req.Validate(); err != nil {
    return fmt.Errorf("invalid request: %w", err)
}
```

**Example (Python - Sapheneia side):**
```python
def validate_inference_request(req: dict) -> None:
    """Validate incoming inference request."""
    if not req.get("request_id"):
        raise ValueError("request_id is required")
    if not req.get("model") or "/" not in req["model"]:
        raise ValueError("model must be full name (e.g., 'amazon/chronos-t5-tiny')")
    if not req.get("context", {}).get("values"):
        raise ValueError("context.values cannot be empty")
    if req.get("horizon", {}).get("length", 0) <= 0:
        raise ValueError("horizon.length must be positive")
```

### Empty Context Handling

**Decision:** Runtime validation (not compile-time).

**Rationale:**
- System-to-system communication
- Cannot enforce array length at compile time
- `Validate()` method catches this before network call

---

## Implementation Checklist

### Phase 1: Sapheneia Infrastructure

| # | Task | Status | Effort |
|---|------|--------|--------|
| 1 | Update `.env` with 127xx ports | DONE | Small |
| 2 | Update `docker-compose.yml` port variables | DONE | Small |
| 3 | Create `simulations/` directory structure | DONE | Small |
| 4 | Update `.env.template` | DONE | Small |
| 5 | Update `RUNBOOK.md` | DONE | Small |

### Phase 2: Sapheneia API

| # | Task | Status | Effort |
|---|------|--------|--------|
| 6 | Implement `/orchestration/v1/predict` endpoint | TODO | Medium |
| 7 | Add request_id/response_id to responses | TODO | Small |
| 8 | Implement simulation storage service | TODO | Medium |
| 9 | Add forecast persistence on inference | TODO | Small |

### Phase 3: Aleutian Integration

| # | Task | Status | Effort |
|---|------|--------|--------|
| 10 | Create `datatypes/inference.go` | DONE | Small |
| 11 | Implement `CallInferenceService()` in evaluator | DONE | Medium |
| 12 | Update `RunScenario` to use new API | TODO | Medium |
| 13 | Add `--compute-mode` CLI flag | TODO | Small |

### Phase 4: Testing & Documentation

| # | Task | Status | Effort |
|---|------|--------|--------|
| 14 | Unit tests for new type serialization | DONE | Small |
| 15 | Integration tests for end-to-end flow | TODO | Medium |
| 16 | Test backtest with simulation storage | TODO | Medium |
| 17 | Update CLI reference documentation | TODO | Small |

### No Changes Needed

- Internal container ports (stay at 8000)
- Container names (e.g., `forecast-chronos-t5-tiny`)
- Network name (`aleutian-shared`)
- Aleutian's timeseries.go routing logic (uses container names)

---

## Quick Reference

### Test Commands

```bash
# Start Sapheneia minimal
cd /Users/jin/PycharmProjects/sapheneia
podman-compose up -d forecast forecast-chronos-t5-tiny trading

# Health checks
curl http://localhost:12700/health  # Gateway
curl http://localhost:12710/health  # Chronos tiny
curl http://localhost:12132/health  # Trading

# Test from Aleutian
cd /Users/jin/GolandProjects/AleutianFOSS
./aleutian timeseries forecast SPY --model "amazon/chronos-t5-tiny" --context 90 --horizon 10
```

### Key Files

```
SAPHENEIA:
  /Users/jin/PycharmProjects/sapheneia/.env
  /Users/jin/PycharmProjects/sapheneia/.env.template
  /Users/jin/PycharmProjects/sapheneia/docker-compose.yml
  /Users/jin/PycharmProjects/sapheneia/RUNBOOK.md
  /Users/jin/PycharmProjects/sapheneia/docs/designs/2026Jan_updates_v1.md

ALEUTIAN:
  /Users/jin/GolandProjects/AleutianFOSS/services/orchestrator/handlers/timeseries.go
  /Users/jin/GolandProjects/AleutianFOSS/services/orchestrator/handlers/evaluator.go
  /Users/jin/GolandProjects/AleutianFOSS/services/orchestrator/datatypes/inference.go (NEW)
  /Users/jin/GolandProjects/AleutianFOSS/podman-compose.timeseries.yml
```
