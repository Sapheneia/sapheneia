# GAP-15: Error Handling for Aleutian Merge Changesets

**Priority:** HIGH
**Severity:** HIGH
**Category:** Reliability / Resilience
**Effort:** 2-3 days
**Codebase:** Sapheneia (Python + Go)
**Status:** DONE
**PR Feedback Item:** #3

---

## Architecture Review

### Reliability
- **Current Risk:** Unhandled exceptions in service code cause 500 errors with stack traces leaked to clients
- **Mitigation:** Structured error handling with custom exception hierarchy and global exception handlers
- **Failure Modes:** Service-to-service communication failures, malformed inputs, model loading failures, computation errors

### Continuity
- **Graceful Degradation:** Services should return structured error responses, never crash
- **Circuit Breaking:** Repeated downstream failures should be detected and short-circuited
- **Timeout Enforcement:** All HTTP calls must have explicit timeouts

### Integrity
- **Information Leakage Prevention:** Internal error details (stack traces, file paths, hostnames) must never appear in API responses
- **Error Logging:** Full error context logged server-side with request_id for correlation
- **Audit Trail:** All errors logged with sufficient context for post-incident analysis

### Optimization
- **Error Classification:** Distinguish between retryable (503, timeout) and non-retryable (400, 422) errors
- **Fast Failure:** Validate inputs at the boundary before doing expensive work

### Separation (Scalability)
- **Per-Service Error Contracts:** Each service defines its own error response schema
- **Cross-Service Propagation:** Downstream errors wrapped with context, not passed through raw

---

## Summary

PR feedback asks: "Where is the error handling for all the changes made in aleutian_merge and aleutian_merge_part_2?" While the trading service has custom exceptions, error handling across the orchestration, metrics, and data services is inconsistent. This ticket standardizes error handling across all services.

## Data Flow & Error Handling Gap Analysis

### End-to-End Request Error Propagation Map

Traces every error path from origin to the final consumer (Aleutian Go CLI).
`[H]` = handled, `[!]` = unhandled (propagates/crashes), `[S]` = silently swallowed.

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│         FULL SYSTEM ERROR PROPAGATION: BACKTEST REQUEST                           │
│         (Aleutian Go CLI → Sapheneia Services → Back)                            │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ALEUTIAN CLI (cmd_evaluation.go)                                                │
│  ┌────────────────────────────────────────────────────────────────────────┐       │
│  │  runEvaluation()                                                      │       │
│  │  ├── loadScenario()                                                   │       │
│  │  │   ├── File not found ──► error logged, EXIT               [H]     │       │
│  │  │   ├── Invalid YAML ──► error logged, EXIT                 [H]     │       │
│  │  │   └── URL fetch fails ──► error logged, EXIT              [H]     │       │
│  │  │                                                                    │       │
│  │  ├── NewEvaluator()                                                   │       │
│  │  │   ├── InfluxDB unreachable ──► error, EXIT                [H]     │       │
│  │  │   └── Missing env vars ──► defaults used (no error)       [H]     │       │
│  │  │                                                                    │       │
│  │  └── RunScenario(ctx, scenario, runID)                                │       │
│  │      ├── Returns (*MetricsResponse, nil) ──► display metrics  [H]     │       │
│  │      └── Returns (nil, error) ──► log error, EXIT             [H]     │       │
│  └────────────────────────────────────────────────────────────────────────┘       │
│       │                                                                          │
│       │ RunScenario() internals (evaluator.go):                                  │
│       ▼                                                                          │
│  ┌────────────────────────────────────────────────────────────────────────┐       │
│  │  PHASE 1: DATA AVAILABILITY                                           │       │
│  │  ├── CheckDataCoverage() ──► InfluxDB query                           │       │
│  │  │   ├── Query fails ──► error returned, BACKTEST STOPS       [H]     │       │
│  │  │   └── No data ──► calls data fetcher to fill gaps           [H]     │       │
│  │  │                                                                    │       │
│  │  ├── fetchOHLCFromInfluxByDateRange()                                 │       │
│  │  │   ├── Query fails ──► error returned, BACKTEST STOPS       [H]     │       │
│  │  │   ├── Empty result ──► "no data found" error, STOPS        [H]     │       │
│  │  │   └── Insufficient context ──► "not enough history", STOPS [H]     │       │
│  │  │                                                                    │       │
│  │  PHASE 1 VERDICT: Well-handled. Fatal errors stop backtest cleanly.   │       │
│  └────────────────────────────────────────────────────────────────────────┘       │
│       │                                                                          │
│       ▼                                                                          │
│  ┌────────────────────────────────────────────────────────────────────────┐       │
│  │  PHASE 2: PARALLEL FORECAST FETCH (4 workers)                         │       │
│  │                                                                       │       │
│  │  Per-job error handling (forecastWorker):                              │       │
│  │  ├── CallInferenceService() (unified mode)                            │       │
│  │  │   │                                                                │       │
│  │  │   │  ┌─ GO SIDE (evaluator.go) ─────────────────────────────┐     │       │
│  │  │   │  │  retryWithBackoff(ctx, "inference", func() error {   │     │       │
│  │  │   │  │    POST /orchestration/v1/predict                    │     │       │
│  │  │   │  │    ├── HTTP 200 ──► parse JSON response      [H]    │     │       │
│  │  │   │  │    ├── HTTP 400 ──► NON-RETRYABLE, error     [H]    │     │       │
│  │  │   │  │    ├── HTTP 500 ──► RETRY (up to 3x)         [H]    │     │       │
│  │  │   │  │    ├── Timeout ──► RETRY (up to 3x)          [H]    │     │       │
│  │  │   │  │    └── ConnectError ──► RETRY (up to 3x)     [H]    │     │       │
│  │  │   │  │  })                                                  │     │       │
│  │  │   │  │  All retries fail ──► forecastResult.err = error     │     │       │
│  │  │   │  └──────────────────────────────────────────────────────┘     │       │
│  │  │   │                                                                │       │
│  │  │   │  ┌─ PYTHON SIDE (router.py → service.py) ───────────────┐     │       │
│  │  │   │  │                                                      │     │       │
│  │  │   │  │  router.py::predict()                                │     │       │
│  │  │   │  │  ├── verify_api_key()                                │     │       │
│  │  │   │  │  │   ├── Missing key ──► HTTP 401             [H]   │     │       │
│  │  │   │  │  │   └── Wrong key ──► HTTP 403                [H]   │     │       │
│  │  │   │  │  │                                                   │     │       │
│  │  │   │  │  ├── Pydantic validation fails ──► HTTP 422    [H]   │     │       │
│  │  │   │  │  │   (FastAPI auto-generates validation error)       │     │       │
│  │  │   │  │  │                                                   │     │       │
│  │  │   │  │  ├── service.predict(request)                        │     │       │
│  │  │   │  │  │   │                                               │     │       │
│  │  │   │  │  │   ├── determine_model_family()                    │     │       │
│  │  │   │  │  │   │   └── ValueError("Unknown model") ──►        │     │       │
│  │  │   │  │  │   │       caught in router ──► HTTP 400    [H]   │     │       │
│  │  │   │  │  │   │                                               │     │       │
│  │  │   │  │  │   ├── _run_chronos_inference()                    │     │       │
│  │  │   │  │  │   │   ├── inference_to_chronos()                  │     │       │
│  │  │   │  │  │   │   │   ├── getattr fails (params not obj)     │     │       │
│  │  │   │  │  │   │   │   │   └── AttributeError ──► [!] CRASH  │     │       │
│  │  │   │  │  │   │   │   │       caught by router except ──►    │     │       │
│  │  │   │  │  │   │   │   │       HTTP 500 (generic msg)  [H]*  │     │       │
│  │  │   │  │  │   │   │   │       * But error context LOST       │     │       │
│  │  │   │  │  │   │   │   └── (no validation of input)    [!]    │     │       │
│  │  │   │  │  │   │   │                                           │     │       │
│  │  │   │  │  │   │   ├── httpx POST to model container           │     │       │
│  │  │   │  │  │   │   │   ├── resp.raise_for_status()             │     │       │
│  │  │   │  │  │   │   │   │   └── HTTPStatusError ──► [!]        │     │       │
│  │  │   │  │  │   │   │   │       PROPAGATES through predict()    │     │       │
│  │  │   │  │  │   │   │   │       caught by router except ──►    │     │       │
│  │  │   │  │  │   │   │   │       HTTP 500 (generic) [H]*        │     │       │
│  │  │   │  │  │   │   │   │       * No distinction: model 503    │     │       │
│  │  │   │  │  │   │   │   │         vs model 400 vs model 500    │     │       │
│  │  │   │  │  │   │   │   │                                       │     │       │
│  │  │   │  │  │   │   │   ├── ConnectError ──► [!] PROPAGATES    │     │       │
│  │  │   │  │  │   │   │   │   caught by router ──► HTTP 500 [H]* │     │       │
│  │  │   │  │  │   │   │   │   * Indistinguishable from other 500s│     │       │
│  │  │   │  │  │   │   │   │                                       │     │       │
│  │  │   │  │  │   │   │   └── ReadTimeout ──► [!] PROPAGATES     │     │       │
│  │  │   │  │  │   │   │       caught by router ──► HTTP 500 [H]* │     │       │
│  │  │   │  │  │   │   │       * Should be HTTP 504               │     │       │
│  │  │   │  │  │   │   │                                           │     │       │
│  │  │   │  │  │   │   └── chronos_to_inference()                  │     │       │
│  │  │   │  │  │   │       ├── KeyError (no "median"/"mean")       │     │       │
│  │  │   │  │  │   │       │   └── [!] CRASH ──► router HTTP 500  │     │       │
│  │  │   │  │  │   │       └── IndexError (empty values)           │     │       │
│  │  │   │  │  │   │           └── [!] CRASH ──► router HTTP 500  │     │       │
│  │  │   │  │  │   │                                               │     │       │
│  │  │   │  │  │   └── _run_timesfm_inference()                    │     │       │
│  │  │   │  │  │       ├── Try import timesfm (direct call)        │     │       │
│  │  │   │  │  │       │   ├── ImportError ──► fall back HTTP [H]  │     │       │
│  │  │   │  │  │       │   └── run_in_executor()                   │     │       │
│  │  │   │  │  │       │       └── NO TIMEOUT ──► [!] CAN HANG    │     │       │
│  │  │   │  │  │       │           FOREVER                         │     │       │
│  │  │   │  │  │       └── _run_timesfm_http() ──► same as chronos│     │       │
│  │  │   │  │  │                                                   │     │       │
│  │  │   │  │  └── catch ValueError ──► HTTP 400              [H]  │     │       │
│  │  │   │  │      catch Exception ──► HTTP 500 (generic)     [H]* │     │       │
│  │  │   │  │      * ALL errors become generic HTTP 500             │     │       │
│  │  │   │  │        Go side can't distinguish error types          │     │       │
│  │  │   │  └──────────────────────────────────────────────────────┘     │       │
│  │  │   │                                                                │       │
│  │  │   └── forecastResult.err set ──► skipped in trading loop    [S]   │       │
│  │  │       (logged as warning, backtest continues)                      │       │
│  │  │                                                                    │       │
│  │  PHASE 2 VERDICT:                                                     │       │
│  │  • Go retry logic: GOOD (exponential backoff, 4xx non-retryable)     │       │
│  │  • Python error handling: POOR                                        │       │
│  │    - All errors become generic HTTP 500                               │       │
│  │    - No error codes (Go can't distinguish timeout vs model error)     │       │
│  │    - Adapter crashes (KeyError/IndexError) not caught individually     │       │
│  │    - Executor call has no timeout (can hang forever)                   │       │
│  └────────────────────────────────────────────────────────────────────────┘       │
│       │                                                                          │
│       ▼                                                                          │
│  ┌────────────────────────────────────────────────────────────────────────┐       │
│  │  PHASE 3: SEQUENTIAL TRADING LOOP                                     │       │
│  │                                                                       │       │
│  │  For each day i in [startIndex, endIndex]:                            │       │
│  │  ├── Get forecastResult[i]                                            │       │
│  │  │   └── forecastResult.err != nil ──► SKIP DAY, continue      [S]   │       │
│  │  │       (no InfluxDB record for this day)                            │       │
│  │  │                                                                    │       │
│  │  ├── CallTradingService()                                             │       │
│  │  │   │                                                                │       │
│  │  │   │  ┌─ GO SIDE (evaluator.go) ────────────────────────────┐      │       │
│  │  │   │  │  POST /trading/execute                              │      │       │
│  │  │   │  │  ├── HTTP 200 ──► parse response              [H]  │      │       │
│  │  │   │  │  ├── HTTP 4xx/5xx ──► error                    [!]  │      │       │
│  │  │   │  │  │   NO RETRY! Single attempt only.                 │      │       │
│  │  │   │  │  │   Error logged, day SKIPPED                 [S]  │      │       │
│  │  │   │  │  ├── Timeout ──► error, day SKIPPED            [S]  │      │       │
│  │  │   │  │  └── ConnectError ──► error, day SKIPPED       [S]  │      │       │
│  │  │   │  └─────────────────────────────────────────────────────┘      │       │
│  │  │   │                                                                │       │
│  │  │   │  ┌─ PYTHON SIDE (trading/main.py → trading.py) ────────┐      │       │
│  │  │   │  │                                                     │      │       │
│  │  │   │  │  MIDDLEWARE CHAIN:                                   │      │       │
│  │  │   │  │  ① Request ID middleware ──► adds UUID        [H]   │      │       │
│  │  │   │  │  ② Process Time middleware ──► measures time   [H]   │      │       │
│  │  │   │  │  ③ Request Size middleware ──► max 10MB        [H]   │      │       │
│  │  │   │  │     └── EDGE: ValueError on invalid            [!]   │      │       │
│  │  │   │  │         Content-Length header ──► FALLS THROUGH      │      │       │
│  │  │   │  │         (bug: no return after except)                │      │       │
│  │  │   │  │                                                     │      │       │
│  │  │   │  │  execute_trading_signal(params)                     │      │       │
│  │  │   │  │  ├── _validate_common_params()                      │      │       │
│  │  │   │  │  │   └── InvalidParametersError ──►                 │      │       │
│  │  │   │  │  │       TradingException handler ──►               │      │       │
│  │  │   │  │  │       HTTP {exc.status_code} + error dict  [H]   │      │       │
│  │  │   │  │  │                                                  │      │       │
│  │  │   │  │  ├── generate_trading_signal()                      │      │       │
│  │  │   │  │  │   ├── InvalidStrategyError ──►                   │      │       │
│  │  │   │  │  │   │   TradingException handler ──► HTTP 400[H]   │      │       │
│  │  │   │  │  │   └── InvalidParametersError ──►                 │      │       │
│  │  │   │  │  │       TradingException handler ──► HTTP 400[H]   │      │       │
│  │  │   │  │  │                                                  │      │       │
│  │  │   │  │  ├── Capital check                                  │      │       │
│  │  │   │  │  │   └── Insufficient ──► HOLD response       [H]   │      │       │
│  │  │   │  │  │                                                  │      │       │
│  │  │   │  │  ├── Unexpected exception ──►                       │      │       │
│  │  │   │  │  │   generic_exception_handler ──►                  │      │       │
│  │  │   │  │  │   HTTP 500 (generic msg, no stack trace)   [H]   │      │       │
│  │  │   │  │  │                                                  │      │       │
│  │  │   │  │  └── NaN/Inf in calculations ──►                    │      │       │
│  │  │   │  │      std_dev/ATR no NaN check ──► [!] BAD SIGNAL   │      │       │
│  │  │   │  │      (returns invalid trading signal, not an error) │      │       │
│  │  │   │  │                                                     │      │       │
│  │  │   │  └─────────────────────────────────────────────────────┘      │       │
│  │  │                                                                    │       │
│  │  ├── StoreResult to InfluxDB (forecast_evaluations)                   │       │
│  │  │   └── Write fails ──► log error, CONTINUE               [S]       │       │
│  │  │                                                                    │       │
│  │  └── Update portfolioValues (in-memory)                               │       │
│  │                                                                       │       │
│  │  PHASE 3 VERDICT:                                                     │       │
│  │  • Trading service error handling: GOOD (custom exceptions, handlers) │       │
│  │  • Go side: NO RETRY on trading calls (single attempt)                │       │
│  │  • Silent day-skipping: backtest silently loses accuracy              │       │
│  │  • NaN propagation: NaN in calculations → bad signal (not error)      │       │
│  │  • Request size middleware bug: ValueError not returned properly       │       │
│  └────────────────────────────────────────────────────────────────────────┘       │
│       │                                                                          │
│       ▼                                                                          │
│  ┌────────────────────────────────────────────────────────────────────────┐       │
│  │  PHASE 4: METRICS COMPUTATION                                         │       │
│  │                                                                       │       │
│  │  Go side: CallMetricsService()                                        │       │
│  │  ├── len(returns) < 2 ──► return empty MetricsResponse         [H]   │       │
│  │  ├── retryWithBackoff(ctx, "metrics_service", ...)                    │       │
│  │  │   ├── HTTP 200 ──► parse MetricsResponse                    [H]   │       │
│  │  │   ├── HTTP 4xx ──► NON-RETRYABLE                            [H]   │       │
│  │  │   ├── HTTP 5xx ──► RETRY 3x                                 [H]   │       │
│  │  │   └── All fail ──► return empty MetricsResponse              [H]   │       │
│  │  │       (NON-BLOCKING: backtest still succeeds)                      │       │
│  │  │                                                                    │       │
│  │  │   ┌─ PYTHON SIDE (metrics service) ────────────────────────┐      │       │
│  │  │   │                                                        │      │       │
│  │  │   │  endpoints.py::compute_metrics()                       │      │       │
│  │  │   │  ├── Pydantic validates ComputeRequest           [H]   │      │       │
│  │  │   │  │                                                     │      │       │
│  │  │   │  ├── metric == "all" route:                            │      │       │
│  │  │   │  │   ├── _validate_returns(returns)                    │      │       │
│  │  │   │  │   │   ├── Empty ──► ValueError ──► HTTP 400   [H]  │      │       │
│  │  │   │  │   │   ├── All NaN ──► ValueError ──► HTTP 400 [H]  │      │       │
│  │  │   │  │   │   ├── < 2 valid ──► ValueError ──► 400    [H]  │      │       │
│  │  │   │  │   │   └── No DatetimeIndex ──► CREATE synthetic[H]  │      │       │
│  │  │   │  │   │                                                 │      │       │
│  │  │   │  │   ├── calculate_sharpe_ratio()                      │      │       │
│  │  │   │  │   │   ├── qs.stats.sharpe() returns float     [H]  │      │       │
│  │  │   │  │   │   ├── Returns NaN ──► 0.0                  [H]  │      │       │
│  │  │   │  │   │   └── Raises exception ──► [!] PROPAGATES      │      │       │
│  │  │   │  │   │       NO TRY/EXCEPT around qs.stats.sharpe()    │      │       │
│  │  │   │  │   │       caught by endpoint except ──► HTTP 500    │      │       │
│  │  │   │  │   │       * Error context LOST                      │      │       │
│  │  │   │  │   │                                                 │      │       │
│  │  │   │  │   ├── calculate_max_drawdown()                      │      │       │
│  │  │   │  │   │   └── Has try/except ──► returns 0.0      [H]  │      │       │
│  │  │   │  │   │       (ONLY metric with try/except)             │      │       │
│  │  │   │  │   │                                                 │      │       │
│  │  │   │  │   ├── calculate_cagr()                              │      │       │
│  │  │   │  │   │   └── NO try/except ──► [!] same as sharpe     │      │       │
│  │  │   │  │   │                                                 │      │       │
│  │  │   │  │   ├── calculate_calmar_ratio()                      │      │       │
│  │  │   │  │   │   └── NO try/except ──► [!] same as sharpe     │      │       │
│  │  │   │  │   │                                                 │      │       │
│  │  │   │  │   └── calculate_win_rate()                          │      │       │
│  │  │   │  │       └── EDGE: len=0 ──► [!] ZeroDivisionError?   │      │       │
│  │  │   │  │                                                     │      │       │
│  │  │   │  ├── catch ValueError ──► HTTP 400               [H]   │      │       │
│  │  │   │  └── catch Exception ──► HTTP 500 (generic)      [H]*  │      │       │
│  │  │   │      * quantstats crashes become generic 500s          │      │       │
│  │  │   │        Go sees "Internal Server Error", no detail      │      │       │
│  │  │   └────────────────────────────────────────────────────────┘      │       │
│  │  │                                                                    │       │
│  │  ├── StoreMetrics to InfluxDB (backtest_metrics)                      │       │
│  │  │   └── Write fails ──► log error, CONTINUE                  [S]    │       │
│  │  │                                                                    │       │
│  │  PHASE 4 VERDICT:                                                     │       │
│  │  • Go retry logic: GOOD (3x, non-blocking)                           │       │
│  │  • Python: INCONSISTENT                                               │       │
│  │    - _validate_returns: GOOD (catches edge cases)                     │       │
│  │    - calculate_max_drawdown: GOOD (has try/except)                    │       │
│  │    - calculate_sharpe/cagr/calmar: BAD (no try/except)               │       │
│  │    - calculate_win_rate: BAD (possible ZeroDivisionError)            │       │
│  │    - All errors → generic HTTP 500 (no error codes)                  │       │
│  └────────────────────────────────────────────────────────────────────────┘       │
│                                                                                  │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### Python-Side Backtest Error Propagation (orchestration/backtest.py)

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│         PYTHON BACKTEST ERROR PROPAGATION                                        │
│         (When Sapheneia orchestration runs its own backtest)                      │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  backtest.py::run_backtest(config, data_provider)                                │
│       │                                                                          │
│  INIT PHASE:                                                                     │
│  ├── InferenceService(timeout=config.timeout)                                    │
│  │   └── Invalid INFERENCE_TIMEOUT env ──► warning, use default         [H]     │
│  ├── TradingClient()                                                             │
│  │   └── TRADING_SERVICE_URL not set ──► default used                   [H]     │
│  ├── MetricsClient()                                                             │
│  │   └── METRICS_SERVICE_URL not set ──► default used                   [H]     │
│  └── generate_evaluation_dates(start, end, step)                                 │
│      ├── Invalid start_date ──► DateParseError ──► [!] PROPAGATES               │
│      ├── Invalid end_date ──► DateParseError ──► [!] PROPAGATES                 │
│      └── start > end ──► ValueError ──► [!] PROPAGATES                          │
│      NO TRY/EXCEPT around generate_evaluation_dates()                            │
│      Caller (router or CLI) would get unhandled exception                        │
│                                                                                  │
│  MAIN LOOP (per evaluation_date):                                                │
│  ┌──────────────────────────────────────────────────────────────────────┐        │
│  │  try:                                                               │        │
│  │    data = await data_provider(ticker, eval_date, context_size)      │        │
│  │    │                                                                │        │
│  │    ├── data_provider uses httpx:                                    │        │
│  │    │   ├── ConnectError ──► caught by loop try/except        [S]   │        │
│  │    │   ├── ReadTimeout ──► caught by loop try/except         [S]   │        │
│  │    │   └── HTTPStatusError ──► caught by loop try/except     [S]   │        │
│  │    │                                                                │        │
│  │    ├── data_provider returns non-list ──► len() TypeError    [S]   │        │
│  │    ├── data empty or len < 10 ──► skip date (continue)       [H]   │        │
│  │    │                                                                │        │
│  │    inference_service.predict(inference_request)                      │        │
│  │    ├── ValueError (unknown model) ──► caught               [S]     │        │
│  │    ├── httpx.HTTPStatusError ──► caught                     [S]     │        │
│  │    ├── httpx.ConnectError ──► caught                        [S]     │        │
│  │    ├── httpx.ReadTimeout ──► caught                         [S]     │        │
│  │    └── Adapter KeyError/IndexError ──► caught               [S]     │        │
│  │                                                                     │        │
│  │    forecast_price = mean(forecast_values)                           │        │
│  │    └── EDGE: forecast_values empty ──► statistics.mean([])          │        │
│  │        ──► StatisticsError ──► caught by loop                [S]   │        │
│  │                                                                     │        │
│  │    trading_client.execute_signal(...)                                │        │
│  │    ├── HTTP error ──► TradeResult.hold() (safe fallback)    [H]    │        │
│  │    └── Exception ──► TradeResult.hold() (safe fallback)     [H]    │        │
│  │                                                                     │        │
│  │    portfolio_manager.apply_trade(trade, price)                       │        │
│  │    └── No exceptions (warns on invalid state)               [H]    │        │
│  │                                                                     │        │
│  │  except Exception as e:                                             │        │
│  │    logger.error(f"Error on {eval_date}: {e}")                       │        │
│  │    continue  ◄── ALL ERRORS SILENTLY SWALLOWED                      │        │
│  │                                                                     │        │
│  │  PROBLEM: Client has NO way to know how many dates failed.          │        │
│  │  A backtest with 50% failed dates looks identical to 100% success.  │        │
│  │  BacktestResult has no "failed_dates" or "error_count" field.       │        │
│  └──────────────────────────────────────────────────────────────────────┘        │
│                                                                                  │
│  POST-LOOP METRICS:                                                              │
│  ├── prices_to_returns(equity_curve)                                             │
│  │   └── len < 2 ──► returns [] ──► MetricsClient gets []              [H]     │
│  │                                                                               │
│  ├── metrics_client.compute_metrics(returns, ...)                                │
│  │   ├── Circuit breaker OPEN ──► fallback (all zeros)                  [H]     │
│  │   ├── HTTP errors ──► retry 3x ──► fallback (all zeros)             [H]     │
│  │   └── Success ──► MetricsResponse                                    [H]     │
│  │   NO TRY/EXCEPT around this call                                     [!]     │
│  │   If compute_metrics raises unexpected exception                              │
│  │   ──► [!] ENTIRE BACKTEST CRASHES after completing all trades                │
│  │   (all trading results lost because run_backtest never returns)              │
│  │                                                                               │
│  └── Return BacktestResult                                                       │
│                                                                                  │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### Error Handling Consistency Matrix

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                   ERROR HANDLING CONSISTENCY MATRIX                               │
│                                                                                  │
│  Feature              │ Trading │ Metrics │ Orchestration │ Forecast │ Data(Go) │
│  ─────────────────────┼─────────┼─────────┼───────────────┼──────────┼──────────│
│  Custom exceptions     │   YES   │   NO    │      NO       │  PARTIAL │   N/A    │
│  Exception hierarchy   │   YES   │   NO    │      NO       │  YES *   │   N/A    │
│  Global exc handler    │   YES   │   NO    │   YES (broad) │  YES     │   N/A    │
│  Structured error resp │   YES   │   NO    │      NO       │  YES     │  YES     │
│  Error codes in resp   │   YES   │   NO    │      NO       │   NO     │   NO     │
│  Request ID in errors  │   YES   │   NO    │      NO       │   NO     │   NO     │
│  Input validation      │   YES   │ PARTIAL │   PARTIAL     │  PARTIAL │  PARTIAL │
│  Timeout enforcement   │   N/A   │   NO    │   YES (300s)  │   N/A    │  YES(10s)│
│  Retry logic           │   N/A   │   NO    │      NO       │   N/A    │   N/A    │
│  Circuit breaker       │   N/A   │   NO    │      NO       │   N/A    │   N/A    │
│  NaN/Inf handling      │   NO    │ PARTIAL │      NO       │   NO     │   NO     │
│  Stack trace prevention│   YES   │   NO    │   YES (broad) │  YES     │  YES     │
│                                                                                  │
│  * forecast/main.py uses SapheneiaException from forecast.core.exceptions        │
│    but this is NOT shared with other services                                    │
│                                                                                  │
│  LEGEND:                                                                         │
│  YES     = Implemented consistently                                              │
│  PARTIAL = Some functions, not all                                                │
│  NO      = Not implemented                                                       │
│  N/A     = Not applicable (e.g., Go service doesn't use Python exceptions)       │
│                                                                                  │
│  KEY GAPS:                                                                        │
│  1. Metrics service: NO custom exceptions, NO structured errors                  │
│  2. Orchestration: catch-all Exception handler hides root causes                 │
│  3. No shared error module across services                                       │
│  4. No error codes → Go caller can't distinguish error types                     │
│  5. NaN handling inconsistent (only max_drawdown has try/except)                 │
│                                                                                  │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### Specific Bug: Metrics Service Inconsistent Error Handling

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│  METRICS: INCONSISTENT QUANTSTATS ERROR HANDLING                                 │
│                                                                                  │
│  calculate_sharpe_ratio():     qs.stats.sharpe()   ──► NO try/except    [!]     │
│  calculate_max_drawdown():     qs.stats.max_drawdown() ──► HAS try/except [H]   │
│  calculate_cagr():             qs.stats.cagr()     ──► NO try/except    [!]     │
│  calculate_calmar_ratio():     qs.stats.calmar()   ──► NO try/except    [!]     │
│  calculate_win_rate():         manual calculation   ──► NO try/except    [!]     │
│                                                                                  │
│  WHY THIS MATTERS:                                                               │
│  ┌──────────────────────────────────────────────────────────────────┐            │
│  │  calculate_performance_metrics() calls ALL FIVE in sequence:     │            │
│  │                                                                  │            │
│  │  sharpe = calculate_sharpe_ratio(returns, ...)  # can crash      │            │
│  │  max_dd = calculate_max_drawdown(returns)       # safe           │            │
│  │  cagr   = calculate_cagr(returns, ...)          # can crash      │            │
│  │  calmar = calculate_calmar_ratio(returns, ...)  # can crash      │            │
│  │  win    = calculate_win_rate(returns)            # can crash      │            │
│  │                                                                  │            │
│  │  If sharpe crashes → max_dd, cagr, calmar, win NEVER COMPUTED    │            │
│  │  If cagr crashes → calmar, win NEVER COMPUTED                    │            │
│  │  Partial results are LOST                                        │            │
│  └──────────────────────────────────────────────────────────────────┘            │
│                                                                                  │
│  FIX: Wrap each calculation individually, return partial results.                │
│                                                                                  │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### Security: Path Traversal in router.py

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│  SECURITY VULNERABILITY: PATH TRAVERSAL (router.py::get_strategy)                │
│                                                                                  │
│  GET /orchestration/v1/strategies/{name}                                         │
│                                                                                  │
│  CURRENT CODE:                                                                   │
│  path = STRATEGIES_DIR / f"{name}.yaml"                                          │
│  if path.exists():                                                               │
│      with open(path) as f:                                                       │
│          return yaml.safe_load(f)                                                │
│                                                                                  │
│  ATTACK:                                                                         │
│  GET /orchestration/v1/strategies/../../../../../../etc/passwd                    │
│  → Reads: STRATEGIES_DIR/../../../../../../etc/passwd.yaml                        │
│  → If file exists with .yaml extension: CONTENTS LEAKED                          │
│                                                                                  │
│  RISK: LOW (requires .yaml extension) but MUST be fixed per CLAUDE.md 3.3        │
│                                                                                  │
│  FIX: Validate name matches ^[a-zA-Z0-9_-]+$ before path construction           │
│                                                                                  │
└──────────────────────────────────────────────────────────────────────────────────┘
```

## Current State

### What Exists
- **Trading service:** Has `InvalidStrategyError`, `InsufficientCapitalError`, `StrategyStoppedError`
- **Trading service:** Has FastAPI exception handlers for custom exceptions
- **Data service (Go):** Has basic HTTP error responses

### Gaps Identified

#### 1. `orchestration/service.py` - InferenceService
- **Gap:** `predict()` catches broad `Exception` or doesn't catch at all
- **Risk:** Model backend timeout or malformed response crashes the orchestrator
- **Missing:** Structured error wrapping when calling downstream forecast services
- **Missing:** Timeout enforcement on HTTP calls to model containers

#### 2. `orchestration/adapters.py` - Model Adapters
- **Gap:** Adapter functions may raise `KeyError`, `TypeError`, `ValueError` on malformed model responses
- **Risk:** A single model's bad response format crashes the entire request
- **Missing:** Validation of model response structure before conversion
- **Missing:** Clear error messages identifying which model and which field failed

#### 3. `orchestration/backtest.py` - Backtest Orchestrator
- **Gap:** Multi-step workflow with minimal error handling between steps
- **Risk:** Partial backtest execution with no cleanup or status update on failure
- **Missing:** Step-level error handling (data fetch failed vs. forecast failed vs. trading failed)
- **Missing:** Partial result preservation on mid-backtest failure

#### 4. `orchestration/router.py` - Request Routing
- **Gap:** Route resolution may silently fall through for unknown models
- **Risk:** Requests to unsupported models get routed incorrectly or hang
- **Missing:** Explicit unknown-model error response

#### 5. `orchestration/clients/` - Service Clients
- **Gap:** HTTP clients may not handle all failure modes
- **Risk:** Connection refused, timeout, non-JSON response, partial response
- **Missing:** Retry logic with backoff for transient failures
- **Missing:** Response validation before deserialization

#### 6. `metrics/main.py` and `metrics/core/metrics.py`
- **Gap:** quantstats calculations can raise exceptions on edge-case data
- **Risk:** Empty returns array, NaN values, single-element array cause 500
- **Missing:** Input validation before quantstats calls
- **Missing:** Graceful handling of quantstats internal errors

#### 7. `forecast/` - Forecast Service
- **Gap:** Model loading failures not handled gracefully
- **Risk:** GPU OOM, corrupted model weights, missing model files
- **Missing:** Health check that verifies model is loaded and ready
- **Missing:** Structured error response for model loading failures

## Expected Behavior

### Error Response Schema (Standard Across All Services)

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Human-readable error description",
    "request_id": "uuid-from-header",
    "details": {}
  }
}
```

### Error Code Taxonomy

| Code | HTTP Status | Retryable | Description |
|------|-------------|-----------|-------------|
| `VALIDATION_ERROR` | 400 | No | Input failed validation |
| `INVALID_MODEL` | 400 | No | Unknown or unsupported model |
| `INVALID_STRATEGY` | 400 | No | Unknown strategy type or params |
| `INSUFFICIENT_DATA` | 422 | No | Not enough data for computation |
| `INSUFFICIENT_CAPITAL` | 422 | No | Not enough capital for trade |
| `MODEL_UNAVAILABLE` | 503 | Yes | Model service is down or loading |
| `SERVICE_UNAVAILABLE` | 503 | Yes | Downstream service unreachable |
| `COMPUTATION_ERROR` | 500 | No | Internal calculation failure |
| `TIMEOUT` | 504 | Yes | Downstream service timed out |

### Implementation Design

#### A. Shared Error Module (`shared/errors.py`)

```python
"""Standardized error handling for Sapheneia services."""

from enum import Enum
from dataclasses import dataclass
from typing import Any


class ErrorCode(str, Enum):
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INVALID_MODEL = "INVALID_MODEL"
    INVALID_STRATEGY = "INVALID_STRATEGY"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    INSUFFICIENT_CAPITAL = "INSUFFICIENT_CAPITAL"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    COMPUTATION_ERROR = "COMPUTATION_ERROR"
    TIMEOUT = "TIMEOUT"


class SapheneiaError(Exception):
    """Base exception for all Sapheneia services."""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        status_code: int = 500,
        details: dict[str, Any] | None = None,
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class ValidationError(SapheneiaError):
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(ErrorCode.VALIDATION_ERROR, message, 400, details)


class ModelUnavailableError(SapheneiaError):
    def __init__(self, model_name: str):
        super().__init__(
            ErrorCode.MODEL_UNAVAILABLE,
            f"Model '{model_name}' is not available",
            503,
            {"model": model_name},
        )


class ServiceUnavailableError(SapheneiaError):
    def __init__(self, service_name: str, reason: str = ""):
        super().__init__(
            ErrorCode.SERVICE_UNAVAILABLE,
            f"Service '{service_name}' is unavailable: {reason}",
            503,
            {"service": service_name},
        )


class TimeoutError(SapheneiaError):
    def __init__(self, service_name: str, timeout_seconds: float):
        super().__init__(
            ErrorCode.TIMEOUT,
            f"Request to '{service_name}' timed out after {timeout_seconds}s",
            504,
            {"service": service_name, "timeout_seconds": timeout_seconds},
        )


class InsufficientDataError(SapheneiaError):
    def __init__(self, message: str, required: int = 0, provided: int = 0):
        super().__init__(
            ErrorCode.INSUFFICIENT_DATA,
            message,
            422,
            {"required": required, "provided": provided},
        )


class ComputationError(SapheneiaError):
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(ErrorCode.COMPUTATION_ERROR, message, 500, details)
```

#### B. FastAPI Global Exception Handler (per service)

```python
from fastapi import Request
from fastapi.responses import JSONResponse

async def sapheneia_exception_handler(request: Request, exc: SapheneiaError):
    """Global handler that converts SapheneiaError to structured JSON response."""
    request_id = request.headers.get("X-Request-ID", "unknown")
    logger.error(
        "Request failed",
        error_code=exc.code.value,
        message=exc.message,
        request_id=request_id,
        details=exc.details,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code.value,
                "message": exc.message,
                "request_id": request_id,
                "details": exc.details,
            }
        },
    )

async def unhandled_exception_handler(request: Request, exc: Exception):
    """Catch-all handler that prevents stack trace leakage."""
    request_id = request.headers.get("X-Request-ID", "unknown")
    logger.exception("Unhandled exception", request_id=request_id)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An internal error occurred",
                "request_id": request_id,
            }
        },
    )
```

#### C. Service Client Retry Pattern

```python
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

class ServiceClient:
    """Base client with retry, timeout, and error wrapping."""

    def __init__(self, base_url: str, service_name: str, timeout: float = 30.0):
        self.base_url = base_url
        self.service_name = service_name
        self.client = httpx.Client(timeout=timeout)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.ConnectError, httpx.ReadTimeout)),
    )
    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        try:
            response = self.client.request(method, f"{self.base_url}{path}", **kwargs)
            if response.status_code >= 500:
                raise ServiceUnavailableError(self.service_name, f"HTTP {response.status_code}")
            return response
        except httpx.ConnectError:
            raise ServiceUnavailableError(self.service_name, "Connection refused")
        except httpx.ReadTimeout:
            raise TimeoutError(self.service_name, self.client.timeout.read)
```

#### D. Specific Error Handling Locations

##### orchestration/adapters.py
```python
def convert_unified_to_model_format(request, model_family):
    """Wrap adapter conversion with structured error handling."""
    try:
        adapter = ADAPTER_MAP.get(model_family)
        if adapter is None:
            raise ValidationError(
                f"No adapter for model family '{model_family}'",
                details={"model_family": model_family, "supported": list(ADAPTER_MAP.keys())},
            )
        return adapter(request)
    except KeyError as e:
        raise ValidationError(
            f"Missing required field in request for {model_family}: {e}",
            details={"model_family": model_family, "missing_field": str(e)},
        )
    except (TypeError, ValueError) as e:
        raise ValidationError(
            f"Invalid data format for {model_family}: {e}",
            details={"model_family": model_family},
        )
```

##### metrics/core/metrics.py
```python
def compute_metrics(returns: list[float], risk_free_rate: float = 0.0) -> dict:
    """Wrap quantstats calls with input validation and error handling."""
    if not returns:
        raise InsufficientDataError("Returns array is empty", required=2, provided=0)
    if len(returns) < 2:
        raise InsufficientDataError("Need at least 2 returns", required=2, provided=len(returns))

    # Sanitize NaN/Inf values
    clean_returns = [r for r in returns if math.isfinite(r)]
    if len(clean_returns) < len(returns):
        logger.warning("Removed %d non-finite values from returns", len(returns) - len(clean_returns))

    try:
        # quantstats calculations...
        pass
    except Exception as e:
        raise ComputationError(
            f"Metrics calculation failed: {e}",
            details={"returns_count": len(clean_returns)},
        )
```

## Acceptance Criteria

### Error Module
- [x] Create `shared/errors.py` with base exception hierarchy
- [x] All error codes map to appropriate HTTP status codes
- [x] Error responses never contain stack traces, file paths, or internal details

### Per-Service Integration
- [x] `orchestration/` services use SapheneiaError subclasses
- [x] `metrics/` service has global exception handler and input validation
- [x] `trading/` service registers shared handlers alongside existing TradingException hierarchy
- [x] `forecast/` service registers shared error handler for orchestration code
- [x] All FastAPI apps register both `sapheneia_error_handler` and `generic_error_handler`

### Client Error Handling
- [x] All service clients have explicit timeouts (InferenceService, MetricsClient, TradingClient)
- [x] MetricsClient retries on transient failures (already had retry + circuit breaker)
- [x] Orchestration service wraps connection errors in ServiceUnavailableError
- [x] Orchestration adapters validate response structure before deserialization

### Logging
- [x] All errors logged with request_id for correlation
- [x] All errors logged with sufficient context (service name, endpoint, input summary)
- [x] No PII or secrets in error logs (per CLAUDE.md compliance requirements)

### Edge Cases
- [x] Empty input arrays handled gracefully (not 500)
- [x] NaN/Inf values in numeric inputs detected and handled
- [x] Downstream service errors wrapped with structured error types
- [x] Partial metric results preserved (individual try/except per metric)

## Implementation Summary (Completed 2026-02-21)

### Files Created
| File | Description |
|------|-------------|
| `shared/__init__.py` | Package init with re-exports |
| `shared/errors.py` | `SapheneiaError` base class, 6 subclasses, `ErrorCode` enum, `register_error_handlers(app)` |

### Files Modified
| File | Key Changes |
|------|-------------|
| `metrics/core/metrics.py` | Individual try/except per metric (fixes partial-results-lost bug), NaN/Inf check in `_validate_returns` |
| `metrics/routes/endpoints.py` | `HTTPException(400/500)` → `ValidationError`/`ComputationError` |
| `metrics/main.py` | `register_error_handlers(app)` |
| `orchestration/router.py` | Path traversal regex fix on `get_strategy()`, structured errors on predict/legacy |
| `orchestration/service.py` | HTTP errors → `ServiceUnavailableError`/`ServiceTimeoutError`/`ValidationError`/`ModelUnavailableError`; `asyncio.wait_for()` timeout on TimesFM executor |
| `orchestration/adapters.py` | Response parsing → `ComputationError` for missing/empty keys |
| `orchestration/backtest.py` | Added `failed_dates`/`error_count` to `BacktestResult`; metrics call wrapped in try/except |
| `trading/main.py` | `register_error_handlers(app)`; fixed middleware bug (missing return after invalid Content-Length) |
| `forecast/main.py` | `register_error_handlers(app)` alongside existing `SapheneiaException` handler |
| `tests/metrics/test_endpoints.py` | Updated assertion to match new structured error format |

### Scope Control (NOT Done - by design)
- Did NOT migrate `TradingException` to inherit from `SapheneiaError` (would break trading tests)
- Did NOT migrate `forecast/core/exceptions.py::SapheneiaException` (would require touching all forecast code)
- Did NOT add retry logic to orchestration clients (existing patterns sufficient)
- Did NOT add `tenacity` dependency

### Verification
- 99 tests pass, 0 failures, 20 skipped

---

## Dependencies

- Should be implemented BEFORE GAP-14 (Unit Testing) so tests can validate error behavior
- Coordinate with trading service's existing exception classes to avoid breaking changes

## Files to Create/Modify

| File | Action | Changes |
|------|--------|---------|
| `shared/__init__.py` | Create | Package init |
| `shared/errors.py` | Create | Error hierarchy and codes |
| `orchestration/service.py` | Modify | Wrap predict() with error handling |
| `orchestration/adapters.py` | Modify | Add validation and error wrapping |
| `orchestration/backtest.py` | Modify | Step-level error handling |
| `orchestration/router.py` | Modify | Unknown model error |
| `orchestration/clients/*.py` | Modify | Add retry, timeout, error wrapping |
| `metrics/main.py` | Modify | Register global exception handlers |
| `metrics/core/metrics.py` | Modify | Input validation, quantstats error handling |
| `trading/main.py` | Modify | Register global exception handlers, wrap existing exceptions |
| `forecast/main.py` | Modify | Model loading error handling |

## Rollback Plan

Error handling is additive. If new error handling introduces regressions:
1. Revert to bare `except Exception` handlers
2. Keep the error module for future use
3. Existing behavior (500 with stack trace) is worse but functional
