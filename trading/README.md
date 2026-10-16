# Trading Service

Stateless trading-strategy execution. Receives a forecast scalar plus current
portfolio state, returns a trade decision. Persists nothing — the orchestrator
owns state.

## Endpoints

All `/trading/*` endpoints require `Authorization: Bearer ${TRADING_API_KEY}`
(token must be ≥32 chars in production; warning logged in dev).

| Method | Path | Description |
|--------|------|-------------|
| GET    | `/health`                  | FastAPI liveness |
| GET    | `/`                        | Service banner |
| GET    | `/trading/strategies`      | List supported strategy types and required params (rate-limited 30/min) |
| GET    | `/trading/status`          | Health + strategies catalogue (rate-limited 30/min) |
| POST   | `/trading/execute`         | Execute a strategy (rate-limited 10/min) |

### Execute request/response

```json
POST /trading/execute
{
  "strategy_type": "threshold",        // threshold | return | quantile
  "forecast_price": 472.50,            // SCALAR — caller picks the trading_horizon index
  "current_price": 470.00,
  "current_position": 0.0,
  "available_cash": 100000.0,
  "initial_capital": 100000.0,
  // ...strategy-specific params (see Strategies below)
}
```

```json
200 OK
{
  "action": "BUY",                     // BUY | SELL | HOLD
  "size": 10.0,                        // units
  "value": 4700.00,                    // notional
  "reason": "forecast > current + threshold",
  "available_cash": 95300.00,
  "position_after": 10.0,
  "stopped": false                     // true if max-loss circuit broke
}
```

The service is horizon-unaware: `forecast_price` is a single number. It is
the orchestrator's job to compute `forecast_price = forecast_vector[trading_horizon - 1]`.

## Strategies

### `threshold` — diff-driven
Compare `forecast_price` vs `current_price + threshold`. Buy if forecast
higher, sell if lower.

| Param | Values | Notes |
|-------|--------|-------|
| `threshold_type` | `absolute` \| `percentage` \| `std_dev` \| `atr` | `std_dev` needs `history`; `atr` needs OHLC. Both fall back to `absolute` on missing inputs. |
| `threshold_value` | float | Magnitude in units of the chosen type |
| `execution_size` | float | Trade size in units |
| `history` | list[float] | Required for `std_dev` |
| `ohlc` | dict | Required for `atr`: `{open, high, low, close}` arrays |

### `return` — return-driven
Compute expected return `(forecast_price - current_price) / current_price`.
Buy/sell if magnitude exceeds `threshold_value`.

| Param | Values | Notes |
|-------|--------|-------|
| `position_sizing` | `fixed` \| `proportional` \| `normalized` | `normalized` needs `window_history` |
| `threshold_value` | float | Return magnitude in decimal (e.g. 0.015 = 1.5%) |
| `base_size` | float | Used by `fixed` |
| `window_history` | list[float] | Required for `normalized` (recommended length ≤ 1000 for performance) |

### `quantile` — percentile-driven
Rank `forecast_price` against a historical window; map percentile to a
`quantile_signals` table (BUY/SELL/HOLD per range).

| Param | Values | Notes |
|-------|--------|-------|
| `ohlc` | dict | All four arrays required (same length) |
| `quantile_signals` | list[dict] | `[{range:[lo,hi], signal:"BUY"\|"SELL"\|"HOLD", multiplier:float}]`; ranges must not overlap |

All three strategies are long-only. No short-selling.

## Configuration

| Env | Default | Notes |
|-----|---------|-------|
| `TRADING_API_KEY` | required | Bearer token (≥32 chars in production) |
| `TRADING_API_HOST` / `TRADING_API_PORT` | `0.0.0.0` / `9000` | uvicorn bind |
| `LOG_LEVEL` | `INFO` | |
| `ENVIRONMENT` | `development` | `production` enforces token length |

Rate limits (slowapi, in-memory, IP-keyed):
- `/trading/execute`: 10/min
- `/trading/strategies`, `/trading/status`: 30/min
- Other endpoints: 60/min

## Architecture invariants

- **Stateless.** No database, no in-memory portfolio. Caller passes all state
  in the request, receives all state in the response.
- **Single global singleton:** the slowapi rate limiter (in `app.state.limiter`).
  Restart wipes counters; multi-replica is not supported.
- **Request-ID middleware** generates `X-Request-ID` if absent and stamps
  every log line.
- **Exception handlers** map `TradingException` and generic `Exception` to
  structured JSON via `shared.errors`.

## Run locally

```bash
docker compose up -d trading
# or venv:
uv pip install -e ".[trading]"
uvicorn trading.main:app --host 0.0.0.0 --port 9000
```

## Tests

```bash
uv run pytest trading/tests
```

Integration tests use FastAPI's `TestClient`; no external services required.
