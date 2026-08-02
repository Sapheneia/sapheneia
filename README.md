# Sapheneia

Agentic time-series forecasting and trading-strategy backtesting platform.

A Claude Code agent (via the `run-simulation` skill) drives a stateless
service mesh of forecasting models, trading strategies, metrics computation,
and price data — coordinated by a Python orchestrator that owns all run
state in TimescaleDB.

```
agent (Claude Code, skill: run-simulation)
   │  MCP (HTTP/SSE on :12703 — primary; stdio fallback)
   ▼
sapheneia-mcp                                                   ┐
   │  HTTP                                                      │
   ▼                                                            │
orchestrator-service (:12704)  ── owns ALL run-state writes ────┘
   ├─► data       (:12701)  Python+yfinance, prices cache only
   ├─► forecast   (:12700)  Python (TimesFM 2.0 + Chronos T5), stateless inference
   ├─► trading    (:12132)  Python (threshold/return/quantile), stateless
   ├─► metrics    (:12702)  Python (quantstats wrappers), stateless
   └─► timescaledb (:5432 on loopback, Docker named volume `timescaledb_data`)
```

## Quick start

```bash
cp .env.template .env             # edit API_SECRET_KEY, TRADING_API_KEY, etc.
./setup.sh up                     # docker compose up -d + alembic migrate + skill symlinks
```

After ~90s every healthcheck should be green:

```bash
./setup.sh status
```

Run a single backtest end-to-end without the agent (developer escape hatch):

```bash
uv run sapheneia simulate --strategy simulations/templates/spy_chronos_tiny.example.yaml
```

Run a matrix through the agent: open Claude Code in this repo and say
"run `simulations/templates/combinations.example.yaml`". The
`run-simulation` skill validates, expands the matrix, dispatches runs in
parallel through the MCP, polls for completion, and writes a comparison
report under `.local/experiments/{experiment_id}/report.md`.

## Services

| Service | Port | README | Owns |
|---------|------|--------|------|
| forecast (gateway + per-model containers) | 12700 + 12710-12721 | [`forecast/README.md`](forecast/README.md) | Stateless model inference |
| trading | 12132 | [`trading/README.md`](trading/README.md) | Stateless strategy execution |
| metrics | 12702 | [`metrics/README.md`](metrics/README.md) | Stateless metrics computation |
| data | 12701 | [`data/__init__.py`](data/__init__.py) | TimescaleDB price cache + yfinance fallback |
| orchestrator | 12704 | [`orchestrator/__init__.py`](orchestrator/__init__.py) | All run-state writes (runs, forecasts, trades, equity, metrics) |
| sapheneia-mcp | 12703 | [`sapheneia_mcp/__init__.py`](sapheneia_mcp/__init__.py) | MCP surface for the agent |
| timescaledb | 5432 | [`migrations/`](migrations/) | Persistence (Postgres + TimescaleDB extension) |

## Adding a new model

See "How to add a new model" in [`forecast/README.md`](forecast/README.md).
The short version: append a row to `forecast/models/registry.py`, copy a
docker-compose service block, and (if it's a new family) add a
`forecast/models/{family}/services/model.py`. The agent picks it up
automatically once it's in the combinations YAML.

## Development

```bash
uv sync --all-extras              # install everything
make test                         # full pytest (incl. integration via testcontainers)
make test-unit                    # fast inner loop, no docker required
make fmt                          # black + ruff --fix
```

Coverage gate (in `pyproject.toml`): ≥ 35% across the in-scope modules.

## Tests

| Path | What |
|------|------|
| `tests/`                | Cross-cutting (paths, error registration, skill schema, migrations) |
| `data/tests/`           | Data service: unit (mocked yfinance) + integration (testcontainers Postgres) |
| `orchestrator/tests/`   | Orchestrator: schema, inner loop with mocked clients, endpoints |
| `sapheneia_mcp/tests/`  | MCP tools: combinations validation/expansion/rendering, mocked HTTP |
| `sapheneia/cli/tests/`  | `sapheneia simulate` CLI |
| `trading/tests/`        | Trading strategies: `unit/` + `integration/` |
| `tests/metrics/`        | Metrics computation + auth |
| `tests/shared/`         | Model registry/family, DSN + config validators, time utils |

Integration tests are marked `@pytest.mark.integration` and require Docker
(testcontainers spins up a real TimescaleDB). They are skipped automatically
when testcontainers isn't installed, and run in CI as a separate job with a
real TimescaleDB service container — the unit job runs `-m "not integration"`,
so repository SQL is only exercised by that second job.

## Repository layout

```
forecast/              FastAPI: model containers + gateway
trading/               FastAPI: strategy execution
metrics/               FastAPI: returns → metrics
data/                  FastAPI: yfinance cache against TimescaleDB
orchestrator/          FastAPI: sole writer of run-state
sapheneia_mcp/         MCP server (HTTP/SSE + stdio)
sapheneia/cli/         `sapheneia simulate` developer CLI
shared/                Cross-service contracts, model registry, HTTP client,
                       auth/config validators, errors, DB pool factory
migrations/            Alembic schema versions
skills/                Claude Code skills (run-simulation)
simulations/templates/ Strategy YAML template + combinations example
tests/                 Cross-cutting tests
docker-compose.yml     All services on the internal `sapheneia-net`
setup.sh               Single-command up/down/reset/test
Makefile               Convenience targets
```

## Design background

- [`CLAUDE.md`](CLAUDE.md) — agent routing, gates, and the architecture
  invariants (§3–§9) this repository is held to.

> The longer-form engineering notes live outside the repository under
> `.config/agentic-engineering/` (gitignored, local to each developer's
> machine). `CLAUDE.md` is the authoritative in-repo statement of the rules.
