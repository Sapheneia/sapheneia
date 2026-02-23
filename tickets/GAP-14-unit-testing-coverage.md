# GAP-14: Unit Testing for Aleutian Merge Changesets

**Priority:** HIGH
**Severity:** HIGH
**Category:** Quality / Testing
**Effort:** 3-4 days
**Codebase:** Sapheneia (Python + Go)
**Status:** COMPLETED
**PR Feedback Item:** #2

---

## Architecture Review

### Reliability
- **Current Risk:** Untested code paths may contain latent bugs that surface in production
- **Mitigation:** Unit tests with mocked dependencies for all business logic
- **Coverage Target:** 80%+ line coverage on new code in aleutian_merge changesets
- **CI Gate:** Tests must pass before merge; coverage must not regress

### Continuity
- **State Management:** Tests use fixtures and mocks - no external service dependencies
- **Reproducibility:** All tests must be deterministic (no time-dependent or network-dependent tests)

### Integrity
- **Data Validation:** Test edge cases: empty inputs, malformed data, boundary values
- **Contract Testing:** Validate request/response schemas match service expectations

### Optimization
- **Parallelism:** Tests should be independent and parallelizable
- **Speed:** Unit tests should complete in < 30 seconds total

### Separation (Scalability)
- **Unit vs Integration:** This ticket focuses on unit tests only (mocked dependencies)
- **Integration tests:** Covered by existing test infrastructure, not in scope here

---

## Summary

PR feedback asks: "Where are the unit tests for the changes in aleutian_merge and aleutian_merge_part_2?" While some tests exist (trading/tests/, tests/orchestration/, tests/metrics/), significant gaps remain in coverage for the core business logic introduced in these changesets.

## Data Flow & Test Coverage Gap Analysis

### Complete Code Path Map with Test Coverage Status

Shows every code path through the system and whether it has test coverage.
`[T]` = tested, `[!]` = untested, `[~]` = partially tested.

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│              ORCHESTRATION MODULE: CODE PATH / TEST COVERAGE MAP                 │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  adapters.py::determine_model_family(model_name)                                 │
│  ┌────────────────────────────────────────────────────────────────────────┐       │
│  │  Input: model_name (str)                                              │       │
│  │       │                                                               │       │
│  │       ▼                                                               │       │
│  │  model_lower = model_name.lower()                                     │       │
│  │       │                                                               │       │
│  │       ├── "chronos" in model_lower? ──► return "chronos"        [!]   │       │
│  │       ├── "timesfm" in model_lower? ──► return "timesfm"        [!]   │       │
│  │       ├── "moirai" in model_lower?  ──► return "moirai"         [!]   │       │
│  │       ├── "granite" in model_lower? ──► return "granite"        [!]   │       │
│  │       ├── "moment" in model_lower?  ──► return "moment"         [!]   │       │
│  │       ├── "lag-llama" in model_lower? ► return "lag-llama"      [!]   │       │
│  │       ├── "yinglong" in model_lower? ─► return "yinglong"       [!]   │       │
│  │       └── no match ───────────────────► raise ValueError        [!]   │       │
│  │                                                                       │       │
│  │  EDGE CASES NEEDING TESTS:                                            │       │
│  │  • model_name = None  ──► AttributeError (crash)               [!]   │       │
│  │  • model_name = ""    ──► ValueError                            [!]   │       │
│  │  • model_name = "CHRONOS" (uppercase) ──► should match          [!]   │       │
│  │  • model_name = "amazon/chronos-t5-tiny" (full path) ──► match  [!]   │       │
│  └────────────────────────────────────────────────────────────────────────┘       │
│                                                                                  │
│  adapters.py::inference_to_chronos(request) → dict                               │
│  ┌────────────────────────────────────────────────────────────────────────┐       │
│  │  Input: InferenceRequest                                              │       │
│  │       │                                                               │       │
│  │       ├── request.context.values ──► "context" field            [!]   │       │
│  │       ├── request.horizon.length ──► "prediction_length"        [!]   │       │
│  │       ├── request.params (Optional)                                   │       │
│  │       │   ├── params exists ──► getattr(params, 'num_samples',20)[!]  │       │
│  │       │   │                    getattr(params, 'temperature',1.0)[!]  │       │
│  │       │   │                    getattr(params, 'top_k', 50)      [!]  │       │
│  │       │   │                    getattr(params, 'top_p', 1.0)     [!]  │       │
│  │       │   └── params is None ─► defaults used                   [!]   │       │
│  │       │                                                               │       │
│  │  EDGE CASES:                                                          │       │
│  │  • request.params is dict (not ModelParams obj) → getattr fails [!]   │       │
│  │  • request.context.values is empty list                         [!]   │       │
│  └────────────────────────────────────────────────────────────────────────┘       │
│                                                                                  │
│  adapters.py::chronos_to_inference(response, request, time_ms)                   │
│  ┌────────────────────────────────────────────────────────────────────────┐       │
│  │  Input: dict (from model), InferenceRequest, int                      │       │
│  │       │                                                               │       │
│  │       ├── response has "prediction" key? ──► use it             [!]   │       │
│  │       └── no "prediction" key ──────────► use entire response   [!]   │       │
│  │       │                                                               │       │
│  │       ├── prediction has "median"? ──► use as forecast_values   [!]   │       │
│  │       └── no "median" ──► use "mean" key                        [!]   │       │
│  │       │                                                               │       │
│  │       ├── has quantile data? ──► build QuantileForecast list    [!]   │       │
│  │       └── no quantiles ──► None                                 [!]   │       │
│  │       │                                                               │       │
│  │       └── calculate_forecast_dates()                            [!]   │       │
│  │                                                                       │       │
│  │  EDGE CASES:                                                          │       │
│  │  • Neither "median" nor "mean" in prediction → KeyError crash   [!]   │       │
│  │  • Empty prediction values → empty forecast                     [!]   │       │
│  └────────────────────────────────────────────────────────────────────────┘       │
│                                                                                  │
│  adapters.py::timesfm_to_inference(response, request, time_ms)                   │
│  ┌────────────────────────────────────────────────────────────────────────┐       │
│  │  Input: dict (from model), InferenceRequest, int                      │       │
│  │       │                                                               │       │
│  │       └── response["point_forecast"][0]                         [!]   │       │
│  │           UNSAFE: IndexError if point_forecast is empty list          │       │
│  │           UNSAFE: KeyError if point_forecast key missing              │       │
│  │                                                                       │       │
│  │  EDGE CASES:                                                          │       │
│  │  • point_forecast = [] → IndexError                             [!]   │       │
│  │  • point_forecast = [[]] → empty values                         [!]   │       │
│  │  • point_forecast missing entirely                              [!]   │       │
│  └────────────────────────────────────────────────────────────────────────┘       │
│                                                                                  │
│  adapters.py::parse_date(date_str, field_name)                                   │
│  ┌────────────────────────────────────────────────────────────────────────┐       │
│  │       ├── date_str is empty ──► DateParseError                  [!]   │       │
│  │       ├── "YYYY-MM-DD" format ──► datetime                      [!]   │       │
│  │       ├── "YYYYMMDD" format (8 digits) ──► datetime             [!]   │       │
│  │       ├── ISO format with "Z" ──► datetime                      [!]   │       │
│  │       └── none match ──► DateParseError                         [!]   │       │
│  └────────────────────────────────────────────────────────────────────────┘       │
│                                                                                  │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  service.py::InferenceService.predict(request)                                   │
│  ┌────────────────────────────────────────────────────────────────────────┐       │
│  │  Input: InferenceRequest                                              │       │
│  │       │                                                               │       │
│  │       ▼                                                               │       │
│  │  determine_model_family(request.model)                                │       │
│  │       │                                                               │       │
│  │       ├── "chronos" ──► _run_chronos_inference(request)               │       │
│  │       │   │                                                           │       │
│  │       │   ├── inference_to_chronos(request) ── adapter          [!]   │       │
│  │       │   ├── httpx POST to CHRONOS_SERVICE_URL                 [!]   │       │
│  │       │   │   ├── HTTP 200 ──► parse JSON                       [!]   │       │
│  │       │   │   ├── HTTP 4xx ──► HTTPStatusError (propagates)     [!]   │       │
│  │       │   │   ├── HTTP 5xx ──► HTTPStatusError (propagates)     [!]   │       │
│  │       │   │   ├── Timeout ──► ReadTimeout (propagates)          [!]   │       │
│  │       │   │   └── ConnectError ──► (propagates)                 [!]   │       │
│  │       │   └── chronos_to_inference() ── adapter                 [!]   │       │
│  │       │                                                               │       │
│  │       ├── "timesfm" ──► _run_timesfm_inference(request)               │       │
│  │       │   │                                                           │       │
│  │       │   ├── Try: import timesfm model (direct call)           [!]   │       │
│  │       │   │   ├── Success ──► run_in_executor()                 [!]   │       │
│  │       │   │   │   └── No timeout on executor ──► could hang     [!]   │       │
│  │       │   │   └── ImportError ──► fall back to HTTP             [!]   │       │
│  │       │   │                                                           │       │
│  │       │   └── _run_timesfm_http(request, start_time)            [!]   │       │
│  │       │       ├── httpx POST to TIMESFM_SERVICE_URL             [!]   │       │
│  │       │       └── (same error paths as chronos)                 [!]   │       │
│  │       │                                                               │       │
│  │       └── else ──► _run_chronos_inference (fallback)            [!]   │       │
│  │                                                                       │       │
│  │  ALL PATHS UNTESTED: 0 of ~15 code paths have unit tests             │       │
│  └────────────────────────────────────────────────────────────────────────┘       │
│                                                                                  │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  backtest.py::run_backtest(config, data_provider, run_id, callback)              │
│  ┌────────────────────────────────────────────────────────────────────────┐       │
│  │                                                                       │       │
│  │  PHASE 0: INITIALIZATION                                              │       │
│  │  ├── Generate run_id if not provided                            [!]   │       │
│  │  ├── Create InferenceService(timeout=config.inference_timeout)  [!]   │       │
│  │  ├── Create TradingClient()                                     [!]   │       │
│  │  ├── Create MetricsClient()                                     [!]   │       │
│  │  ├── Create PortfolioManager(config.initial_capital)            [!]   │       │
│  │  └── generate_evaluation_dates(start, end, step)                [!]   │       │
│  │       ├── parse start_date ──► DateParseError?                  [!]   │       │
│  │       ├── parse end_date ──► DateParseError?                    [!]   │       │
│  │       ├── start > end ──► ValueError                            [!]   │       │
│  │       └── skip weekends (Sat=5, Sun=6)                          [!]   │       │
│  │                                                                       │       │
│  │  MAIN LOOP: for each evaluation_date                                  │       │
│  │  ┌──────────────────────────────────────────────────────────┐         │       │
│  │  │  try:                                                    │         │       │
│  │  │  PHASE 1: DATA FETCH                                     │         │       │
│  │  │  ├── data_provider(ticker, eval_date, context_size) [!]  │         │       │
│  │  │  │   ├── Returns data ──► continue                  [!]  │         │       │
│  │  │  │   ├── Returns empty ──► skip date (continue)     [!]  │         │       │
│  │  │  │   └── Raises exception ──► caught at loop level  [!]  │         │       │
│  │  │  ├── len(data) < 10 ──► skip date (continue)        [!]  │         │       │
│  │  │  └── current_price = data[-1]                        [!]  │         │       │
│  │  │                                                          │         │       │
│  │  │  PHASE 2: FORECAST                                       │         │       │
│  │  │  ├── Build InferenceRequest                          [!]  │         │       │
│  │  │  ├── inference_service.predict(request)              [!]  │         │       │
│  │  │  │   ├── Success ──► extract forecast_values         [!]  │         │       │
│  │  │  │   └── Exception ──► caught at loop level          [!]  │         │       │
│  │  │  └── forecast_price = mean(forecast_values)          [!]  │         │       │
│  │  │      └── EDGE: empty forecast_values ──► crash       [!]  │         │       │
│  │  │                                                          │         │       │
│  │  │  PHASE 3: TRADING                                        │         │       │
│  │  │  ├── trading_client.execute_signal(...)              [!]  │         │       │
│  │  │  │   ├── Success ──► TradeResult                     [!]  │         │       │
│  │  │  │   └── Exception ──► caught at loop level          [!]  │         │       │
│  │  │  └── Returns: action, size, value, position_after    [!]  │         │       │
│  │  │                                                          │         │       │
│  │  │  PHASE 4: PORTFOLIO UPDATE                               │         │       │
│  │  │  ├── portfolio_manager.apply_trade(result, price)    [!]  │         │       │
│  │  │  ├── Check should_checkpoint()                       [!]  │         │       │
│  │  │  └── callback(checkpoint) if provided                [!]  │         │       │
│  │  │                                                          │         │       │
│  │  │  except Exception:                                       │         │       │
│  │  │  └── Log error, CONTINUE to next date                [!]  │         │       │
│  │  │      (Silent failure - client can't tell)                │         │       │
│  │  └──────────────────────────────────────────────────────────┘         │       │
│  │                                                                       │       │
│  │  PHASE 5: METRICS                                                     │       │
│  │  ├── prices_to_returns(equity_curve)                          [!]     │       │
│  │  ├── metrics_client.compute_metrics(returns, rf, periods)     [!]     │       │
│  │  │   └── NO try/except here ──► exception crashes backtest    [!]     │       │
│  │  └── Return BacktestResult                                    [!]     │       │
│  │                                                                       │       │
│  │  TOTAL UNTESTED PATHS: ~30                                            │       │
│  └────────────────────────────────────────────────────────────────────────┘       │
│                                                                                  │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  BacktestResult.total_return (property)                                          │
│  ┌────────────────────────────────────────────────────────────────────────┐       │
│  │  ├── len(equity_curve) < 2 ──► return 0.0                     [!]     │       │
│  │  └── (final - initial) / initial                               [!]     │       │
│  │      └── EDGE: initial = 0 ──► ZeroDivisionError crash         [!]     │       │
│  └────────────────────────────────────────────────────────────────────────┘       │
│                                                                                  │
└──────────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────────┐
│              METRICS MODULE: CODE PATH / TEST COVERAGE MAP                       │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  metrics/core/metrics.py::_validate_returns(returns)                             │
│  ┌────────────────────────────────────────────────────────────────────────┐       │
│  │  ├── isinstance(returns, list) ──► pd.Series(returns)           [~]   │       │
│  │  ├── isinstance(returns, np.ndarray) ──► pd.Series(returns)     [~]   │       │
│  │  ├── isinstance(returns, pd.Series) ──► use as-is               [~]   │       │
│  │  ├── returns is empty ──► raise ValueError                      [!]   │       │
│  │  ├── all NaN ──► raise ValueError                               [!]   │       │
│  │  ├── < 2 valid values after dropna ──► raise ValueError         [!]   │       │
│  │  └── no DatetimeIndex ──► CREATE synthetic dates (2020-01-01+)  [!]   │       │
│  │      (quantstats requires DatetimeIndex)                              │       │
│  └────────────────────────────────────────────────────────────────────────┘       │
│                                                                                  │
│  metrics/core/metrics.py::calculate_sharpe_ratio(returns, rf, periods)           │
│  ┌────────────────────────────────────────────────────────────────────────┐       │
│  │  ├── qs.stats.sharpe(returns, rf, periods)                      [~]   │       │
│  │  │   ├── Returns float ──► return it                            [~]   │       │
│  │  │   ├── Returns NaN ──► return 0.0                             [!]   │       │
│  │  │   └── Raises exception ──► PROPAGATES (no try/except!)       [!]   │       │
│  │  │       EDGE: quantstats internal error on edge data                 │       │
│  └────────────────────────────────────────────────────────────────────────┘       │
│                                                                                  │
│  metrics/core/metrics.py::calculate_max_drawdown(returns)                        │
│  ┌────────────────────────────────────────────────────────────────────────┐       │
│  │  try:                                                                 │       │
│  │  ├── qs.stats.max_drawdown(returns)                             [~]   │       │
│  │  │   ├── Returns float ──► return it                            [~]   │       │
│  │  │   └── Returns NaN ──► return 0.0                             [!]   │       │
│  │  except Exception:                                                    │       │
│  │  └── log warning, return 0.0                                    [!]   │       │
│  │  (ONLY metric function with try/except)                               │       │
│  └────────────────────────────────────────────────────────────────────────┘       │
│                                                                                  │
│  metrics/core/metrics.py::calculate_cagr(returns, periods)                       │
│  ┌────────────────────────────────────────────────────────────────────────┐       │
│  │  ├── qs.stats.cagr(returns, periods)                            [~]   │       │
│  │  │   ├── Returns float ──► return it                            [~]   │       │
│  │  │   ├── Returns NaN ──► return 0.0                             [!]   │       │
│  │  │   └── Raises exception ──► PROPAGATES (no try/except!)       [!]   │       │
│  └────────────────────────────────────────────────────────────────────────┘       │
│                                                                                  │
│  metrics/core/metrics.py::calculate_calmar_ratio(returns, periods)               │
│  ┌────────────────────────────────────────────────────────────────────────┐       │
│  │  (same pattern as cagr - no try/except, NaN check only)         [!]   │       │
│  └────────────────────────────────────────────────────────────────────────┘       │
│                                                                                  │
│  metrics/core/metrics.py::calculate_win_rate(returns)                            │
│  ┌────────────────────────────────────────────────────────────────────────┐       │
│  │  ├── count(r > 0) / len(returns)                                [!]   │       │
│  │  │   └── EDGE: len(returns) = 0 ──► ZeroDivisionError?         [!]   │       │
│  └────────────────────────────────────────────────────────────────────────┘       │
│                                                                                  │
│  metrics/routes/endpoints.py::compute_metrics()                                  │
│  ┌────────────────────────────────────────────────────────────────────────┐       │
│  │  metric param routes to:                                              │       │
│  │  ├── "performance" ──► calculate_performance_metrics()          [!]   │       │
│  │  ├── "all" ──► call each metric function individually           [!]   │       │
│  │  ├── "sharpe" ──► calculate_sharpe_ratio()                      [!]   │       │
│  │  ├── "max_drawdown" ──► calculate_max_drawdown()                [!]   │       │
│  │  ├── "cagr" ──► calculate_cagr()                                [!]   │       │
│  │  ├── "calmar" ──► calculate_calmar_ratio()                      [!]   │       │
│  │  └── "win_rate" ──► calculate_win_rate()                        [!]   │       │
│  │                                                                       │       │
│  │  Error handling:                                                      │       │
│  │  ├── ValueError ──► HTTP 400                                    [!]   │       │
│  │  └── Exception ──► HTTP 500 (generic message)                   [!]   │       │
│  └────────────────────────────────────────────────────────────────────────┘       │
│                                                                                  │
└──────────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────────┐
│              CLIENT MODULE: CODE PATH / TEST COVERAGE MAP                        │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  clients/metrics_client.py::MetricsClient.compute_metrics(returns, ...)          │
│  ┌────────────────────────────────────────────────────────────────────────┐       │
│  │  INPUT VALIDATION:                                                    │       │
│  │  ├── len(returns) < 2 ──► return fallback (all zeros)           [!]   │       │
│  │  └── filter NaN/Inf from returns                                [!]   │       │
│  │                                                                       │       │
│  │  CIRCUIT BREAKER CHECK:                                               │       │
│  │  ├── CLOSED ──► proceed                                         [!]   │       │
│  │  ├── OPEN + recovery timeout passed ──► HALF_OPEN, proceed      [!]   │       │
│  │  ├── OPEN + recovery timeout NOT passed ──► return fallback     [!]   │       │
│  │  └── HALF_OPEN ──► proceed (one test request)                   [!]   │       │
│  │                                                                       │       │
│  │  RETRY LOOP (max 3 attempts):                                         │       │
│  │  ├── Attempt N:                                                       │       │
│  │  │   ├── httpx POST /metrics/v1/compute/                        [!]   │       │
│  │  │   │   ├── HTTP 200 ──► parse JSON ──► on_success() ──► return[!]   │       │
│  │  │   │   ├── HTTPStatusError ──► log, continue retry            [!]   │       │
│  │  │   │   ├── RequestError ──► log, continue retry               [!]   │       │
│  │  │   │   └── Exception ──► log, continue retry                  [!]   │       │
│  │  │   └── sleep(2^attempt seconds) between retries               [!]   │       │
│  │  └── All retries exhausted ──► on_failure() ──► return fallback [!]   │       │
│  │                                                                       │       │
│  │  TOTAL PATHS: 12  TESTED: 0                                          │       │
│  └────────────────────────────────────────────────────────────────────────┘       │
│                                                                                  │
│  clients/trading_client.py::TradingClient.execute_signal(...)                    │
│  ┌────────────────────────────────────────────────────────────────────────┐       │
│  │  PAYLOAD CONSTRUCTION:                                                │       │
│  │  ├── strategy_type == THRESHOLD + no params                           │       │
│  │  │   └── Apply defaults: threshold_type=absolute, value=2.0     [!]   │       │
│  │  ├── Merge strategy_params into payload                         [!]   │       │
│  │  └── Add portfolio state fields                                 [!]   │       │
│  │                                                                       │       │
│  │  HTTP CALL:                                                           │       │
│  │  ├── httpx POST /trading/execute                                [!]   │       │
│  │  │   ├── HTTP 200 ──► parse TradeResult.from_dict()             [!]   │       │
│  │  │   ├── HTTPStatusError ──► TradeResult.hold(error_msg)        [!]   │       │
│  │  │   ├── RequestError ──► TradeResult.hold(error_msg)           [!]   │       │
│  │  │   └── Exception ──► TradeResult.hold(error_msg)              [!]   │       │
│  │  │                                                                    │       │
│  │  (All errors degrade to HOLD - never crashes)                         │       │
│  │  TOTAL PATHS: 8  TESTED: 0                                           │       │
│  └────────────────────────────────────────────────────────────────────────┘       │
│                                                                                  │
│  clients/data_client.py::DataClient.query_data(ticker, days, end_date)           │
│  ┌────────────────────────────────────────────────────────────────────────┐       │
│  │  ├── httpx POST /v1/data/query                                  [!]   │       │
│  │  │   ├── HTTP 200 ──► extract close prices from response        [!]   │       │
│  │  │   ├── HTTPStatusError ──► log, return []                     [!]   │       │
│  │  │   ├── RequestError ──► log, return []                        [!]   │       │
│  │  │   └── Exception ──► log, return []                           [!]   │       │
│  │  │                                                                    │       │
│  │  (All errors return empty list - silent failure)                      │       │
│  │  TOTAL PATHS: 5  TESTED: 0                                           │       │
│  └────────────────────────────────────────────────────────────────────────┘       │
│                                                                                  │
│  clients/metrics_client.py::prices_to_returns(prices)                            │
│  ┌────────────────────────────────────────────────────────────────────────┐       │
│  │  ├── len(prices) < 2 ──► return []                              [!]   │       │
│  │  └── For each pair: (prices[i] - prices[i-1]) / prices[i-1]    [!]   │       │
│  │      ├── prices[i-1] = 0 ──► append 0.0                        [!]   │       │
│  │      ├── prices[i-1] = NaN ──► append 0.0                      [!]   │       │
│  │      ├── result < -1.0 ──► cap to -1.0                         [!]   │       │
│  │      └── result > 10.0 ──► cap to 10.0                         [!]   │       │
│  └────────────────────────────────────────────────────────────────────────┘       │
│                                                                                  │
└──────────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────────┐
│              TRADING MODULE: CODE PATH / TEST COVERAGE MAP                       │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  trading/services/trading.py::execute_trading_signal(params)                     │
│  ┌────────────────────────────────────────────────────────────────────────┐       │
│  │  ├── _validate_common_params(params)                            [~]   │       │
│  │  │   ├── forecast_price <= 0 ──► InvalidParametersError         [!]   │       │
│  │  │   ├── current_price <= 0 ──► InvalidParametersError          [!]   │       │
│  │  │   ├── current_position < 0 ──► InvalidParametersError        [!]   │       │
│  │  │   ├── available_cash < 0 ──► InvalidParametersError          [!]   │       │
│  │  │   └── initial_capital <= 0 ──► InvalidParametersError        [!]   │       │
│  │  │                                                                    │       │
│  │  ├── generate_trading_signal(params)                                  │       │
│  │  │   ├── THRESHOLD ──► calculate_threshold_signal(params)       [~]   │       │
│  │  │   │   ├── threshold_type = "absolute"                        [~]   │       │
│  │  │   │   │   ├── diff > threshold ──► BUY                      [~]   │       │
│  │  │   │   │   ├── diff < -threshold ──► SELL                    [~]   │       │
│  │  │   │   │   └── else ──► HOLD                                 [~]   │       │
│  │  │   │   ├── threshold_type = "percentage"                      [!]   │       │
│  │  │   │   ├── threshold_type = "std_dev"                         [!]   │       │
│  │  │   │   │   └── EDGE: no history ──► fallback to absolute      [!]   │       │
│  │  │   │   └── threshold_type = "atr"                             [!]   │       │
│  │  │   │       └── EDGE: no OHLC data ──► fallback to absolute    [!]   │       │
│  │  │   │                                                                │       │
│  │  │   ├── RETURN ──► calculate_return_signal(params)             [~]   │       │
│  │  │   │   ├── position_sizing = "fixed"                          [!]   │       │
│  │  │   │   ├── position_sizing = "proportional"                   [!]   │       │
│  │  │   │   └── position_sizing = "normalized"                     [!]   │       │
│  │  │   │       └── EDGE: insufficient history ──► fallback fixed  [!]   │       │
│  │  │   │                                                                │       │
│  │  │   ├── QUANTILE ──► calculate_quantile_signal(params)         [!]   │       │
│  │  │   │   ├── Calculate percentile from recent history           [!]   │       │
│  │  │   │   ├── Match to quantile_signals ranges                   [!]   │       │
│  │  │   │   └── EDGE: insufficient history ──► InvalidParams       [!]   │       │
│  │  │   │                                                                │       │
│  │  │   └── Unknown strategy ──► InvalidStrategyError              [!]   │       │
│  │  │                                                                    │       │
│  │  ├── signal.action == "buy"                                           │       │
│  │  │   ├── max_affordable = cash / price                          [~]   │       │
│  │  │   ├── shares = min(signal.size, max_affordable)              [~]   │       │
│  │  │   └── EDGE: cash = 0 ──► hold (can't buy)                   [!]   │       │
│  │  │                                                                    │       │
│  │  ├── signal.action == "sell"                                          │       │
│  │  │   ├── shares = min(signal.size, current_position)            [~]   │       │
│  │  │   └── EDGE: position = 0 ──► hold (nothing to sell)         [!]   │       │
│  │  │                                                                    │       │
│  │  └── signal.action == "hold"                                    [~]   │       │
│  │                                                                       │       │
│  │  TESTED: ~8/25 paths (basic threshold buy/sell/hold)                  │       │
│  └────────────────────────────────────────────────────────────────────────┘       │
│                                                                                  │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### Test Priority Matrix

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                        TEST PRIORITY MATRIX                                      │
│  (Risk = Likelihood of bug × Impact of bug)                                      │
├───────────────────────────┬───────────┬──────────┬──────────┬───────────────────┤
│ Code Path                 │ Likelihood│ Impact   │ Priority │ Est. Tests Needed │
├───────────────────────────┼───────────┼──────────┼──────────┼───────────────────┤
│ adapters.py conversions   │ HIGH      │ HIGH     │ P0       │ 20-25 tests       │
│ (KeyError/IndexError)     │ (fragile) │ (crash)  │          │                   │
├───────────────────────────┼───────────┼──────────┼──────────┼───────────────────┤
│ backtest.py run_backtest  │ HIGH      │ HIGH     │ P0       │ 15-20 tests       │
│ (5-phase workflow)        │ (complex) │ (silent) │          │                   │
├───────────────────────────┼───────────┼──────────┼──────────┼───────────────────┤
│ metrics.py quantstats     │ MEDIUM    │ HIGH     │ P0       │ 15-20 tests       │
│ (edge case crashes)       │ (qs bugs) │ (500s)   │          │                   │
├───────────────────────────┼───────────┼──────────┼──────────┼───────────────────┤
│ MetricsClient circuit brk │ MEDIUM    │ MEDIUM   │ P1       │ 10-12 tests       │
│ (retry + fallback logic)  │           │          │          │                   │
├───────────────────────────┼───────────┼──────────┼──────────┼───────────────────┤
│ TradingClient error paths │ MEDIUM    │ LOW      │ P1       │ 8-10 tests        │
│ (degrades to HOLD)        │           │ (safe)   │          │                   │
├───────────────────────────┼───────────┼──────────┼──────────┼───────────────────┤
│ Trading strategies edges  │ LOW       │ MEDIUM   │ P1       │ 15-20 tests       │
│ (std_dev/ATR/quantile)    │           │          │          │                   │
├───────────────────────────┼───────────┼──────────┼──────────┼───────────────────┤
│ service.py predict routing│ LOW       │ HIGH     │ P1       │ 8-10 tests        │
│ (model family dispatch)   │           │          │          │                   │
├───────────────────────────┼───────────┼──────────┼──────────┼───────────────────┤
│ DataClient error paths    │ LOW       │ LOW      │ P2       │ 5-8 tests         │
│ (returns empty on error)  │           │ (safe)   │          │                   │
├───────────────────────────┼───────────┼──────────┼──────────┼───────────────────┤
│ schema.py validation      │ LOW       │ LOW      │ P2       │ 8-10 tests        │
│ (Pydantic handles most)   │           │          │          │                   │
├───────────────────────────┼───────────┼──────────┼──────────┼───────────────────┤
│ router.py path traversal  │ LOW       │ CRITICAL │ P0       │ 3-5 tests         │
│ (security vulnerability)  │           │ (RCE)    │          │                   │
├───────────────────────────┴───────────┴──────────┴──────────┴───────────────────┤
│                                                                                  │
│  TOTAL ESTIMATED TESTS NEEDED: ~110-140                                          │
│  EXISTING TESTS: ~25-30 (trading strategies only)                                │
│  GAP: ~80-110 new unit tests                                                     │
│                                                                                  │
└──────────────────────────────────────────────────────────────────────────────────┘
```

## Current State

### Existing Test Coverage

| Module | Test Files | Approximate Coverage | Gap |
|--------|-----------|---------------------|-----|
| `trading/` | `trading/tests/` (~600 lines) | Good for strategies | Missing edge cases |
| `orchestration/` | `tests/orchestration/` | Partial | adapters.py, backtest.py undertested |
| `metrics/` | `tests/metrics/` | Partial | Edge cases missing |
| `data/` (Go) | `data/main_test.go` (1,234 lines) | Good | Minor gaps |
| `forecast/` | Minimal | Low | Core routing untested |

### Specific Untested or Under-Tested Areas

1. **`orchestration/adapters.py`** (13,733 bytes)
   - 7+ model family detection functions
   - Schema conversion functions (unified -> model-specific -> unified)
   - Error cases when model name doesn't match any family
   - Malformed input handling

2. **`orchestration/service.py`** (11,297 bytes)
   - `InferenceService.predict()` routing logic
   - Timeout handling
   - Error propagation from model backends
   - Fallback behavior

3. **`orchestration/backtest.py`** (12,675 bytes)
   - BacktestOrchestrator full workflow
   - Date range calculations
   - Portfolio state tracking
   - Look-ahead bias prevention

4. **`orchestration/router.py`** (11,137 bytes)
   - Route resolution logic
   - Unknown model handling
   - Health check aggregation

5. **`orchestration/clients/`**
   - DataClient error handling
   - MetricsClient retry logic
   - TradingClient request formatting

6. **`metrics/core/metrics.py`**
   - Edge cases: empty returns array, single element, all-zero returns
   - NaN/Inf handling in Sharpe ratio calculation
   - Negative-only returns (max drawdown = 100%)
   - Very large return values

7. **`trading/services/trading.py`** (1,171+ lines)
   - Threshold strategy with all 4 threshold types (absolute, percentage, std_dev, ATR)
   - Return strategy with all position sizing modes
   - Quantile strategy with insufficient history
   - InsufficientCapitalError triggering
   - StrategyStoppedError triggering
   - Zero-position and zero-cash edge cases

## Expected Behavior

### Test Structure

```
tests/
  unit/
    orchestration/
      test_adapters.py          # Model family detection, schema conversion
      test_service.py           # InferenceService predict routing
      test_backtest.py          # Backtest orchestration logic
      test_router.py            # Route resolution
      test_schema.py            # Pydantic model validation
      clients/
        test_data_client.py     # DataClient with mocked HTTP
        test_metrics_client.py  # MetricsClient with mocked HTTP
        test_trading_client.py  # TradingClient with mocked HTTP
    metrics/
      test_metrics_core.py      # All metric calculations edge cases
      test_metrics_endpoints.py # FastAPI endpoint validation
    trading/
      test_threshold_strategy.py  # All threshold types
      test_return_strategy.py     # All position sizing modes
      test_quantile_strategy.py   # Quantile edge cases
      test_trading_errors.py      # Custom exception behavior
    conftest.py                 # Shared fixtures
```

### Test Categories Per Module

#### orchestration/adapters.py Tests
```python
class TestDetectModelFamily:
    def test_chronos_family_detection(self): ...
    def test_timesfm_family_detection(self): ...
    def test_moirai_family_detection(self): ...
    def test_granite_family_detection(self): ...
    def test_moment_family_detection(self): ...
    def test_lagllama_family_detection(self): ...
    def test_yinglong_family_detection(self): ...
    def test_unknown_model_raises_error(self): ...
    def test_empty_model_name(self): ...
    def test_case_sensitivity(self): ...

class TestSchemaConversion:
    def test_unified_to_chronos_format(self): ...
    def test_unified_to_timesfm_format(self): ...
    def test_chronos_response_to_unified(self): ...
    def test_timesfm_response_to_unified(self): ...
    def test_missing_required_fields(self): ...
    def test_extra_fields_ignored(self): ...
```

#### metrics/core/metrics.py Tests
```python
class TestSharpeRatio:
    def test_positive_returns(self): ...
    def test_negative_returns(self): ...
    def test_zero_volatility(self): ...
    def test_single_return(self): ...
    def test_empty_returns(self): ...
    def test_custom_risk_free_rate(self): ...

class TestMaxDrawdown:
    def test_monotonic_increase(self): ...      # drawdown = 0
    def test_monotonic_decrease(self): ...      # drawdown = total loss
    def test_recovery_after_drawdown(self): ...
    def test_single_value(self): ...
    def test_empty_values(self): ...

class TestWinRate:
    def test_all_positive(self): ...            # win_rate = 1.0
    def test_all_negative(self): ...            # win_rate = 0.0
    def test_mixed_returns(self): ...
    def test_zero_returns_excluded(self): ...
    def test_empty_returns(self): ...
```

#### trading/services/trading.py Tests
```python
class TestThresholdStrategy:
    def test_absolute_threshold_buy(self): ...
    def test_absolute_threshold_sell(self): ...
    def test_absolute_threshold_hold(self): ...
    def test_percentage_threshold(self): ...
    def test_std_dev_threshold(self): ...
    def test_atr_threshold(self): ...
    def test_insufficient_history_for_std_dev(self): ...

class TestReturnStrategy:
    def test_fixed_position_sizing(self): ...
    def test_proportional_position_sizing(self): ...
    def test_normalized_position_sizing(self): ...
    def test_zero_available_cash(self): ...

class TestQuantileStrategy:
    def test_above_upper_quantile_sell(self): ...
    def test_below_lower_quantile_buy(self): ...
    def test_within_quantile_hold(self): ...
    def test_insufficient_history(self): ...

class TestErrorConditions:
    def test_insufficient_capital_raises(self): ...
    def test_strategy_stopped_raises(self): ...
    def test_invalid_strategy_type_raises(self): ...
    def test_negative_position_rejected(self): ...
```

## Acceptance Criteria

- [ ] Unit tests exist for all public functions in `orchestration/adapters.py`
- [ ] Unit tests exist for `InferenceService.predict()` with mocked backends
- [ ] Unit tests exist for `BacktestOrchestrator` core logic
- [ ] Unit tests exist for router resolution logic
- [ ] Unit tests exist for all three client classes with mocked HTTP
- [ ] Unit tests exist for all metric calculations including edge cases
- [ ] Unit tests exist for all three trading strategy types
- [ ] Unit tests exist for custom exception classes
- [ ] All tests pass with `pytest -x` (fail-fast)
- [ ] Line coverage >= 80% for files changed in aleutian_merge changesets
- [ ] No test depends on external services (all HTTP calls mocked)
- [ ] Tests complete in < 30 seconds

---

## Dependencies

- GAP-15 (Error Handling) may change function signatures - coordinate to avoid rework
- Recommend implementing GAP-15 first, then writing tests against the improved error handling

## Files to Create/Modify

| File | Action |
|------|--------|
| `tests/unit/orchestration/test_adapters.py` | Create |
| `tests/unit/orchestration/test_service.py` | Create |
| `tests/unit/orchestration/test_backtest.py` | Create |
| `tests/unit/orchestration/test_router.py` | Create |
| `tests/unit/orchestration/test_schema.py` | Create |
| `tests/unit/orchestration/clients/test_data_client.py` | Create |
| `tests/unit/orchestration/clients/test_metrics_client.py` | Create |
| `tests/unit/orchestration/clients/test_trading_client.py` | Create |
| `tests/unit/metrics/test_metrics_core.py` | Create |
| `tests/unit/metrics/test_metrics_endpoints.py` | Create |
| `tests/unit/trading/test_threshold_strategy.py` | Create |
| `tests/unit/trading/test_return_strategy.py` | Create |
| `tests/unit/trading/test_quantile_strategy.py` | Create |
| `tests/unit/trading/test_trading_errors.py` | Create |
| `tests/unit/conftest.py` | Create (shared fixtures) |
| `pyproject.toml` or `pytest.ini` | Update test paths |

## Rollback Plan

Tests are additive-only. No rollback needed. If tests fail, fix the underlying code, not the tests.
