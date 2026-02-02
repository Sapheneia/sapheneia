# Aleutian Integration Tickets

Local development tickets for completing the Aleutian/Sapheneia integration.

**Goal:** Complete end-to-end flow: `data → forecast → trading → metrics`

**Status:** ✅ ALL 10 TICKETS COMPLETED (2025-02)

---

## Executive Summary

All 10 GAP tickets have been implemented. Below is a brief summary of each for team discussion.

### GAP-01: Metrics Service Integration ✅
Implemented `MetricsClient` in `orchestration/clients/metrics_client.py` with async HTTP communication to the Go metrics service on port 12702. The client supports computing Sharpe ratio, max drawdown, and total return from equity curves, with graceful degradation returning empty metrics on failure rather than crashing the backtest.

### GAP-02: Trading Feedback Loop ✅
Created `TradingClient` and `PortfolioManager` in `orchestration/clients/trading_client.py` to integrate with the trading microservice on port 12132. The client executes threshold, return, and quantile strategies via HTTP, while `PortfolioManager` tracks portfolio state with checkpointing, atomic updates, and audit trails for full backtest continuity.

### GAP-03: Python Orchestration Entry Point ✅
Built a Click-based CLI at `sapheneia/cli/__init__.py` with commands for `evaluate`, `forecast`, `backtest`, and `config`. Added entry point in `pyproject.toml` enabling `sapheneia` as a standalone command. Integrated with `run_all_backtests.sh` via `--sapheneia` flag to run Python CLI instead of Go aleutian CLI.

### GAP-04: Data Write-Back Endpoint ✅
Extended `DataClient` in `orchestration/clients/data_client.py` to support writing backtest results back to the Go data service. The client handles both read (historical prices) and write (predictions, metrics) operations with proper error handling and request ID propagation for distributed tracing.

### GAP-05: Python Orchestration Tests ✅
Added 155+ tests across `orchestration/tests/` covering service clients, adapters, backtest configuration, and integration scenarios. Tests include timeout behavior (8 tests), date parsing (18 tests), request ID propagation (7 tests), and mock service responses. All tests passing with pytest.

### GAP-06: Backtest Mode Go Test ✅
Verified temporal isolation in Go data service using `end_date` parameter. The stop bound ensures InfluxDB queries only return data up to the evaluation date, preventing future data leakage during backtests. Go tests confirm date boundaries are correctly applied.

### GAP-07: Directory Structure Documentation ✅
Updated `README.md` with comprehensive project structure showing all service directories, their ports, and responsibilities. Documentation includes service architecture diagram, port map, and integration patterns for onboarding new team members.

### GAP-08: Configurable Timeout ✅
Implemented 3-level timeout configuration in `InferenceService`: constructor parameter (highest priority), `INFERENCE_TIMEOUT` environment variable, and 300-second default. Added `--timeout` flag to CLI commands. This allows tuning for different model sizes (tiny models need 30s, large models need 600s+).

### GAP-09: Request ID Propagation ✅
Added `_build_headers()` method to all service clients (`DataClient`, `MetricsClient`, `TradingClient`) that includes `X-Request-ID` header when provided. This enables distributed tracing across the microservice mesh, allowing correlation of logs from forecast → trading → metrics for debugging.

### GAP-10: Silent Date Parsing Fix ✅
Created `DateParseError` exception and `parse_date()` function in `orchestration/adapters.py` that explicitly fails with field name context. Replaces silent failures where invalid dates defaulted to current time. Supports YYYY-MM-DD, YYYYMMDD, and ISO 8601 formats.

---

## Before vs After Comparison

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           BEFORE IMPLEMENTATION                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│    ┌──────────┐         ┌──────────┐                                        │
│    │  Go CLI  │────────►│ Forecast │                                        │
│    │ aleutian │         │ Service  │                                        │
│    └──────────┘         └──────────┘                                        │
│         │                                                                    │
│         ▼                                                                    │
│    ┌──────────┐                                                              │
│    │   File   │  ← Results written to CSV only                              │
│    │  Output  │  ← No trading integration                                    │
│    └──────────┘  ← No metrics computation                                    │
│                  ← No request tracing                                        │
│                  ← Hardcoded 5-minute timeout                                │
│                  ← Silent date parsing failures                              │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                           AFTER IMPLEMENTATION                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│    ┌──────────┐     ┌──────────┐                                            │
│    │  Go CLI  │     │Python CLI│  ← Dual CLI support                        │
│    │ aleutian │     │sapheneia │  ← --sapheneia flag in scripts             │
│    └────┬─────┘     └────┬─────┘                                            │
│         │                │                                                   │
│         └───────┬────────┘                                                   │
│                 │                                                            │
│                 ▼                                                            │
│    ┌────────────────────────────────────────────────────────────────────┐   │
│    │                    ORCHESTRATION LAYER                              │   │
│    │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │   │
│    │  │ DataClient  │  │MetricsClient│  │TradingClient│                 │   │
│    │  │  :12701     │  │  :12702     │  │  :12132     │                 │   │
│    │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                 │   │
│    │         │                │                │                         │   │
│    │         │    X-Request-ID propagation     │                         │   │
│    │         └────────────────┼────────────────┘                         │   │
│    │                          │                                          │   │
│    │  ┌───────────────────────▼─────────────────────────────────────┐   │   │
│    │  │              PortfolioManager                                │   │   │
│    │  │  • Checkpointing every N iterations                          │   │   │
│    │  │  • Atomic state updates                                      │   │   │
│    │  │  • Equity curve tracking                                     │   │   │
│    │  └─────────────────────────────────────────────────────────────┘   │   │
│    └────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│    IMPROVEMENTS:                                                             │
│    ✓ Full trading feedback loop                                             │
│    ✓ Metrics computation (Sharpe, drawdown, return)                         │
│    ✓ Distributed tracing via X-Request-ID                                   │
│    ✓ Configurable timeout (env/flag/constructor)                            │
│    ✓ Explicit date parsing with error messages                              │
│    ✓ 155+ tests for confidence                                              │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## End-to-End Flow (Target Architecture)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                     SAPHENEIA END-TO-END ORCHESTRATION FLOW                      │
│                                                                                  │
│  ENTRY ──► BACKTEST LOOP ──────────────────────────────────────────► OUTPUT     │
│    │                                                                      │      │
│    │       ┌──────────────────────────────────────────────────────────┐   │      │
│    │       │  for each evaluation_date:                               │   │      │
│    │       │                                                          │   │      │
│    │       │    ┌─────────┐    ┌──────────┐    ┌─────────┐           │   │      │
│    │       │    │  DATA   │───►│ FORECAST │───►│ TRADING │           │   │      │
│    │       │    │ :12701  │    │  :12700  │    │ :12132  │           │   │      │
│    │       │    └─────────┘    └──────────┘    └────┬────┘           │   │      │
│    │       │         ▲                              │                 │   │      │
│    │       │         │         InfluxDB             ▼                 │   │      │
│    │       │         │         :12130      ┌──────────────┐          │   │      │
│    │       │         │                     │ Update State │          │   │      │
│    │       │         └─────────────────────┴──────────────┘          │   │      │
│    │       │                                                          │   │      │
│    │       └──────────────────────────────────────────────────────────┘   │      │
│    │                                    │                                  │      │
│    │                                    ▼                                  │      │
│    │                           ┌───────────────┐                           │      │
│    │                           │   METRICS     │                           │      │
│    │                           │    :12702     │──────────────────────────►│      │
│    │                           └───────────────┘                           │      │
│    │                                                                       │      │
│    └───────────────────────────────────────────────────────────────────────┘      │
│                                                                                   │
└───────────────────────────────────────────────────────────────────────────────────┘
```

---

## Architecture Review Summary

All tickets have been reviewed for:

| Criteria | Description |
|----------|-------------|
| **Reliability** | Error handling, retries, circuit breakers, graceful degradation |
| **Continuity** | State management, checkpointing, recovery, idempotency |
| **Integrity** | Data validation, audit trails, consistency checks |
| **Optimization** | Batching, caching, connection pooling, async operations |
| **Separation** | Service boundaries, interfaces, horizontal scaling |

---

## Ticket Overview

| Ticket | Title | Priority | Effort | Status |
|--------|-------|----------|--------|--------|
| GAP-01 | [Metrics Service Integration](./GAP-01-metrics-service-integration.md) | HIGH | 3-4 days | ✅ DONE |
| GAP-02 | [Trading Feedback Loop](./GAP-02-trading-feedback-loop.md) | HIGH | 2-3 days | ✅ DONE |
| GAP-03 | [Python Orchestration Entry Point](./GAP-03-python-orchestration-entrypoint.md) | MEDIUM | 1-2 days | ✅ DONE |
| GAP-04 | [Data Write-Back Endpoint](./GAP-04-data-writeback-endpoint.md) | MEDIUM | 1-2 days | ✅ DONE |
| GAP-05 | [Python Orchestration Tests](./GAP-05-python-orchestration-tests.md) | CRITICAL | 2-3 days | ✅ DONE |
| GAP-06 | [Backtest Mode Go Test](./GAP-06-backtest-mode-go-test.md) | MEDIUM | 0.5 days | ✅ DONE |
| GAP-07 | [Directory Structure Docs](./GAP-07-directory-structure-standardization.md) | LOW | 1 day | ✅ DONE |
| GAP-08 | [Configurable Timeout](./GAP-08-configurable-timeout.md) | LOW | 0.5 days | ✅ DONE |
| GAP-09 | [Request ID Propagation](./GAP-09-request-id-propagation.md) | LOW | 1 day | ✅ DONE |
| GAP-10 | [Silent Date Parsing](./GAP-10-silent-date-parsing.md) | LOW | 0.5 days | ✅ DONE |

**Total Estimated Effort:** 12-17 days | **Actual:** Completed

---

## Dependency Graph

```
                      ┌─────────────────────────────┐
                      │      FOUNDATION LAYER       │
                      │                             │
                      │  GAP-05 (Python Tests)      │
                      │  GAP-06 (Go Backtest Test)  │
                      └──────────────┬──────────────┘
                                     │
                      ┌──────────────▼──────────────┐
                      │       CORE INTEGRATION      │
                      │                             │
          ┌──────────►│  GAP-02 (Trading Loop)     │◄──────────┐
          │           │           +                 │           │
          │           │  GAP-01 (Metrics)          │           │
          │           └──────────────┬──────────────┘           │
          │                          │                          │
          │           ┌──────────────▼──────────────┐           │
          │           │        PERSISTENCE          │           │
          │           │                             │           │
          │           │  GAP-04 (Data Write-Back)  │           │
          │           └──────────────┬──────────────┘           │
          │                          │                          │
          │           ┌──────────────▼──────────────┐           │
          │           │       USER INTERFACE        │           │
          │           │                             │           │
          │           │  GAP-03 (Python CLI)       │           │
          │           └─────────────────────────────┘           │
          │                                                     │
          │           ┌─────────────────────────────┐           │
          │           │         POLISH              │           │
          └───────────│  GAP-08, GAP-09, GAP-10    │───────────┘
                      │  GAP-07 (Documentation)     │
                      └─────────────────────────────┘
```

---

## Recommended Execution Order

### Phase 1: Foundation (Week 1)
Build confidence in existing code before making changes.

| Order | Ticket | Why |
|-------|--------|-----|
| 1 | **GAP-05** | Python tests enable safe refactoring |
| 2 | **GAP-06** | Verifies critical temporal isolation |

### Phase 2: Core Integration (Week 2)
Implement the main integration loop.

| Order | Ticket | Why |
|-------|--------|-----|
| 3 | **GAP-02** | Trading feedback loop is the backbone |
| 4 | **GAP-01** | Metrics computation completes the flow |
| 5 | **GAP-04** | Persist results to InfluxDB (optional) |

### Phase 3: User Experience (Week 3)
Make it easy to use.

| Order | Ticket | Why |
|-------|--------|-----|
| 6 | **GAP-03** | Python CLI for researchers |
| 7 | **GAP-08** | Configurable timeout |

### Phase 4: Polish (When Time Permits)

| Order | Ticket | Why |
|-------|--------|-----|
| 8 | **GAP-10** | Fix date parsing issues |
| 9 | **GAP-09** | Request ID propagation |
| 10 | **GAP-07** | Documentation cleanup |

---

## Key Implementation Files Created

Each ticket now includes detailed implementation code:

| Ticket | New Files |
|--------|-----------|
| GAP-01 | `orchestration/clients/metrics_client.py` |
| GAP-02 | `orchestration/clients/trading_client.py`, `orchestration/backtest.py` |
| GAP-03 | `sapheneia/cli/__init__.py`, `sapheneia/cli/commands/*.py` |
| GAP-04 | Go endpoint + `orchestration/clients/data_client.py` |
| GAP-05 | `orchestration/tests/conftest.py`, `test_*.py` |
| GAP-06 | Go test functions |

---

## Service Port Map

| Service | Port | Container |
|---------|------|-----------|
| Forecast Gateway | 12700 | sapheneia-forecast |
| Data Service (Go) | 12701 | sapheneia-data |
| Metrics Service | 12702 | sapheneia-metrics |
| Trading Service | 12132 | sapheneia-trading |
| InfluxDB | 12130 | user-influxdb |
| Chronos T5 Tiny | 12710 | forecast-chronos-t5-tiny |
| Chronos T5 Base | 12713 | forecast-chronos-t5-base |

---

## Key Architecture Decisions

### Client Pattern
All service clients follow the same pattern:
- Circuit breaker for reliability
- Retry with exponential backoff
- Graceful degradation on failure
- Async by default

### State Management
- Portfolio state managed by `PortfolioManager` class
- Checkpointing every N iterations
- Atomic updates with validation

### Data Flow
- All data queries go through Go data service (temporal bounding)
- Python services receive pre-validated data
- Results written to both file system and InfluxDB

---

## Notes

- Tickets are for **local development only** - not intended to be merged
- PR #42 is approved; these are follow-up improvements
- Focus on **GAP-01** and **GAP-02** first to achieve end-to-end metrics goal
- Each ticket includes full implementation code ready to use

---

## Detailed Architecture Diagrams

### Complete Backtest Data Flow

```
┌───────────────────────────────────────────────────────────────────────────────────┐
│                         BACKTEST LOOP STATE MACHINE                                │
│                                                                                    │
│   START                                                                            │
│     │                                                                              │
│     ▼                                                                              │
│  ┌──────────────────┐                                                              │
│  │ Initialize       │                                                              │
│  │ PortfolioManager │ cash=$100,000  position=0  equity=[100000]                  │
│  └────────┬─────────┘                                                              │
│           │                                                                        │
│           ▼                                                                        │
│  ┌──────────────────┐     ┌─────────────────────────────────────┐                 │
│  │ For each date in │────►│          SINGLE ITERATION           │                 │
│  │ evaluation_dates │     │                                     │                 │
│  └──────────────────┘     │  ┌─────────────────────────────┐   │                 │
│           │               │  │ 1. DataClient.get_prices()  │   │                 │
│           │               │  │    end_date = current_date   │   │                 │
│           │               │  │    (temporal isolation)      │   │                 │
│           │               │  └─────────────┬───────────────┘   │                 │
│           │               │                │                    │                 │
│           │               │                ▼                    │                 │
│           │               │  ┌─────────────────────────────┐   │                 │
│           │               │  │ 2. InferenceService.forecast│   │                 │
│           │               │  │    timeout = configurable    │   │                 │
│           │               │  │    X-Request-ID = {uuid}     │   │                 │
│           │               │  └─────────────┬───────────────┘   │                 │
│           │               │                │                    │                 │
│           │               │                ▼                    │                 │
│           │               │  ┌─────────────────────────────┐   │                 │
│           │               │  │ 3. TradingClient.execute()  │   │                 │
│           │               │  │    strategy = threshold      │   │                 │
│           │               │  │    returns TradeResult       │   │                 │
│           │               │  └─────────────┬───────────────┘   │                 │
│           │               │                │                    │                 │
│           │               │                ▼                    │                 │
│           │               │  ┌─────────────────────────────┐   │                 │
│           │               │  │ 4. PortfolioManager.apply() │   │                 │
│           │               │  │    Update cash/position     │   │                 │
│           │               │  │    Append to equity curve   │   │                 │
│           │               │  │    Checkpoint if needed     │   │                 │
│           │               │  └─────────────────────────────┘   │                 │
│           │               │                                     │                 │
│           │               └─────────────────────────────────────┘                 │
│           │                                                                        │
│           │ (loop continues)                                                       │
│           │                                                                        │
│           ▼                                                                        │
│  ┌──────────────────┐                                                              │
│  │ All dates done   │                                                              │
│  └────────┬─────────┘                                                              │
│           │                                                                        │
│           ▼                                                                        │
│  ┌─────────────────────────────────────────────────────────────────────────────┐  │
│  │                           METRICS COMPUTATION                                │  │
│  │                                                                              │  │
│  │   MetricsClient.compute_metrics(equity_curve)                               │  │
│  │                                                                              │  │
│  │   Returns:                                                                   │  │
│  │     • sharpe_ratio: (mean_return - risk_free) / std_dev                     │  │
│  │     • max_drawdown: max(peak - trough) / peak                               │  │
│  │     • total_return: (final - initial) / initial                             │  │
│  │     • win_rate: winning_trades / total_trades                               │  │
│  │                                                                              │  │
│  └─────────────────────────────────────────────────────────────────────────────┘  │
│           │                                                                        │
│           ▼                                                                        │
│        OUTPUT: BacktestResult with trades[], equity_curve[], metrics{}            │
│                                                                                    │
└───────────────────────────────────────────────────────────────────────────────────┘
```

### Service Interaction Diagram (HTTP)

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                          HTTP SERVICE MESH                                           │
│                                                                                      │
│   ┌────────────────────────────────────────────────────────────────────────────┐    │
│   │                        ORCHESTRATION LAYER (Python)                         │    │
│   │                                                                             │    │
│   │   InferenceService          DataClient         TradingClient               │    │
│   │        │                        │                    │                      │    │
│   └────────┼────────────────────────┼────────────────────┼──────────────────────┘    │
│            │                        │                    │                           │
│            │ POST /forecast         │ GET /data/prices   │ POST /trading/execute    │
│            │ Headers:               │ Headers:           │ Headers:                 │
│            │  Content-Type: json    │  X-Request-ID      │  X-Request-ID           │
│            │  X-Request-ID          │                    │  Authorization          │
│            │  timeout: 30-600s      │ Params:            │                         │
│            │                        │  symbol            │ Body:                   │
│            │                        │  start_date        │  strategy_type          │
│            │                        │  end_date          │  forecast_price         │
│            │                        │                    │  current_price          │
│            │                        │                    │  portfolio_state        │
│            ▼                        ▼                    ▼                          │
│   ┌────────────────┐       ┌────────────────┐   ┌────────────────┐                  │
│   │   FORECAST     │       │     DATA       │   │    TRADING     │                  │
│   │   GATEWAY      │       │    SERVICE     │   │    SERVICE     │                  │
│   │    :12700      │       │    :12701      │   │    :12132      │                  │
│   │                │       │                │   │                │                  │
│   │  Routes to:    │       │  Queries:      │   │  Strategies:   │                  │
│   │  - chronos-t5  │       │  - InfluxDB    │   │  - threshold   │                  │
│   │  - other models│       │    :12130      │   │  - return      │                  │
│   └────────┬───────┘       └───────┬────────┘   │  - quantile    │                  │
│            │                       │            └────────────────┘                  │
│            │                       │                                                │
│            ▼                       ▼                                                │
│   ┌────────────────┐       ┌────────────────┐                                       │
│   │  MODEL PODS    │       │   INFLUXDB     │                                       │
│   │  :12710-12713  │       │    :12130      │                                       │
│   │                │       │                │                                       │
│   │  chronos-t5-   │       │  Buckets:      │                                       │
│   │  tiny/base     │       │  - prices      │                                       │
│   └────────────────┘       │  - predictions │                                       │
│                            │  - metrics     │                                       │
│                            └────────────────┘                                       │
│                                                                                      │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

### CLI Integration with Scripts

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                        CLI / SCRIPT INTEGRATION                                      │
│                                                                                      │
│   USER ENTRY POINTS                                                                  │
│   ─────────────────                                                                  │
│                                                                                      │
│   ┌─────────────────────┐          ┌─────────────────────┐                          │
│   │  model-manager.sh   │          │ run_all_backtests.sh│                          │
│   │                     │          │                     │                          │
│   │  Commands:          │          │  Flags:             │                          │
│   │  - start            │          │  --quick            │                          │
│   │  - stop             │          │  --full             │                          │
│   │  - logs             │          │  --sapheneia ←─────────── NEW: Use Python CLI  │
│   │  - status           │          │  --python           │                          │
│   └──────────┬──────────┘          └──────────┬──────────┘                          │
│              │                                │                                      │
│              │                                ├─────────────────┐                    │
│              │                                │                 │                    │
│              ▼                                ▼                 ▼                    │
│   ┌─────────────────────┐          ┌─────────────────┐ ┌─────────────────┐          │
│   │  Docker Containers  │          │    Go CLI       │ │   Python CLI    │          │
│   │                     │          │   (aleutian)    │ │   (sapheneia)   │          │
│   │  - sapheneia-data   │          │                 │ │                 │          │
│   │  - sapheneia-trading│          │  aleutian       │ │  sapheneia      │          │
│   │  - sapheneia-metrics│          │    backtest     │ │    backtest     │          │
│   │  - sapheneia-forecast          │    --symbol     │ │    --symbol     │          │
│   │  - forecast-chronos-*          │    --start-date │ │    --start-date │          │
│   │  - user-influxdb    │          │    --end-date   │ │    --end-date   │          │
│   └─────────────────────┘          │    --model      │ │    --model      │          │
│                                    │                 │ │    --timeout ←──── NEW     │
│                                    └─────────────────┘ └─────────────────┘          │
│                                                                                      │
│   USAGE EXAMPLES:                                                                    │
│   ───────────────                                                                    │
│                                                                                      │
│   # Start all services                                                               │
│   ./scripts/model-manager.sh start                                                   │
│                                                                                      │
│   # Run backtest with Go CLI (default)                                              │
│   ./simulations/strategies/run_all_backtests.sh --quick                             │
│                                                                                      │
│   # Run backtest with Python CLI                                                     │
│   ./simulations/strategies/run_all_backtests.sh --quick --sapheneia                 │
│                                                                                      │
│   # Direct Python CLI usage                                                          │
│   sapheneia backtest --symbol SPY --model chronos-t5-tiny --timeout 60              │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### Timeout Configuration Priority

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    TIMEOUT CONFIGURATION HIERARCHY                           │
│                                                                              │
│   HIGHEST PRIORITY                                                           │
│        │                                                                     │
│        ▼                                                                     │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │  1. Constructor Parameter                                             │  │
│   │                                                                       │  │
│   │     service = InferenceService(timeout=60.0)                         │  │
│   │                                                                       │  │
│   │     Use when: Programmatic control needed per-service instance       │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│        │                                                                     │
│        ▼                                                                     │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │  2. Environment Variable                                              │  │
│   │                                                                       │  │
│   │     export INFERENCE_TIMEOUT=120.0                                   │  │
│   │     service = InferenceService()  # Uses 120s                        │  │
│   │                                                                       │  │
│   │     Use when: Container/deployment configuration                     │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│        │                                                                     │
│        ▼                                                                     │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │  3. CLI Flag                                                          │  │
│   │                                                                       │  │
│   │     sapheneia forecast --timeout 180                                 │  │
│   │                                                                       │  │
│   │     Use when: User override for specific run                         │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│        │                                                                     │
│        ▼                                                                     │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │  4. Default Value                                                     │  │
│   │                                                                       │  │
│   │     DEFAULT_TIMEOUT = 300.0  # 5 minutes                             │  │
│   │                                                                       │  │
│   │     Suitable for: Most chronos-t5-base inference workloads           │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│   LOWEST PRIORITY                                                            │
│                                                                              │
│   RECOMMENDED VALUES BY MODEL:                                               │
│   ─────────────────────────────                                              │
│   chronos-t5-tiny:   30-60 seconds                                          │
│   chronos-t5-base:   120-300 seconds                                        │
│   chronos-t5-large:  300-600 seconds                                        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Request ID Tracing Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     DISTRIBUTED TRACING WITH X-REQUEST-ID                    │
│                                                                              │
│   BACKTEST START                                                             │
│        │                                                                     │
│        │  Generate UUID: "abc123-def456"                                    │
│        │                                                                     │
│        ▼                                                                     │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │  DataClient.get_prices(request_id="abc123-def456")                  │   │
│   │                                                                      │   │
│   │  HTTP Request:                                                       │   │
│   │    GET /data/prices?symbol=SPY&start=2025-01-01&end=2025-01-15      │   │
│   │    Headers:                                                          │   │
│   │      X-Request-ID: abc123-def456                                    │   │
│   │                                                                      │   │
│   │  Logs:                                                               │   │
│   │    [DATA] request_id=abc123-def456 action=query_prices rows=252     │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│        │                                                                     │
│        ▼                                                                     │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │  InferenceService.forecast(request_id="abc123-def456")              │   │
│   │                                                                      │   │
│   │  HTTP Request:                                                       │   │
│   │    POST /forecast                                                    │   │
│   │    Headers:                                                          │   │
│   │      X-Request-ID: abc123-def456                                    │   │
│   │      Content-Type: application/json                                  │   │
│   │                                                                      │   │
│   │  Logs:                                                               │   │
│   │    [FORECAST] request_id=abc123-def456 model=chronos latency=2.3s   │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│        │                                                                     │
│        ▼                                                                     │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │  TradingClient.execute_signal(request_id="abc123-def456")           │   │
│   │                                                                      │   │
│   │  HTTP Request:                                                       │   │
│   │    POST /trading/execute                                             │   │
│   │    Headers:                                                          │   │
│   │      X-Request-ID: abc123-def456                                    │   │
│   │      Authorization: Bearer ***                                       │   │
│   │                                                                      │   │
│   │  Logs:                                                               │   │
│   │    [TRADING] request_id=abc123-def456 action=BUY size=10 value=$5k  │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│        │                                                                     │
│        ▼                                                                     │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │  MetricsClient.compute_metrics(request_id="abc123-def456")          │   │
│   │                                                                      │   │
│   │  Logs:                                                               │   │
│   │    [METRICS] request_id=abc123-def456 sharpe=1.2 drawdown=0.05      │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│   DEBUG QUERY:                                                               │
│   ─────────────                                                              │
│   grep "abc123-def456" /var/log/sapheneia/*.log                             │
│                                                                              │
│   Returns correlated logs across ALL services for this request              │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Test Coverage Summary

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         TEST COVERAGE BY TICKET                              │
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │  orchestration/tests/                                                │   │
│   │                                                                      │   │
│   │  test_service.py          │████████████████████│ 8 tests (timeout)  │   │
│   │  test_adapters.py         │████████████████████│ 18 tests (parsing) │   │
│   │  test_clients.py          │████████████████████│ 7 tests (req-id)   │   │
│   │  test_backtest.py         │████████████████████│ ~30 tests          │   │
│   │  test_integration.py      │████████████████████│ ~20 tests          │   │
│   │                                                                      │   │
│   │  TOTAL PYTHON: 155+ tests                                           │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│   KEY TEST SCENARIOS:                                                        │
│                                                                              │
│   GAP-05 (Tests):                                                            │
│     ✓ Service client mocking                                                │
│     ✓ Portfolio state management                                            │
│     ✓ Backtest loop execution                                               │
│     ✓ Error handling and graceful degradation                               │
│                                                                              │
│   GAP-08 (Timeout):                                                          │
│     ✓ test_custom_timeout_via_constructor                                   │
│     ✓ test_timeout_from_env_var                                             │
│     ✓ test_invalid_env_timeout_uses_default                                 │
│     ✓ test_explicit_timeout_overrides_env                                   │
│                                                                              │
│   GAP-09 (Request ID):                                                       │
│     ✓ test_data_client_propagates_request_id                                │
│     ✓ test_metrics_client_propagates_request_id                             │
│     ✓ test_trading_client_propagates_request_id                             │
│     ✓ test_no_request_id_when_none                                          │
│                                                                              │
│   GAP-10 (Date Parsing):                                                     │
│     ✓ test_parse_yyyy_mm_dd_format                                          │
│     ✓ test_parse_yyyymmdd_format                                            │
│     ✓ test_parse_iso_format                                                 │
│     ✓ test_empty_date_raises_error                                          │
│     ✓ test_invalid_date_raises_error                                        │
│     ✓ test_error_includes_field_name                                        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Integration Checklist

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SCRIPT INTEGRATION VERIFICATION                           │
│                                                                              │
│   scripts/model-manager.sh                                                   │
│   ────────────────────────                                                   │
│   [✓] Updated usage docs to show both CLI options                           │
│   [✓] Supports starting all required containers                              │
│   [✓] Logs accessible via 'logs' command                                    │
│                                                                              │
│   simulations/strategies/run_all_backtests.sh                               │
│   ───────────────────────────────────────────                               │
│   [✓] Added --sapheneia / --python flag                                     │
│   [✓] Conditional CLI selection based on flag                               │
│   [✓] Backward compatible (default uses Go CLI)                             │
│   [✓] Works with --quick and --full modes                                   │
│                                                                              │
│   sapheneia CLI (pyproject.toml)                                            │
│   ──────────────────────────────                                            │
│   [✓] Entry point: sapheneia = "sapheneia.cli:main"                         │
│   [✓] Dependencies: click, httpx, pyyaml                                    │
│   [✓] Commands: evaluate, forecast, backtest, config                        │
│   [✓] Global --timeout option                                               │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Running Backtests - Team Guide

This section covers how to run backtests on the server.

### Quick Start

```bash
# SSH to server
ssh digits
cd /path/to/sapheneia

# Interactive mode - pick model and ticker
./scripts/run-backtest.sh

# Direct run
./scripts/run-backtest.sh -m chronos-t5-tiny -t SPY
```

---

### Available Scripts

| Script | Purpose | Location |
|--------|---------|----------|
| `run-backtest.sh` | **Interactive** single backtest runner | `scripts/` |
| `model-manager.sh` | Container lifecycle (start/stop/init) | `scripts/` |
| `test-models.sh` | Model testing suite | `scripts/` |
| `run_all_backtests.sh` | Batch run all strategies | `simulations/strategies/` |

---

### 1. Interactive Backtest Runner (`run-backtest.sh`)

The easiest way to run a single backtest. Lets you pick a model and ticker interactively.

```bash
# Interactive mode (recommended for first-time users)
./scripts/run-backtest.sh

# List available models and tickers
./scripts/run-backtest.sh --list

# Direct run with confirmation prompt
./scripts/run-backtest.sh -m chronos-t5-tiny -t SPY

# Direct run, skip confirmation
./scripts/run-backtest.sh -m chronos-t5-tiny -t SPY --yes
```

**Example Interactive Session:**
```
╔═══════════════════════════════════════════════════════════════╗
║            Sapheneia Interactive Backtest Runner              ║
╚═══════════════════════════════════════════════════════════════╝

Available Models:

   1) ● chronos-t5-tiny        Fastest, good for testing
   2) ● chronos-t5-mini        Fast, slightly better accuracy
   3) ○ chronos-t5-small       Balanced speed/accuracy
   4) ○ chronos-t5-base        Good accuracy, slower
   5) ○ chronos-t5-large       Best accuracy, slowest
   6) ● timesfm-2-0            Google TimesFM 2.0

  ● = running    ○ = not running

Select model [1-6]: 1
  ✓ Selected: chronos-t5-tiny

Available Tickers:

  BND      BTCUSDT  EEM      ETHUSD   FBND     GLD
  IUSB     IWM      QQQ      RSP      SLV      SPY
  TLT      USO      VTI      XLB      XLC      XLE
  ...

Enter ticker symbol: SPY
  ✓ Selected: SPY

═══════════════════════════════════════════════════════════════
                    BACKTEST CONFIGURATION
═══════════════════════════════════════════════════════════════

  Model:     chronos-t5-tiny
  HF ID:     amazon/chronos-t5-tiny
  Port:      12710
  Ticker:    SPY
  Strategy:  spy_chronos_t5_tiny.yaml

Strategy details:
    start_date: "20230101"
    end_date: "20240101"
    context_size: 252
    horizon_size: 20
    initial_capital: 100000.0

  Model status: RUNNING

═══════════════════════════════════════════════════════════════

Proceed with backtest? [Y/n]: y

Starting backtest...
```

---

### 2. Model Manager (`model-manager.sh`)

Manages forecast model containers.

```bash
# List all models and their status
./scripts/model-manager.sh list

# Start a specific model
./scripts/model-manager.sh start chronos-t5-tiny

# Start all supported models
./scripts/model-manager.sh start --all

# Initialize model (load weights into memory)
./scripts/model-manager.sh init chronos-t5-tiny

# Check status of running containers
./scripts/model-manager.sh status

# Stop a model
./scripts/model-manager.sh stop chronos-t5-tiny

# View logs
./scripts/model-manager.sh logs chronos-t5-tiny

# Build container image
./scripts/model-manager.sh build chronos-t5-tiny

# Pre-download HuggingFace weights
./scripts/model-manager.sh pull chronos-t5-tiny
```

**Typical Startup Sequence:**
```bash
# 1. Start the model container
./scripts/model-manager.sh start chronos-t5-tiny

# 2. Wait for container health check
./scripts/model-manager.sh status

# 3. Initialize the model (loads weights)
./scripts/model-manager.sh init chronos-t5-tiny

# 4. Verify model is ready
curl http://localhost:12710/health
```

---

### 3. Model Test Suite (`test-models.sh`)

Systematically tests forecast models at multiple levels.

```bash
# Quick test - inference only (fast)
./scripts/test-models.sh quick

# Full test - includes backtest + CSV export
./scripts/test-models.sh full

# Test specific model
./scripts/test-models.sh model chronos-t5-tiny

# Test with full backtest
./scripts/test-models.sh model chronos-t5-tiny --full

# Test entire model family
./scripts/test-models.sh family chronos

# Test with different ticker
./scripts/test-models.sh full --ticker QQQ

# List all models and status
./scripts/test-models.sh list

# Generate status report
./scripts/test-models.sh report
```

**Test Levels:**
| Level | Test | What it checks |
|-------|------|----------------|
| 1 | Container health | Is the service running? |
| 2 | Model init | Can it load weights? |
| 3 | Status ready | Is model ready for inference? |
| 4 | Inference | Can it generate forecasts? |
| 5 | Backtest (--full) | Can it run full backtest + CSV? |

**Output Files:**
```
test_results/
├── MODEL_STATUS.md              # Latest summary
├── model_test_report_*.md       # Timestamped reports
└── backtest_*.csv               # CSV exports (--full only)
```

---

### 4. Batch Backtest Runner (`run_all_backtests.sh`)

Runs multiple backtests from strategy YAML files.

```bash
# Run all strategies for all tickers
./simulations/strategies/run_all_backtests.sh

# Run only SPY strategies
./simulations/strategies/run_all_backtests.sh --ticker SPY

# Run only chronos-t5-tiny strategies
./simulations/strategies/run_all_backtests.sh --model chronos-t5-tiny

# Combine filters
./simulations/strategies/run_all_backtests.sh --ticker SPY --model chronos-t5-tiny

# Dry run (show what would run)
./simulations/strategies/run_all_backtests.sh --dry-run

# Skip data fetching (assumes data exists)
./simulations/strategies/run_all_backtests.sh --skip-fetch

# Use Python CLI instead of Go CLI
./simulations/strategies/run_all_backtests.sh --sapheneia
```

**Strategy Files Location:**
```
simulations/strategies/
├── SPY/
│   ├── spy_chronos_t5_tiny.yaml
│   ├── spy_chronos_t5_base.yaml
│   ├── spy_timesfm_2_0.yaml
│   └── ...
├── QQQ/
│   └── ...
├── BTCUSDT/
│   └── ...
└── results/
    └── 20250202_143022/
        ├── run_log.txt
        └── backtest_*.csv
```

---

### Server Testing Checklist

Before running backtests, verify the stack is healthy:

```bash
# 1. Check all containers are running
podman ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# 2. Health checks
curl -s http://localhost:12130/ping && echo "InfluxDB OK"
curl -s http://localhost:12701/health | jq .status  # Data service
curl -s http://localhost:12700/health | jq .status  # Forecast gateway
curl -s http://localhost:12710/health | jq .status  # Chronos model

# 3. Check model is initialized
curl -s http://localhost:12710/forecast/v1/chronos/status | jq .

# 4. Quick inference test
curl -X POST http://localhost:12710/forecast/v1/inference \
  -H "Content-Type: application/json" \
  -d '{"context": [100,101,102,103,104], "prediction_length": 3}' | jq .
```

---

### Troubleshooting

**Container won't start:**
```bash
# Check logs
podman logs forecast-chronos-t5-tiny

# Check if port is in use
ss -tlnp | grep 12710

# Restart
./scripts/model-manager.sh stop chronos-t5-tiny
./scripts/model-manager.sh start chronos-t5-tiny
```

**Model initialization fails:**
```bash
# Check GPU
nvidia-smi

# Check container has GPU access
podman exec forecast-chronos-t5-tiny nvidia-smi

# Try manual init
curl -X POST http://localhost:12710/forecast/v1/chronos/initialization \
  -H "Content-Type: application/json" \
  -d '{"model_variant": "amazon/chronos-t5-tiny"}'
```

**Backtest returns no data:**
```bash
# Check InfluxDB has data
curl -G 'http://localhost:12130/query' \
  --data-urlencode "db=sapheneia" \
  --data-urlencode "q=SELECT COUNT(*) FROM prices WHERE ticker='SPY'"

# Fetch data if missing
aleutian timeseries fetch SPY --days 500
```

**Model status shows "not ready":**
```bash
# Wait and retry (large models take time)
sleep 30
curl -s http://localhost:12710/forecast/v1/chronos/status | jq .

# Check for OOM in logs
podman logs forecast-chronos-t5-tiny | tail -50
```

---

### Model Reference

| Model | Port | Speed | Accuracy | GPU Memory |
|-------|------|-------|----------|------------|
| chronos-t5-tiny | 12710 | ⚡⚡⚡ | ★★☆ | ~2GB |
| chronos-t5-mini | 12711 | ⚡⚡⚡ | ★★☆ | ~2GB |
| chronos-t5-small | 12712 | ⚡⚡ | ★★★ | ~4GB |
| chronos-t5-base | 12713 | ⚡ | ★★★★ | ~8GB |
| chronos-t5-large | 12714 | 🐢 | ★★★★★ | ~16GB |
| timesfm-2-0 | 12721 | ⚡⚡ | ★★★★ | ~8GB |

**Recommended for testing:** `chronos-t5-tiny` (fastest, good enough for validation)

**Recommended for production:** `chronos-t5-base` or `timesfm-2-0`

---

### Available Tickers

```
ETFs:        SPY, QQQ, IWM, VTI, RSP
Sectors:     XLB, XLC, XLE, XLF, XLI, XLK, XLP, XLRE, XLU, XLV, XLY
Bonds:       TLT, BND, FBND, IUSB
Commodities: GLD, SLV, USO
Intl:        EEM
Crypto:      BTCUSDT, ETHUSD
```
