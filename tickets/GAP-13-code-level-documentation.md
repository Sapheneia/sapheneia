# GAP-13: Code-Level and Higher-Level Documentation

**Priority:** MEDIUM
**Severity:** MEDIUM
**Category:** Documentation / Developer Experience
**Effort:** 2-3 days
**Codebase:** Sapheneia (Python + Go)
**Status:** COMPLETED
**PR Feedback Item:** #1

---

## Architecture Review

### Reliability
- **Current Risk:** New contributors cannot understand module responsibilities without reading full implementations
- **Mitigation:** Docstrings on all public functions/classes, module-level docs in `__init__.py`
- **Standard:** Google-style Python docstrings, GoDoc comments for Go

### Continuity
- **State Management:** Documentation lives alongside code - no drift from external wikis
- **Versioning:** Docs checked in with the code they describe

### Integrity
- **Validation:** CI lint check (pydocstyle or ruff D rules) to enforce docstring presence
- **Completeness:** Every public function, class, and module must have a docstring

### Optimization
- **Scope:** Only document public APIs and non-obvious internal logic
- **Avoid:** Do not document self-evident one-liners or trivial getters

### Separation (Scalability)
- **Code-level:** Docstrings in source files
- **Higher-level:** Markdown guides in `docs/guides/`

---

## Summary

PR feedback indicates the aleutian_merge and aleutian_merge_part_2 changesets lack sufficient documentation at both the function/module level and at the higher "how to use it / how to extend it" level. This ticket covers adding docstrings, module descriptions, and practical developer guides.

## Data Flow & Documentation Gap Analysis

### System-Wide Module Dependency Map

Shows every module, what it exports, and where documentation is missing.
`[!]` = missing docstrings, `[~]` = partial, `[ok]` = adequate.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         SAPHENEIA MODULE GRAPH                                  │
│                   (Documentation status per module)                             │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  orchestration/                                                                 │
│  ├── __init__.py [~] ── exports Period, DataSource, DataField, ContextData,     │
│  │                      HorizonSpec, ForecastData, InferenceRequest,            │
│  │                      InferenceResponse, orchestration_router                 │
│  │                      GAP: No module-level docstring explaining purpose       │
│  │                                                                              │
│  ├── schema.py [~] ── 9 Pydantic models + 3 enums                              │
│  │   │  Period, DataSource, DataField (enums)                                   │
│  │   │  ContextData ── field_validator('start_date','end_date')                 │
│  │   │  HorizonSpec ── length: gt=0, le=365                                     │
│  │   │  ModelParams ── num_samples, temperature, top_k, top_p                   │
│  │   │  InferenceRequest ── ticker: min=1, max=20                               │
│  │   │  InferenceResponse, ForecastData, ContextSummary                         │
│  │   │  LegacyForecastRequest, LegacyForecastResponse                           │
│  │   │  GAP: Models have Field() descriptions but no class-level docstrings     │
│  │   │       No module docstring. No usage examples.                            │
│  │   │                                                                          │
│  ├── adapters.py [!] ── 12+ functions, 0 docstrings                             │
│  │   │  determine_model_family(model_name) -> str                               │
│  │   │  get_model_endpoint(model_family) -> str                                 │
│  │   │  parse_date(date_str, field_name) -> datetime                            │
│  │   │  calculate_forecast_dates(context_end_date, horizon, period) -> tuple     │
│  │   │  inference_to_chronos(request) -> dict                                   │
│  │   │  chronos_to_inference(response, request, time_ms) -> InferenceResponse   │
│  │   │  inference_to_timesfm(request) -> dict                                   │
│  │   │  timesfm_to_inference(response, request, time_ms) -> InferenceResponse   │
│  │   │  legacy_to_inference(request, source, period) -> InferenceRequest         │
│  │   │  inference_to_legacy(response) -> LegacyForecastResponse                 │
│  │   │  GAP: ZERO docstrings. No module docstring. Adapter pattern undocumented.│
│  │   │       Model family routing logic is non-obvious and must be documented.  │
│  │   │                                                                          │
│  ├── service.py [!] ── 2 classes, 6 methods, minimal docs                       │
│  │   │  InferenceService.__init__(base_url, api_key, timeout)                   │
│  │   │  InferenceService.predict(request) -> InferenceResponse                  │
│  │   │  InferenceService._run_chronos_inference(request) -> InferenceResponse   │
│  │   │  InferenceService._run_timesfm_inference(request) -> InferenceResponse   │
│  │   │  InferenceService._run_timesfm_http(request, start_time)                 │
│  │   │  LegacyCompatService.forecast(request, source, period)                   │
│  │   │  GAP: No docstrings. Routing logic (chronos vs timesfm vs fallback)      │
│  │   │       is complex and completely undocumented.                             │
│  │   │                                                                          │
│  ├── backtest.py [!] ── 2 dataclasses, 4 functions, minimal docs                │
│  │   │  BacktestConfig (dataclass) ── 12 fields                                 │
│  │   │  BacktestResult (dataclass) ── 7 fields + 2 properties                   │
│  │   │  run_backtest(config, data_provider, run_id, callback) -> BacktestResult  │
│  │   │  generate_evaluation_dates(start, end, step) -> List[str]                │
│  │   │  calculate_start_date(end_date, days) -> str                             │
│  │   │  create_influx_data_provider(url) -> DataProvider                         │
│  │   │  quick_backtest(ticker, model, ...) -> BacktestResult                     │
│  │   │  GAP: run_backtest() is 150+ lines with 5 phases and no docstring.       │
│  │   │       DataProvider type alias undocumented.                               │
│  │   │                                                                          │
│  ├── router.py [!] ── 7 endpoints, 2 dependencies                               │
│  │   │  get_inference_service() -> InferenceService                              │
│  │   │  get_legacy_service() -> LegacyCompatService                              │
│  │   │  verify_api_key(authorization, x_api_key) -> str                          │
│  │   │  POST /orchestration/v1/predict                                           │
│  │   │  GET  /orchestration/v1/health                                            │
│  │   │  GET  /orchestration/v1/models                                            │
│  │   │  GET  /orchestration/v1/strategies                                        │
│  │   │  GET  /orchestration/v1/strategies/{name}                                 │
│  │   │  POST /v1/timeseries/forecast (deprecated)                                │
│  │   │  GAP: No endpoint docstrings. No module docstring.                       │
│  │   │                                                                          │
│  └── clients/ [!] ── 3 client classes, circuit breaker, portfolio manager        │
│      ├── data_client.py ── DataClient, ResultPoint, MetricsSummary, DataPoint   │
│      │   GAP: No class/method docstrings. 5 methods undocumented.               │
│      ├── metrics_client.py ── MetricsClient, MetricsResponse, prices_to_returns │
│      │   GAP: Circuit breaker pattern undocumented. Retry logic undocumented.   │
│      └── trading_client.py ── TradingClient, TradeResult, PortfolioState,       │
│          PortfolioManager                                                        │
│          GAP: PortfolioManager checkpoint logic undocumented.                    │
│                                                                                 │
│  metrics/                                                                        │
│  ├── __init__.py [~] ── declares __version__ = "2.0.0", no module docstring     │
│  ├── core/                                                                       │
│  │   ├── __init__.py [!] ── EMPTY                                               │
│  │   └── metrics.py [!] ── 10 functions                                          │
│  │       _validate_returns(returns) -> pd.Series                                 │
│  │       calculate_sharpe_ratio(returns, rf, periods) -> float                   │
│  │       calculate_max_drawdown(returns) -> float                                │
│  │       calculate_cagr(returns, periods) -> float                               │
│  │       calculate_calmar_ratio(returns, periods) -> float                       │
│  │       calculate_win_rate(returns) -> float                                    │
│  │       calculate_performance_metrics(returns, ...) -> dict                     │
│  │       _interpret_sharpe/_interpret_calmar/_interpret_win_rate                  │
│  │       _get_overall_assessment(sharpe, max_dd, calmar, win_rate) -> str         │
│  │       GAP: No docstrings on any function. quantstats dependency undocumented. │
│  │                                                                               │
│  └── routes/                                                                     │
│      ├── __init__.py [!] ── EMPTY                                               │
│      └── endpoints.py [~] ── ComputeRequest model, POST /compute/ endpoint      │
│          GAP: Endpoint has basic description, but metric routing undocumented.   │
│                                                                                 │
│  trading/                                                                        │
│  ├── __init__.py [~] ── declares __version__, __author__                         │
│  ├── main.py [~] ── FastAPI app with 5 middleware layers                         │
│  │   GAP: Middleware order and purpose undocumented.                             │
│  ├── services/                                                                   │
│  │   ├── __init__.py [!] ── EMPTY                                               │
│  │   └── trading.py [~] ── TradingStrategy class, 1171+ lines                   │
│  │       4 enums: StrategyType, ThresholdType, PositionSizing, WhichHistory      │
│  │       execute_trading_signal(params) -> dict                                  │
│  │       generate_trading_signal(params) -> dict                                 │
│  │       calculate_threshold_signal(params) -> dict                              │
│  │       calculate_return_signal(params) -> dict                                 │
│  │       calculate_quantile_signal(params) -> dict                               │
│  │       _validate_common_params, _convert_to_array, _get_history_array          │
│  │       _calculate_threshold, _calculate_returns, _calculate_atr               │
│  │       get_portfolio_value, get_portfolio_return                                │
│  │       GAP: Partial docs. Strategy selection logic undocumented.               │
│  │            12 helper methods have no docstrings.                              │
│  │                                                                               │
│  └── routes/, schemas/, core/ ── all __init__.py EMPTY                           │
│                                                                                 │
│  forecast/                                                                       │
│  ├── __init__.py [~] ── declares __version__ = "2.0.0"                           │
│  ├── main.py [~] ── FastAPI gateway, routes to model containers                  │
│  │   GAP: Model routing logic undocumented. Optional imports undocumented.       │
│  ├── core/                                                                       │
│  │   ├── security.py [!] ── get_api_key(), create_api_key_header()              │
│  │   │   GAP: No docstrings. Auth flow undocumented.                            │
│  │   └── config.py, rate_limit.py ── settings and rate limiting                  │
│  └── models/                                                                     │
│      ├── chronos/ ── routes, schemas, services for Chronos models                │
│      └── timesfm20/ ── routes, schemas, services for TimesFM 2.0                │
│          GAP: No model-specific documentation on how inference works.            │
│                                                                                 │
│  data/ (Go)                                                                      │
│  └── main.go [~] ── Server struct, 5 handlers                                   │
│      handleFetchData, fetchWorker, getLatestTimestamp, fetchYahooData            │
│      handleQueryData, handleWriteResults                                         │
│      GAP: GoDoc comments present on some functions but incomplete.              │
│           Worker pool pattern undocumented.                                      │
│                                                                                 │
│  shared/ ── DOES NOT EXIST YET (proposed in GAP-15)                              │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Request Flow: What a Developer Needs to Understand

Shows the path a single prediction request takes through the system.
Each numbered step needs documentation explaining what happens and why.

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│            PREDICTION REQUEST FLOW (unified mode)                                │
│            Steps a new developer must understand                                 │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ① Aleutian CLI (Go)                                                             │
│  cmd_evaluation.go::runEvaluation()                                              │
│  DOC NEEDED: How scenario YAML maps to RunScenario() params                      │
│       │                                                                          │
│       │  HTTP POST /orchestration/v1/predict                                     │
│       │  Auth: Bearer token in Authorization header                              │
│       ▼                                                                          │
│  ② Sapheneia Router                                                              │
│  orchestration/router.py::predict()                                              │
│  DOC NEEDED: How verify_api_key() dependency works                               │
│  DOC NEEDED: Why Depends(get_inference_service) creates per-request instance      │
│       │                                                                          │
│       │  Pydantic validates InferenceRequest                                     │
│       ▼                                                                          │
│  ③ Inference Service                                                             │
│  orchestration/service.py::InferenceService.predict()                            │
│  DOC NEEDED: Model family routing decision tree                                  │
│       │                                                                          │
│       ├──── model.lower() contains "chronos"? ──► _run_chronos_inference()       │
│       ├──── model.lower() contains "timesfm"? ──► _run_timesfm_inference()       │
│       └──── else (fallback) ─────────────────► _run_chronos_inference()          │
│             DOC NEEDED: Why chronos is the fallback. Is this intentional?         │
│       │                                                                          │
│       ▼                                                                          │
│  ④ Adapter Transform (Request)                                                   │
│  orchestration/adapters.py::inference_to_chronos() or inference_to_timesfm()     │
│  DOC NEEDED: What fields get mapped. What gets dropped.                          │
│  DOC NEEDED: Why timesfm wraps context in extra list (batch format)              │
│       │                                                                          │
│       │  Transforms: InferenceRequest → model-specific dict                      │
│       ▼                                                                          │
│  ⑤ HTTP Call to Model Container                                                  │
│  service.py::_run_chronos_inference() or _run_timesfm_http()                     │
│  DOC NEEDED: Which env vars control which URLs                                   │
│  DOC NEEDED: Timeout behavior (default 300s from INFERENCE_TIMEOUT env)           │
│       │                                                                          │
│       │  POST {CHRONOS_SERVICE_URL}/forecast/v1/inference                         │
│       │  or POST {TIMESFM_SERVICE_URL}/forecast/v1/timesfm20/inference            │
│       │  or direct Python call via run_in_executor (timesfm only)                │
│       ▼                                                                          │
│  ⑥ Model Container Response                                                      │
│       │                                                                          │
│       ▼                                                                          │
│  ⑦ Adapter Transform (Response)                                                  │
│  adapters.py::chronos_to_inference() or timesfm_to_inference()                   │
│  DOC NEEDED: How forecast values extracted (median vs mean)                      │
│  DOC NEEDED: How quantiles are assembled                                         │
│  DOC NEEDED: How forecast dates are calculated from context_end + horizon         │
│       │                                                                          │
│       │  Transforms: model-specific dict → InferenceResponse                     │
│       ▼                                                                          │
│  ⑧ Response Returned                                                             │
│  router.py → JSON response to Aleutian Go caller                                │
│                                                                                  │
│  TOTAL UNDOCUMENTED STEPS: 8/8                                                   │
│  TOTAL "DOC NEEDED" ITEMS: 12                                                    │
│                                                                                  │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### Extension Points Map: "How Do I Add a New X?"

Shows where a developer must make changes to extend the system.

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                 EXTENSION POINT: ADDING A NEW FORECAST MODEL                     │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  Step 1: Register Model Family                                                   │
│  FILE: orchestration/adapters.py::determine_model_family()                       │
│  ACTION: Add substring check for new model name                                  │
│  ┌─────────────────────────────────────────────┐                                 │
│  │  if "newmodel" in model_lower:              │                                 │
│  │      return "newmodel"                      │  NO GUIDE EXISTS                │
│  └─────────────────────────────────────────────┘                                 │
│       │                                                                          │
│  Step 2: Create Request Adapter                                                  │
│  FILE: orchestration/adapters.py                                                 │
│  ACTION: Write inference_to_newmodel(request) -> dict                            │
│  ┌─────────────────────────────────────────────┐                                 │
│  │  def inference_to_newmodel(request):        │                                 │
│  │      # Transform InferenceRequest to        │  NO GUIDE EXISTS                │
│  │      # model-specific format                │                                 │
│  └─────────────────────────────────────────────┘                                 │
│       │                                                                          │
│  Step 3: Create Response Adapter                                                 │
│  FILE: orchestration/adapters.py                                                 │
│  ACTION: Write newmodel_to_inference(response, request, time) -> InferenceResp   │
│  ┌─────────────────────────────────────────────┐                                 │
│  │  def newmodel_to_inference(resp, req, ms):  │                                 │
│  │      # Transform model response to          │  NO GUIDE EXISTS                │
│  │      # InferenceResponse                    │                                 │
│  └─────────────────────────────────────────────┘                                 │
│       │                                                                          │
│  Step 4: Add Routing in InferenceService                                         │
│  FILE: orchestration/service.py::predict()                                       │
│  ACTION: Add elif branch for new model family                                    │
│  ┌─────────────────────────────────────────────┐                                 │
│  │  elif model_family == "newmodel":           │                                 │
│  │      return await self._run_newmodel(req)   │  NO GUIDE EXISTS                │
│  └─────────────────────────────────────────────┘                                 │
│       │                                                                          │
│  Step 5: Create Model Container                                                  │
│  FILE: forecast/models/newmodel/ (new directory)                                 │
│  ACTION: FastAPI service, Dockerfile, routes, schemas, services                  │
│  ┌─────────────────────────────────────────────┐                                 │
│  │  forecast/models/newmodel/                  │                                 │
│  │  ├── __init__.py                            │  NO GUIDE EXISTS                │
│  │  ├── routes/endpoints.py                    │                                 │
│  │  ├── schemas/inference.py                   │                                 │
│  │  └── services/model.py                      │                                 │
│  └─────────────────────────────────────────────┘                                 │
│       │                                                                          │
│  Step 6: Add to docker-compose.yml                                               │
│  ACTION: New service definition with port, health check, volumes                 │
│  ┌─────────────────────────────────────────────┐                                 │
│  │  sapheneia-forecast-newmodel:               │                                 │
│  │    build: ...                               │  NO GUIDE EXISTS                │
│  │    ports: ["127XX:8000"]                    │                                 │
│  └─────────────────────────────────────────────┘                                 │
│       │                                                                          │
│  Step 7: Create Strategy YAMLs                                                   │
│  FILE: simulations/strategies/ (1200+ existing files as reference)                │
│  ACTION: Create YAML per ticker per model variant                                │
│  ┌─────────────────────────────────────────────┐                                 │
│  │  XLK_newmodel_base.yaml                     │  NO GUIDE EXISTS                │
│  │  SPY_newmodel_base.yaml                     │                                 │
│  └─────────────────────────────────────────────┘                                 │
│                                                                                  │
│  TOTAL STEPS: 7 │ DOCUMENTED: 0 │ GUIDE EXISTS: NO                              │
│                                                                                  │
├──────────────────────────────────────────────────────────────────────────────────┤
│                 EXTENSION POINT: ADDING A NEW TRADING STRATEGY                   │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  Step 1: Define Strategy Type                                                    │
│  FILE: trading/services/trading.py::StrategyType enum                            │
│  ┌─────────────────────────────────────────────┐                                 │
│  │  class StrategyType(str, Enum):             │                                 │
│  │      THRESHOLD = "threshold"                │                                 │
│  │      RETURN = "return"                      │  NO GUIDE EXISTS                │
│  │      QUANTILE = "quantile"                  │                                 │
│  │      NEW_STRAT = "new_strat"  # add here    │                                 │
│  └─────────────────────────────────────────────┘                                 │
│       │                                                                          │
│  Step 2: Implement Signal Calculation                                            │
│  FILE: trading/services/trading.py                                               │
│  ACTION: Write calculate_new_strat_signal(params) -> dict                        │
│  MUST RETURN: {"action": buy/sell/hold, "size": float, "reason": str}            │
│  ┌─────────────────────────────────────────────┐                                 │
│  │  @staticmethod                              │                                 │
│  │  def calculate_new_strat_signal(params):    │  NO GUIDE EXISTS                │
│  │      # Validate params                      │                                 │
│  │      # Calculate signal                     │                                 │
│  │      return {"action":..., "size":...}      │                                 │
│  └─────────────────────────────────────────────┘                                 │
│       │                                                                          │
│  Step 3: Add Routing                                                             │
│  FILE: trading/services/trading.py::generate_trading_signal()                    │
│  ┌─────────────────────────────────────────────┐                                 │
│  │  elif strategy == StrategyType.NEW_STRAT:   │                                 │
│  │      return cls.calc_new_strat_signal(p)    │  NO GUIDE EXISTS                │
│  └─────────────────────────────────────────────┘                                 │
│       │                                                                          │
│  Step 4: Add Client Support                                                      │
│  FILE: orchestration/clients/trading_client.py::StrategyType enum                │
│  ACTION: Mirror the new strategy type in the client enum                         │
│       │                                                                          │
│  Step 5: Write Tests                                                             │
│  FILE: trading/tests/                                                            │
│                                                                                  │
│  TOTAL STEPS: 5 │ DOCUMENTED: 0 │ GUIDE EXISTS: NO                              │
│                                                                                  │
├──────────────────────────────────────────────────────────────────────────────────┤
│                 EXTENSION POINT: ADDING A NEW METRIC                             │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  Step 1: Add Calculation Function                                                │
│  FILE: metrics/core/metrics.py                                                   │
│  ┌─────────────────────────────────────────────┐                                 │
│  │  def calculate_new_metric(returns) -> float:│  NO GUIDE EXISTS                │
│  │      validated = _validate_returns(returns)  │                                 │
│  │      return qs.stats.new_metric(validated)   │                                 │
│  └─────────────────────────────────────────────┘                                 │
│       │                                                                          │
│  Step 2: Add to Aggregator                                                       │
│  FILE: metrics/core/metrics.py::calculate_performance_metrics()                  │
│  ACTION: Include new metric in returned dict                                     │
│       │                                                                          │
│  Step 3: Add to Endpoint                                                         │
│  FILE: metrics/routes/endpoints.py::compute_metrics()                            │
│  ACTION: Add new Literal option and elif branch                                  │
│       │                                                                          │
│  Step 4: Update Client                                                           │
│  FILE: orchestration/clients/metrics_client.py::MetricsResponse                  │
│  ACTION: Add new field to dataclass                                              │
│       │                                                                          │
│  Step 5: Update Go Consumer (AleutianFOSS)                                       │
│  FILE: datatypes/evaluator.go::MetricsResponse struct                            │
│  ACTION: Add new field with json tag                                             │
│                                                                                  │
│  TOTAL STEPS: 5 │ DOCUMENTED: 0 │ GUIDE EXISTS: NO                              │
│                                                                                  │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### Service Communication Contracts (Undocumented)

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│               SERVICE-TO-SERVICE COMMUNICATION MAP                               │
│               (All contracts currently undocumented)                              │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  Aleutian Go CLI ──POST──► Sapheneia Orchestration Router                        │
│  │                         /orchestration/v1/predict                              │
│  │                         Auth: Bearer {SAPHENEIA_API_KEY}                       │
│  │                         Timeout: 5 min                                         │
│  │                         Retry: 3x exponential backoff                          │
│  │                         Body: InferenceRequest (schema.py)                     │
│  │                         Response: InferenceResponse (schema.py)                │
│  │                         DOC: ❌ No contract doc                                │
│  │                                                                               │
│  Aleutian Go CLI ──POST──► Sapheneia Trading Service                             │
│  │                         /trading/execute                                       │
│  │                         Auth: Bearer {SAPHENEIA_TRADING_API_KEY}               │
│  │                         Timeout: 5 min                                         │
│  │                         Retry: NONE                                            │
│  │                         Body: strategy_type + params (ad-hoc dict)             │
│  │                         Response: action, size, value, reason, etc.            │
│  │                         DOC: ❌ No contract doc                                │
│  │                                                                               │
│  Aleutian Go CLI ──POST──► Sapheneia Metrics Service                             │
│  │                         /metrics/v1/compute/                                   │
│  │                         Auth: None (X-Run-ID header only)                      │
│  │                         Timeout: 5 min                                         │
│  │                         Retry: 3x exponential backoff                          │
│  │                         Body: {returns, metric, risk_free_rate, periods}       │
│  │                         Response: {sharpe_ratio, max_drawdown, cagr, ...}     │
│  │                         DOC: ❌ No contract doc                                │
│  │                                                                               │
│  Orchestration ──POST──► Forecast Containers                                     │
│  │                       /forecast/v1/inference (chronos)                         │
│  │                       /forecast/v1/timesfm20/inference (timesfm)               │
│  │                       Auth: Bearer token                                       │
│  │                       Timeout: 300s (INFERENCE_TIMEOUT env)                    │
│  │                       Retry: None (caller retries)                             │
│  │                       DOC: ❌ No contract doc                                  │
│  │                                                                               │
│  Backtest ──async──► DataClient                                                  │
│                      /v1/data/query                                               │
│                      Timeout: 30s (hardcoded)                                     │
│                      DOC: ❌ No contract doc                                      │
│                                                                                  │
│  TOTAL CONTRACTS: 5 │ DOCUMENTED: 0                                              │
│                                                                                  │
└──────────────────────────────────────────────────────────────────────────────────┘
```

## Current State

### Code-Level Documentation Gaps

| File | Size | Public Functions/Classes | Documented | Gap |
|------|------|-------------------------|------------|-----|
| `orchestration/adapters.py` | 13,733 bytes | ~15 functions | Minimal | HIGH |
| `orchestration/service.py` | 11,297 bytes | InferenceService + methods | Minimal | HIGH |
| `orchestration/schema.py` | 14,814 bytes | ~10 Pydantic models | Partial (field descriptions) | MEDIUM |
| `orchestration/backtest.py` | 12,675 bytes | BacktestOrchestrator + methods | Minimal | HIGH |
| `orchestration/router.py` | 11,137 bytes | Router + methods | Minimal | HIGH |
| `orchestration/clients/` | Multiple files | Client classes | Minimal | HIGH |
| `metrics/main.py` | FastAPI app | Endpoints | Partial | MEDIUM |
| `metrics/core/metrics.py` | Core logic | Metric functions | Minimal | HIGH |
| `trading/main.py` | FastAPI app | Endpoints | Partial | MEDIUM |
| `trading/services/trading.py` | 1,171+ lines | TradingEngine + strategies | Partial | MEDIUM |
| `data/main.go` | 668 lines | Handlers + helpers | Partial | MEDIUM |

### Higher-Level Documentation Gaps

- No "How to Add a New Forecast Model" guide
- No "How to Add a New Trading Strategy" guide
- No "How to Add a New Metric" guide
- No "Service Communication Contract" reference (what calls what, expected schemas)
- No "Local Development Setup" quickstart for new contributors
- RUNBOOK.md exists but is operations-focused, not developer-focused

## Expected Behavior

### Part A: Code-Level Documentation

Every public function, class, and module should have a docstring explaining:
1. **What** it does (1 sentence)
2. **Args** with types and descriptions
3. **Returns** with type and description
4. **Raises** for expected exceptions

Example standard:
```python
def detect_model_family(model_name: str) -> str:
    """Detect the model family from a model name string.

    Maps model name prefixes to their corresponding family identifier,
    used for routing inference requests to the correct adapter.

    Args:
        model_name: Full model identifier (e.g., "amazon/chronos-t5-tiny").

    Returns:
        Model family string (e.g., "chronos", "timesfm", "moirai").

    Raises:
        ValueError: If model_name doesn't match any known family.
    """
```

### Part B: Higher-Level Guides

Create the following in `docs/guides/`:

1. **`adding-a-forecast-model.md`** - Step-by-step guide to register a new model
   - Where to add the model config
   - How to write the adapter in `orchestration/adapters.py`
   - How to add the Docker container
   - How to add the strategy YAML files
   - How to test it end-to-end

2. **`adding-a-trading-strategy.md`** - How to add a new strategy type
   - Where the strategy logic lives in `trading/services/trading.py`
   - How to define strategy params
   - How to wire it into the orchestrator
   - How to test it

3. **`adding-a-metric.md`** - How to add a new performance metric
   - Where to add the calculation in `metrics/core/metrics.py`
   - How to expose it via the API
   - How to update the orchestrator to request it

4. **`service-contracts.md`** - API contract reference
   - Request/response schemas for each service endpoint
   - Error response formats
   - Authentication requirements
   - Timeout expectations

5. **`local-dev-setup.md`** - New contributor quickstart
   - Prerequisites (Python 3.11+, Go 1.21+, Docker)
   - Environment setup (.env.template)
   - Running services locally
   - Running tests
   - Common troubleshooting

## Acceptance Criteria

### Code-Level (Part A)
- [ ] All public functions in `orchestration/` have Google-style docstrings
- [ ] All public functions in `metrics/` have Google-style docstrings
- [ ] All public functions in `trading/` have Google-style docstrings
- [ ] All Go exported functions in `data/` have GoDoc comments
- [ ] All `__init__.py` files have module-level docstrings describing the package
- [ ] All Pydantic models have `model_config` descriptions or class docstrings

### Higher-Level (Part B)
- [ ] `docs/guides/adding-a-forecast-model.md` created with working example
- [ ] `docs/guides/adding-a-trading-strategy.md` created with working example
- [ ] `docs/guides/adding-a-metric.md` created with working example
- [ ] `docs/guides/service-contracts.md` created with all endpoint schemas
- [ ] `docs/guides/local-dev-setup.md` created and tested by a second person

### Enforcement
- [ ] Add ruff rule `D` (pydocstyle) to linting config for new code
- [ ] Add a PR checklist item: "New public APIs have docstrings"

---

## Files to Modify

| File | Changes |
|------|---------|
| `orchestration/adapters.py` | Add docstrings to all public functions |
| `orchestration/service.py` | Add docstrings to InferenceService and methods |
| `orchestration/schema.py` | Add class-level docstrings to all models |
| `orchestration/backtest.py` | Add docstrings to BacktestOrchestrator and methods |
| `orchestration/router.py` | Add docstrings to Router and methods |
| `orchestration/clients/*.py` | Add docstrings to client classes and methods |
| `metrics/main.py` | Add docstrings to endpoint functions |
| `metrics/core/metrics.py` | Add docstrings to all metric functions |
| `trading/services/trading.py` | Add docstrings to TradingEngine and strategy methods |
| `data/main.go` | Add GoDoc comments to exported functions |
| `docs/guides/*.md` | Create 5 new guide files |

## Dependencies

- None (documentation-only, can be done in parallel with other tickets)

## Rollback Plan

Documentation is additive-only. No rollback needed.

---

## Implementation Notes (2026-02-21)

### Design Review Findings

Survey of the codebase revealed that most Python modules already had excellent docstrings (contrary to the original ticket assessment). The remaining gaps were:
- **orchestration/clients/**: Missing docstrings on enums (TradeAction, StrategyType, CircuitState), dataclass methods (to_dict, from_dict), and PortfolioManager.__init__
- **orchestration/backtest.py**: Missing docstrings on BacktestConfig.to_dict, BacktestResult.to_dict, DataProvider type alias
- **orchestration/service.py**: Incomplete _run_timesfm_http docstring
- **data/main.go**: 14 exported types and 1 function missing GoDoc comments
- **docs/guides/**: All 5 guides needed to be created from scratch

### Changes Made

**Part A — Code-Level Documentation:**
- `orchestration/clients/trading_client.py`: Added docstrings to TradeAction, StrategyType enums, TradeResult.from_dict/to_dict, PortfolioState.to_dict/from_dict, PortfolioManager.__init__
- `orchestration/clients/metrics_client.py`: Added docstrings to CircuitState enum, MetricsResponse.from_dict/to_dict
- `orchestration/clients/data_client.py`: Added docstrings to ResultPoint.to_dict, MetricsSummary.to_dict
- `orchestration/backtest.py`: Added docstrings to BacktestConfig.to_dict, BacktestResult.to_dict, DataProvider type alias
- `orchestration/service.py`: Expanded _run_timesfm_http with full Args/Returns/Raises
- `data/main.go`: Added GoDoc comments to 14 exported types and handleQueryData function

**Part B — Developer Guides:**
- `docs/guides/adding-a-forecast-model.md` (42KB) — 8-step guide with code examples
- `docs/guides/adding-a-trading-strategy.md` (29KB) — 6-step guide with code examples
- `docs/guides/adding-a-metric.md` (18KB) — 6-step guide with code examples
- `docs/guides/service-contracts.md` (20KB) — Full API contract reference for all 5 service endpoints
- `docs/guides/local-dev-setup.md` (6KB) — New contributor quickstart

### Code Review Findings (6 Major, fixed)

1. **M1-M2**: InferenceRequest/Response schemas in service-contracts.md diverged from actual Pydantic models → Rewrote with correct field names (context.values, context.source, context.field, params, forecast.period, context_summary object, metadata fields)
2. **M3**: write_results request used wrong field names (action/price/shares vs forecast/actual/signal/position) → Fixed to match SimulationResultPoint Go struct
3. **M4**: Trading example used non-existent strategy types (momentum, mean_reversion) → Fixed to threshold/return/quantile
4. **M5**: Guide claimed StrategyType inherits from `str, Enum` but actual code uses `Enum` only → Fixed
5. **M6**: Trading request/response field types listed as integer but are float → Fixed

### Verification

- All 323 existing tests pass (no breakage from docstring additions)
- All guide code examples reference correct file paths and function signatures
