# Metrics Service

Stateless financial performance metrics. Computes Sharpe, Sortino, CAGR,
Calmar, max drawdown, win rate, and total return from a returns series.
Thin wrapper over `quantstats` with input validation and interpretation.

## Endpoint

Single consolidated endpoint. Bearer auth required only if `METRICS_API_KEY`
is set (empty disables, which is the default for intra-cluster use).

| Method | Path | Description |
|--------|------|-------------|
| GET    | `/health`              | FastAPI liveness |
| GET    | `/`                    | Service banner |
| POST   | `/metrics/v1/compute`  | Compute metrics from a returns series |

### Request

```json
POST /metrics/v1/compute
{
  "returns": [0.01, -0.02, 0.015, 0.008, -0.005],
  "metric": "performance",                    // see below
  "risk_free_rate": 0.0,                      // float or list[float]; default 0
  "periods_per_year": 252                     // 252=daily, 52=weekly, 12=monthly
}
```

`metric` selects which metric(s) to return:

| Value | Returns |
|-------|---------|
| `performance` (default) | All five metrics + `interpretation` + `metadata` |
| `all`                   | All five metrics, no interpretation |
| `sharpe`                | `{sharpe_ratio}` |
| `max_drawdown`          | `{max_drawdown}` |
| `cagr`                  | `{cagr}` |
| `calmar`                | `{calmar_ratio}` |
| `win_rate`              | `{win_rate}` |

### Response (`metric=performance`)

```json
{
  "sharpe_ratio": 1.45,
  "max_drawdown": -0.07,
  "cagr": 0.12,
  "calmar_ratio": 1.71,
  "win_rate": 0.60,
  "interpretation": {
    "sharpe_ratio": "good",
    "calmar_ratio": "good",
    "win_rate": "high",
    "overall_assessment": "Good performance with acceptable risk"
  },
  "metadata": {
    "risk_free_rate": 0.0,
    "periods_per_year": 252,
    "total_periods": 5,
    "profitable_periods": 3,
    "losing_periods": 2
  }
}
```

## Inputs

- `returns` **must** be a returns series, not prices. Each entry is the
  period return (e.g., `0.01` = +1%).
- Minimum 2 values. NaN and Inf are dropped.
- `risk_free_rate` accepts a scalar or a list matching `len(returns)`.

## Thresholds (used in `interpretation`)

| Metric | Tiers |
|--------|-------|
| Sharpe | > 2 excellent · > 1 good · > 0.5 acceptable · ≤ 0 poor |
| Calmar | > 3 exceptional · > 1 good · > 0.5 decent · ≤ 0.5 poor |
| Win rate | > 0.60 high · > 0.50 moderate · < 0.40 low |

Max drawdown closer to 0 is better (no fixed tiers).

## Configuration

| Env | Default | Notes |
|-----|---------|-------|
| `METRICS_HOST` / `METRICS_PORT` | `0.0.0.0` / `8000` | uvicorn bind (host port mapped to `METRICS_PORT` in `.env`, default `12702`) |
| `METRICS_LOG_LEVEL` | `INFO` | |
| `METRICS_API_KEY` | empty | Bearer token; empty disables auth |

## Architecture invariants

- **Stateless.** No DB, no files, no global state beyond the `Settings` singleton.
- **Pure compute.** Each request is independent; no incremental or streaming API.
- **Single process is fine.** Multiple workers are safe.
- Exception handlers via `shared.errors` map to structured JSON.

## Run locally

```bash
docker compose up -d metrics
# or venv:
uv pip install -e ".[metrics]"
uvicorn metrics.main:app --host 0.0.0.0 --port 8000
```

## Tests

```bash
uv run pytest tests/metrics
```

Tests mock nothing (quantstats is fast enough); they exercise validation,
all metric families, interpretation tiers, and edge cases (zero returns,
NaN/Inf, single-return vectors).
