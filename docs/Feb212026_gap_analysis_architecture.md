# GAP Analysis Architecture Document

**Date:** 2026-02-21
**Scope:** GAP-12 through GAP-16 implementation summary
**Codebases:** Sapheneia (Python/Go) + AleutianFOSS (Go)

---

## 1. Overall System Architecture (Post-GAP)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ALEUTIAN FOSS (Go)                                  │
│                    /Users/jin/GolandProjects/AleutianFOSS                   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  CLI (cmd/)                                                         │    │
│  │  $ aleutian eval --scenario strategies/spy_threshold_v1.yaml        │    │
│  └──────────────┬──────────────────────────────────────────────────────┘    │
│                 │                                                            │
│                 ▼                                                            │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  Evaluator (handlers/evaluator.go)                                  │    │
│  │                                                                     │    │
│  │  RunScenario()                                                      │    │
│  │  ├── EnsureDataAvailability() ─── reads/writes ──► InfluxDB         │    │
│  │  ├── fetchOHLCFromInfluxByDateRange() ◄────────── InfluxDB          │    │
│  │  ├── parallelForecastFetch() ─────────────────► Sapheneia Forecast  │    │
│  │  ├── CallTradingService() ────────────────────► Sapheneia Trading   │    │
│  │  ├── CallMetricsService() ────────────────────► Sapheneia Metrics   │    │ GAP-12
│  │  │                                                                  │    │
│  │  │  NEW (GAP-16): InfluxDB intermediate writes                      │    │
│  │  ├── StoreForecast()      ────────────────────► InfluxDB            │    │
│  │  ├── StoreTradingSignal() ────────────────────► InfluxDB            │    │
│  │  ├── StorePortfolioState()────────────────────► InfluxDB            │    │
│  │  ├── StoreResult()        ────────────────────► InfluxDB            │    │
│  │  └── StoreMetrics()       ────────────────────► InfluxDB            │    │ GAP-12
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
        │               │               │
        │ HTTP          │ HTTP          │ HTTP
        ▼               ▼               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        SAPHENEIA (Python/Go)                                │
│                    /Users/jin/PycharmProjects/sapheneia                     │
│                                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │  Forecast     │  │  Trading     │  │  Metrics     │  │  Data        │   │
│  │  Gateway      │  │  Service     │  │  Service     │  │  Service     │   │
│  │  :12700       │  │  :12132      │  │  :12702      │  │  :12701      │   │
│  │              │  │              │  │              │  │  (Go)        │   │
│  │  + Model     │  │              │  │              │  │              │   │
│  │  Containers  │  │              │  │              │  │              │   │
│  │  :12710-12721│  │              │  │              │  │              │   │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Backtest Data Flow (RunScenario)

This is the main backtest loop — the core business logic of the system.

```
RunScenario(scenario, runID)
│
│  PHASE 1: DATA PREPARATION
│  ┌──────────────────────────────────────────────────────┐
│  │ EnsureDataAvailability(scenario)                      │
│  │   │                                                   │
│  │   ├── CheckDataCoverage(ticker)  ◄── InfluxDB query   │
│  │   │   "Do we have SPY data from 2024-01-01 to now?"  │
│  │   │                                                   │
│  │   └── FetchMissingData(ticker, start, end)            │
│  │       POST http://data-service:12701/v1/data/fetch    │
│  │       { names: ["SPY"], start_date, end_date }        │
│  │       Data service fetches Yahoo Finance → InfluxDB   │
│  │                                                       │
│  │ fetchOHLCFromInfluxByDateRange(ticker, start, end)    │
│  │   Returns: fullHistory {Close[], Time[], Open[]...}   │
│  └──────────────────────────────────────────────────────┘
│
│  PHASE 2: PARALLEL FORECAST FETCH
│  ┌──────────────────────────────────────────────────────┐
│  │ For each trading day [startIndex..endIndex]:          │
│  │   Spawn goroutine → CallInferenceService()           │
│  │                                                       │
│  │   POST http://sapheneia:12700                         │
│  │        /orchestration/v1/predict         (unified)    │
│  │   — OR —                                              │
│  │   POST http://sapheneia:12700                         │
│  │        /v1/timeseries/forecast           (legacy)     │
│  │                                                       │
│  │   Request:                                            │
│  │   { ticker: "SPY",                                    │
│  │     model: "amazon/chronos-t5-tiny",                  │
│  │     context: { values: [148.2, 149.1, ...],           │
│  │                period: "1d", source: "influxdb" },    │
│  │     horizon: { length: 20, period: "1d" } }           │
│  │                                                       │
│  │   Response:                                           │
│  │   { forecast: { values: [150.3, 151.1, ...] },        │
│  │     metadata: { inference_time_ms: 245,               │
│  │                 device: "cpu", model_family: "chronos"│
│  │     },                                                │
│  │     quantiles: [{q: 0.1, values: [...]},              │
│  │                 {q: 0.9, values: [...]}] }            │
│  │                                                       │
│  │   → Collected into forecasts map[int]forecastResult   │
│  └──────────────────────────────────────────────────────┘
│
│  PHASE 3: SEQUENTIAL TRADING LOOP
│  ┌──────────────────────────────────────────────────────────────────┐
│  │ for i := startIndex; i <= endIndex; i++ {                        │
│  │                                                                  │
│  │   fr := forecasts[i]                                             │
│  │   predictedPrice := fr.output.Values[0]   // 1-day ahead        │
│  │   currentPrice := fullHistory.Close[i]                           │
│  │                                                                  │
│  │   ┌─ NEW (GAP-16): StoreForecast ────────────────────────────┐  │
│  │   │ POST → InfluxDB "forecasts" measurement                  │  │
│  │   │ tags: run_id, ticker, model, model_family, schema_version│  │
│  │   │ fields: forecast_price, current_price, horizon,           │  │
│  │   │         inference_time_ms, confidence_lower/upper         │  │
│  │   │ time: evaluation date                                     │  │
│  │   └──────────────────────────────────────────────────────────┘  │
│  │                                                                  │
│  │   ── CallTradingService() ─────────────────────────────────────  │
│  │   POST http://sapheneia-trading:12132/trading/execute            │
│  │   { ticker: "SPY", strategy_type: "threshold",                  │
│  │     forecast_price: 150.3, current_price: 148.5,                │
│  │     current_position: 0, available_cash: 10000,                 │
│  │     initial_capital: 10000, threshold_value: 0.02 }             │
│  │                                                                  │
│  │   Response:                                                      │
│  │   { action: "buy", size: 10, value: 1485,                       │
│  │     reason: "Forecast exceeds threshold",                        │
│  │     available_cash: 8515, position_after: 10, stopped: false }  │
│  │                                                                  │
│  │   ┌─ NEW (GAP-16): StoreTradingSignal ───────────────────────┐  │
│  │   │ POST → InfluxDB "trading_signals" measurement             │  │
│  │   │ tags: run_id, ticker, strategy_type, action, schema_ver   │  │
│  │   │ fields: forecast_price, current_price,                    │  │
│  │   │   position_before=0, position_after=10,    ◄── BEFORE     │  │
│  │   │   trade_size=10, trade_value=1485,             state      │  │
│  │   │   cash_before=10000, cash_after=8515,          update     │  │
│  │   │   reason, signal_date                                     │  │
│  │   └──────────────────────────────────────────────────────────┘  │
│  │                                                                  │
│  │   ── Update State ──                                             │
│  │   currentPosition = signal.PositionAfter    // 0 → 10           │
│  │   currentCash = signal.AvailableCash        // 10000 → 8515     │
│  │   portfolioValue = cash + position * price  // 10000            │
│  │                                                                  │
│  │   ┌─ NEW (GAP-16): StorePortfolioState ──────────────────────┐  │
│  │   │ POST → InfluxDB "portfolio_state" measurement             │  │
│  │   │ tags: run_id, ticker, schema_version                      │  │
│  │   │ fields: portfolio_value, cash, position, position_value,  │  │
│  │   │   current_price, cumulative_return, drawdown, step_index  │  │
│  │   │ time: evaluation date                                     │  │
│  │   └──────────────────────────────────────────────────────────┘  │
│  │                                                                  │
│  │   ── StoreResult() ──                    (existing)              │
│  │   POST → InfluxDB "forecast_evaluations" measurement            │
│  │                                                                  │
│  │ }  // end loop                                                   │
│  └──────────────────────────────────────────────────────────────────┘
│
│  PHASE 4: METRICS (GAP-12)
│  ┌──────────────────────────────────────────────────────┐
│  │ returns := portfolioValuesToReturns(portfolioValues)  │
│  │                                                       │
│  │ CallMetricsService(returns, runID)                    │
│  │ POST http://sapheneia-metrics:12702/metrics/v1/compute│
│  │ { returns: [0.01, -0.005, ...],                       │
│  │   metric: "all", risk_free_rate: 0.0,                 │
│  │   periods_per_year: 252 }                             │
│  │                                                       │
│  │ Response:                                             │
│  │ { sharpe_ratio: 1.23, max_drawdown: -0.15,           │
│  │   cagr: 0.08, calmar_ratio: 0.53, win_rate: 0.55 }  │
│  │                                                       │
│  │ StoreMetrics(runID, ticker, model, metrics)           │
│  │ POST → InfluxDB "backtest_metrics" measurement        │
│  └──────────────────────────────────────────────────────┘
```

---

## 3. Sapheneia Internal Routing (Forecast Request)

How a forecast request flows through the Sapheneia gateway to a model container.

```
Aleutian POST /orchestration/v1/predict
    │
    ▼
┌─ forecast/main.py (FastAPI app, port 12700) ─────────────────────────┐
│                                                                       │
│  app.include_router(orchestration_router)                             │
│  register_error_handlers(app)    ◄── GAP-15: structured JSON errors  │
│                                                                       │
│  ┌─ orchestration/router.py ──────────────────────────────────────┐  │
│  │  POST /orchestration/v1/predict                                │  │
│  │    │                                                           │  │
│  │    ├── verify_api_key()  (Authorization: Bearer <key>)         │  │
│  │    │                                                           │  │
│  │    └── service.predict(request)                                │  │
│  │        │                                                       │  │
│  │        │  try/except:                                          │  │
│  │        │    SapheneiaError → re-raise (GAP-15 handler)         │  │
│  │        │    ValueError → ValidationError                       │  │
│  │        │    Exception → ComputationError                       │  │
│  │        │                                                       │  │
│  └────────┼───────────────────────────────────────────────────────┘  │
│           │                                                           │
│  ┌────────▼─── orchestration/service.py ──────────────────────────┐  │
│  │  InferenceService.predict(request)                             │  │
│  │    │                                                           │  │
│  │    ├── determine_model_family(request.model)                   │  │
│  │    │   "amazon/chronos-t5-tiny" → "chronos"                    │  │
│  │    │   "google/timesfm-2.0-*"  → "timesfm"                    │  │
│  │    │                                                           │  │
│  │    ├── if chronos:                                             │  │
│  │    │     inference_to_chronos(request) → chronos_request       │  │
│  │    │     POST http://chronos-container:8000                    │  │
│  │    │          /forecast/v1/inference                            │  │
│  │    │     chronos_to_inference(response) → InferenceResponse    │  │
│  │    │                                                           │  │
│  │    │     Error handling (GAP-15):                               │  │
│  │    │       ConnectError    → ServiceUnavailableError            │  │
│  │    │       ReadTimeout     → ServiceTimeoutError                │  │
│  │    │       HTTP 4xx        → ValidationError                    │  │
│  │    │       HTTP 5xx        → ModelUnavailableError              │  │
│  │    │                                                           │  │
│  │    └── if timesfm:                                             │  │
│  │          try: direct Python import (same process)              │  │
│  │          except ImportError: HTTP fallback to container         │  │
│  └────────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────────────┘
        │
        │ HTTP (internal docker network)
        ▼
┌─ Model Container (e.g., forecast-chronos-t5-tiny:8000) ──────────────┐
│  Same Dockerfile.forecast, different MODEL_VARIANT env var            │
│  POST /forecast/v1/inference                                          │
│  Loads HuggingFace model, runs inference, returns forecast values     │
└───────────────────────────────────────────────────────────────────────┘
```

---

## 4. Error Handling Flow (GAP-15)

```
                    ANY Sapheneia endpoint
                           │
                           ▼
                ┌─ shared/errors.py ──────────────────────────────────┐
                │                                                     │
                │  SapheneiaError (base)                               │
                │  ├── ValidationError          → HTTP 400             │
                │  ├── ModelUnavailableError     → HTTP 503             │
                │  ├── ServiceUnavailableError   → HTTP 502             │
                │  ├── ServiceTimeoutError       → HTTP 504             │
                │  └── ComputationError          → HTTP 500             │
                │                                                     │
                │  ErrorCode enum:                                     │
                │    VALIDATION_ERROR, MODEL_UNAVAILABLE,              │
                │    SERVICE_UNAVAILABLE, SERVICE_TIMEOUT,             │
                │    COMPUTATION_ERROR                                 │
                │                                                     │
                └─────────────────────────────────────────────────────┘
                           │
                           ▼
                ┌─ register_error_handlers(app) ──────────────────────┐
                │  Registered in: forecast/main.py                    │
                │                 metrics/main.py                     │
                │                 trading/main.py                     │
                │                                                     │
                │  SapheneiaError → JSON:                              │
                │  {                                                   │
                │    "error": "VALIDATION_ERROR",                      │
                │    "message": "Invalid model: foo/bar",              │
                │    "details": {                                      │
                │      "model": "foo/bar",                             │
                │      "request_id": "abc-123"                         │
                │    }                                                 │
                │  }                                                   │
                │                                                     │
                │  Generic Exception → JSON:                           │
                │  {                                                   │
                │    "error": "INTERNAL_ERROR",                        │
                │    "message": "Internal server error",               │
                │    "details": { "request_id": "abc-123" }            │
                │  }                                                   │
                └─────────────────────────────────────────────────────┘
```

---

## 5. InfluxDB Measurements (Before vs After GAP-16)

```
BEFORE (3 measurements):

  stock_prices ─────────── Written by: data_fetcher (Go)
  forecast_evaluations ─── Written by: evaluator.StoreResult()
  backtest_metrics ──────── Written by: evaluator.StoreMetrics()  ◄── GAP-12

AFTER (6 measurements):

  stock_prices ─────────── Written by: data_fetcher (Go)
  forecast_evaluations ─── Written by: evaluator.StoreResult()
  backtest_metrics ──────── Written by: evaluator.StoreMetrics()  ◄── GAP-12
  forecasts ────────────── Written by: evaluator.StoreForecast()  ◄── GAP-16
  trading_signals ──────── Written by: evaluator.StoreTradingSignal() ◄── GAP-16
  portfolio_state ──────── Written by: evaluator.StorePortfolioState() ◄── GAP-16

Per-iteration writes (252-day backtest):

  BEFORE: 1 write/iter  (StoreResult)                    = 252 writes
  AFTER:  4 writes/iter (StoreForecast + StoreTradingSignal
                         + StorePortfolioState + StoreResult) = 1,008 writes
  + 1 StoreMetrics at end                                 = 1,009 total
```

### Measurement Schemas

#### `forecasts` (GAP-16)

| Type  | Name              | Description                                    |
|-------|-------------------|------------------------------------------------|
| Tag   | `run_id`          | Backtest run identifier                        |
| Tag   | `ticker`          | Stock symbol                                   |
| Tag   | `model`           | Model name (e.g., amazon/chronos-t5-tiny)      |
| Tag   | `model_family`    | Model family (chronos, timesfm, etc.)          |
| Tag   | `schema_version`  | Schema version (e.g., "1")                     |
| Field | `forecast_price`  | Predicted price (float, sanitized)             |
| Field | `current_price`   | Price at time of forecast (float, sanitized)   |
| Field | `forecast_horizon`| Number of steps ahead (int)                    |
| Field | `confidence_lower`| Lower confidence bound (float, optional)       |
| Field | `confidence_upper`| Upper confidence bound (float, optional)       |
| Field | `inference_time_ms`| Time to generate forecast (int)               |
| Field | `forecast_date`   | The date being forecasted (string, YYYYMMDD)   |
| Time  | `_time`           | Evaluation date                                |

#### `trading_signals` (GAP-16)

| Type  | Name                   | Description                              |
|-------|------------------------|------------------------------------------|
| Tag   | `run_id`               | Backtest run identifier                  |
| Tag   | `ticker`               | Stock symbol                             |
| Tag   | `strategy_type`        | Strategy (threshold, return, quantile)   |
| Tag   | `action`               | Trading action (buy, sell, hold)         |
| Tag   | `schema_version`       | Schema version                           |
| Field | `forecast_price`       | Forecast that triggered the signal       |
| Field | `current_price`        | Current price at signal time             |
| Field | `position_before`      | Position before trade (float)            |
| Field | `position_after`       | Position after trade (float)             |
| Field | `trade_size`           | Number of shares traded (float)          |
| Field | `trade_value`          | Dollar value of trade (float)            |
| Field | `available_cash_before`| Cash before trade (float)                |
| Field | `available_cash_after` | Cash after trade (float)                 |
| Field | `reason`               | Human-readable trade reason (string)     |
| Field | `signal_date`          | Date of trading signal (string, YYYYMMDD)|
| Time  | `_time`                | Evaluation date                          |

#### `portfolio_state` (GAP-16)

| Type  | Name               | Description                                       |
|-------|--------------------|---------------------------------------------------|
| Tag   | `run_id`           | Backtest run identifier                           |
| Tag   | `ticker`           | Stock symbol                                      |
| Tag   | `schema_version`   | Schema version                                    |
| Field | `portfolio_value`  | Total portfolio value: cash + position * price    |
| Field | `cash`             | Available cash (float)                            |
| Field | `position`         | Shares held (float)                               |
| Field | `position_value`   | position * current_price (float)                  |
| Field | `current_price`    | Price used for valuation (float)                  |
| Field | `cumulative_return`| Return since initial capital (float)              |
| Field | `drawdown`         | Current drawdown from peak (float, negative)      |
| Field | `step_index`       | Iteration index in backtest (int, 0-based)        |
| Field | `snapshot_date`    | Date of portfolio snapshot (string, YYYYMMDD)     |
| Time  | `_time`            | Evaluation date                                   |

---

## 6. How to Add a New Forecast Model

```
STEP 1: docker-compose.yml (Sapheneia)
┌────────────────────────────────────────────────────────────────────┐
│ Add a new service block:                                           │
│                                                                    │
│   forecast-newmodel:                                               │
│     build:                                                         │
│       context: .                                                   │
│       dockerfile: Dockerfile.forecast                              │
│       args:                                                        │
│         MODEL_NAME: newmodel         ◄── model family name         │
│     environment:                                                   │
│       - MODEL_VARIANT=org/newmodel-v1  ◄── HuggingFace model ID   │
│     ports:                                                         │
│       - "12730:8000"                                               │
│     networks:                                                      │
│       - aleutian-network                                           │
└────────────────────────────────────────────────────────────────────┘
                    │
                    ▼
STEP 2: orchestration/adapters.py (Sapheneia)
┌────────────────────────────────────────────────────────────────────┐
│ a) determine_model_family():                                       │
│      Add: elif "newmodel" in model.lower(): return "newmodel"      │
│                                                                    │
│ b) Create adapter functions:                                       │
│      inference_to_newmodel(request) → dict                         │
│      newmodel_to_inference(data, request, time_ms) → Response      │
└────────────────────────────────────────────────────────────────────┘
                    │
                    ▼
STEP 3: orchestration/service.py (Sapheneia)
┌────────────────────────────────────────────────────────────────────┐
│ a) Add env var in __init__:                                        │
│      self.newmodel_url = os.getenv("NEWMODEL_SERVICE_URL", ...)    │
│                                                                    │
│ b) Add routing in predict():                                       │
│      elif model_family == "newmodel":                              │
│          response = await self._run_newmodel_inference(request)     │
│                                                                    │
│ c) Add _run_newmodel_inference() method                            │
│      (copy _run_chronos_inference, change endpoint/adapters)       │
└────────────────────────────────────────────────────────────────────┘
                    │
                    ▼
STEP 4: forecast/main.py (Sapheneia)
┌────────────────────────────────────────────────────────────────────┐
│ Add env var to docker-compose forecast gateway:                    │
│   NEWMODEL_SERVICE_URL=http://forecast-newmodel:8000               │
└────────────────────────────────────────────────────────────────────┘
                    │
                    ▼
STEP 5: Strategy YAML (used by Aleutian)
┌────────────────────────────────────────────────────────────────────┐
│ simulations/strategies/spy_newmodel_v1.yaml                        │
│                                                                    │
│   forecast:                                                        │
│     model: "org/newmodel-v1"      ◄── must match HuggingFace ID   │
│     context_size: 252                                              │
│     horizon_size: 20                                               │
│     compute_mode: "unified"                                        │
└────────────────────────────────────────────────────────────────────┘
                    │
                    ▼
DOES ALEUTIAN NEED CHANGES?  ─── NO
┌────────────────────────────────────────────────────────────────────┐
│ Aleutian is model-agnostic. It just passes the model string        │
│ from the strategy YAML to Sapheneia. The routing happens inside    │
│ Sapheneia's orchestration layer:                                   │
│                                                                    │
│   Aleutian                    Sapheneia                            │
│   strategy.yaml               orchestration/service.py             │
│   model: "org/newmodel"  ──►  determine_model_family()             │
│                               → "newmodel"                         │
│                               → _run_newmodel_inference()          │
│                               → http://forecast-newmodel:8000      │
│                                                                    │
│ Aleutian only cares about:                                         │
│   - InferenceRequest/InferenceResponse contract (unchanged)        │
│   - forecast.Values[0] as the predicted price                      │
│   - metadata.InferenceTimeMs, metadata.Device, etc.                │
└────────────────────────────────────────────────────────────────────┘
```

---

## 7. Docker Network Topology

```
┌─────────────── aleutian-shared (docker network) ──────────────────────┐
│                                                                        │
│  ALEUTIAN FOSS                                                         │
│  ┌──────────────────┐                                                  │
│  │ orchestrator      │ (Go binary, not containerized during dev)       │
│  │ runs on host      │                                                 │
│  │                   │                                                 │
│  │ Env vars:         │                                                 │
│  │  SAPHENEIA_GATEWAY│                                                 │
│  │  =localhost:12700 │                                                 │
│  │  SAPHENEIA_TRADING│                                                 │
│  │  =localhost:12132 │                                                 │
│  │  METRICS_SERVICE  │                                                 │
│  │  =localhost:12702 │                                                 │
│  │  INFLUXDB_URL     │                                                 │
│  │  =localhost:12130 │                                                 │
│  └────┬───┬───┬──────┘                                                 │
│       │   │   │                                                        │
│  SAPHENEIA CONTAINERS                                                  │
│  ┌────▼───────────────┐  ┌──────────────────┐  ┌──────────────────┐   │
│  │ forecast (gateway)  │  │ trading          │  │ metrics          │   │
│  │ :12700 → :8000      │  │ :12132 → :9000   │  │ :12702 → :8000   │   │
│  │                     │  │                  │  │                  │   │
│  │ Routes to model     │  │ /trading/execute │  │ /metrics/v1/     │   │
│  │ containers below    │  │                  │  │   compute/       │   │
│  └────┬────────────────┘  └──────────────────┘  └──────────────────┘   │
│       │ internal HTTP                                                   │
│  ┌────▼────────────────────────────────────────────────────────────┐   │
│  │ MODEL CONTAINERS (one per model variant)                        │   │
│  │                                                                 │   │
│  │  forecast-chronos-t5-tiny   :12710   ← most used in backtests   │   │
│  │  forecast-chronos-t5-mini   :12711                              │   │
│  │  forecast-chronos-t5-small  :12712                              │   │
│  │  forecast-chronos-t5-base   :12713                              │   │
│  │  forecast-chronos-t5-large  :12714                              │   │
│  │  forecast-chronos-bolt-mini :12715                              │   │
│  │  forecast-chronos-bolt-small:12716                              │   │
│  │  forecast-chronos-bolt-base :12717                              │   │
│  │  forecast-timesfm-2-0       :12720   (commented out)            │   │
│  │                                                                 │   │
│  │  All use same Dockerfile.forecast, differ by MODEL_VARIANT env  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                        │
│  ┌────────────────────┐  ┌──────────────────────┐                     │
│  │ data               │  │ InfluxDB              │                     │
│  │ :12701 → :8000     │  │ :12130 → :8086        │                     │
│  │ (Go, Yahoo→Influx) │  │ (podman-compose       │                     │
│  └────────────────────┘  │  .timeseries.yml)     │                     │
│                          └──────────────────────┘                     │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 8. What Each GAP Changed

### GAP-12: Metrics Pipeline (AleutianFOSS)

```
  Aleutian evaluator.go
    + CallMetricsService()  ──HTTP POST──►  Sapheneia metrics/:12702
    + StoreMetrics()        ──────────►     InfluxDB "backtest_metrics"
    + MetricsResponse struct
    + portfolioValuesToReturns() helper
```

**Files modified (AleutianFOSS):**
- `services/orchestrator/handlers/evaluator.go` — CallMetricsService, StoreMetrics, RunScenario loop
- `services/orchestrator/datatypes/evaluator.go` — MetricsResponse struct

### GAP-13: Code-Level Documentation (Sapheneia)

```
  Sapheneia
    + docstrings on clients/ (TradeAction, StrategyType, CircuitState,
      from_dict, to_dict, PortfolioManager.__init__)
    + docstrings on backtest.py, service.py
    + GoDoc on data/main.go (14 exported types, 1 function)
    + 5 developer guides in docs/guides/
```

**Files modified (Sapheneia):**
- `orchestration/clients/trading_client.py` — enum + method docstrings
- `orchestration/clients/metrics_client.py` — enum + method docstrings
- `orchestration/clients/data_client.py` — method docstrings
- `orchestration/backtest.py` — dataclass method docstrings
- `orchestration/service.py` — expanded _run_timesfm_http docstring
- `data/main.go` — GoDoc comments on all exported types

**Files created (Sapheneia):**
- `docs/guides/adding-a-forecast-model.md`
- `docs/guides/adding-a-trading-strategy.md`
- `docs/guides/adding-a-metric.md`
- `docs/guides/service-contracts.md`
- `docs/guides/local-dev-setup.md`

### GAP-14: Unit Testing Coverage (+67 tests, Sapheneia)

```
  Sapheneia
    + tests/shared/test_errors.py          (15 tests)
    + orchestration/tests/test_backtest.py (20 tests)
    + orchestration/tests/test_router.py   (10 tests)
    + expanded test_adapters.py            (+5 tests)
    + expanded test_service.py             (+8 tests)
    + expanded test_metrics.py             (+6 tests)
    + expanded test_endpoints.py           (+3 tests)
```

**Files created (Sapheneia):**
- `tests/shared/__init__.py`
- `tests/shared/test_errors.py`
- `orchestration/tests/test_backtest.py`
- `orchestration/tests/test_router.py`

**Files modified (Sapheneia):**
- `orchestration/tests/test_adapters.py` — ComputationError tests
- `orchestration/tests/test_service.py` — Service*Error tests
- `tests/metrics/test_metrics.py` — NaN/Inf edge cases
- `tests/metrics/test_endpoints.py` — structured error response tests

### GAP-15: Error Handling (Sapheneia)

```
  Sapheneia
    + shared/errors.py            (error hierarchy + handler registration)
    + structured errors in        forecast/main.py
                                  metrics/main.py
                                  trading/main.py
    + ComputationError in         orchestration/adapters.py
    + Service*Error in            orchestration/service.py
    + NaN/Inf hardening in        metrics/core/metrics.py
    + path traversal fix in       orchestration/router.py
```

**Files created (Sapheneia):**
- `shared/__init__.py`
- `shared/errors.py`

**Files modified (Sapheneia):**
- `forecast/main.py` — register_error_handlers(app)
- `metrics/main.py` — register_error_handlers(app)
- `trading/main.py` — register_error_handlers(app)
- `orchestration/adapters.py` — ComputationError on missing forecast keys
- `orchestration/service.py` — ServiceUnavailable/Timeout/Validation/ModelUnavailable errors
- `metrics/core/metrics.py` — NaN/Inf filtering, try/except fallbacks
- `metrics/routes/endpoints.py` — structured error responses
- `orchestration/router.py` — path traversal regex validation

### GAP-16: InfluxDB Intermediate Values (AleutianFOSS)

```
  AleutianFOSS
    + datatypes: ForecastRecord, TradingSignalRecord, PortfolioStateRecord
    + handlers: StoreForecast(), StoreTradingSignal(), StorePortfolioState()
    + handlers: sanitizeFloat() helper (NaN/Inf → 0.0)
    + handlers: schemaVersion constant
    + RunScenario loop: peakValue tracking, drawdown computation,
                        cumulative return with div-by-zero guard,
                        3 new Store calls
    + tests: 12 new tests with mock WriteAPIBlocking
```

**Files modified (AleutianFOSS):**
- `services/orchestrator/datatypes/evaluator.go` — 3 new record structs
- `services/orchestrator/handlers/evaluator.go` — 3 Store methods, sanitizeFloat, loop modifications
- `services/orchestrator/handlers/evaluator_test.go` — mock writeAPI, 12 tests

---

## 9. Service Contract Summary

### Aleutian → Sapheneia HTTP Calls

| Call | Method | URL | Port | Request | Response |
|------|--------|-----|------|---------|----------|
| Forecast (unified) | POST | `/orchestration/v1/predict` | 12700 | InferenceRequest | InferenceResponse |
| Forecast (legacy) | POST | `/v1/timeseries/forecast` | 12700 | LegacyForecastRequest | LegacyForecastResponse |
| Trading | POST | `/trading/execute` | 12132 | TradingSignalRequest | TradingSignalResponse |
| Metrics | POST | `/metrics/v1/compute/` | 12702 | MetricsRequest | MetricsResponse |
| Data fetch | POST | `/v1/data/fetch` | 12701 | DataFetchRequest | 200 OK |
| Strategy list | GET | `/orchestration/v1/strategies` | 12700 | — | `{strategies: [...]}` |
| Strategy load | GET | `/orchestration/v1/strategies/{name}` | 12700 | — | YAML as JSON |

### Sapheneia Internal HTTP Calls

| Call | From | To | URL |
|------|------|----|-----|
| Chronos inference | forecast gateway | model container | `http://forecast-chronos-t5-tiny:8000/forecast/v1/inference` |
| TimesFM inference | forecast gateway | model container | `http://forecast-timesfm:8000/forecast/v1/timesfm20/inference` |

### Aleutian → InfluxDB Writes

| Measurement | Writer | Frequency | GAP |
|-------------|--------|-----------|-----|
| `stock_prices` | data_fetcher | On-demand | — |
| `forecast_evaluations` | StoreResult | Per trading day | — |
| `backtest_metrics` | StoreMetrics | Per backtest | GAP-12 |
| `forecasts` | StoreForecast | Per trading day | GAP-16 |
| `trading_signals` | StoreTradingSignal | Per trading day | GAP-16 |
| `portfolio_state` | StorePortfolioState | Per trading day | GAP-16 |

---

## 10. Test Coverage Summary

| Suite | Tests | Time |
|-------|-------|------|
| Sapheneia (`python -m pytest`) | 124 passed, 20 skipped | ~4s |
| AleutianFOSS handlers (`go test`) | All pass (incl. 12 new) | ~14s |
| AleutianFOSS orchestrator (all packages) | 9 packages pass | ~30s |
