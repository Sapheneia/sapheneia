# Standalone Sapheneia: drop the AleutianFOSS dependency

**Branch:** `sapheneia-data-integration`
**Goal:** run a forecast end-to-end (`pull → bring-up → predict`) using only sapheneia containers. No `aleutian-go-orchestrator`, no `aleutian-data-fetcher`, no Aleutian-owned infra.

## Why

For the HF-dashboard direction, sapheneia needs to stand alone. We already added Yahoo ingest into `data/main.go` during the Aleutian merge (`03ba86d`, 2026-01-26) — sapheneia is functionally self-sufficient at the service level. What's missing is *deployment* self-sufficiency.

## Current coupling

- `docker-compose.yml` declares `aleutian-network` as `external: true` (name `aleutian-shared`) — bring-up fails unless Aleutian created it first.
- No `influxdb` service in sapheneia compose. References `user-influxdb:8086` which is provided by Aleutian's compose.
- `start-sapheneia-stack.sh` lives in `AleutianFOSS-TimeSeries/scripts/` and orchestrates both stacks.
- `.env` has `ORCHESTRATOR_URL` / `ALEUTIAN_*` references that no caller in sapheneia actually needs once standalone.

## Required changes (in this repo)

1. **Add `influxdb` service** to `docker-compose.yml`. Keep `container_name: user-influxdb` so existing `INFLUXDB_URL` references keep working. Mirror Aleutian's defaults (`aleutian-finance` org, `financial-data` bucket, token from env). Add named volume `influxdb_data`.
2. **Switch network** from `external: true` to a self-managed `sapheneia-network`. Compose creates it on `up`. Update all `aleutian-network` service references. (If we want dual-stack to keep working, add an alias or document the rename.)
3. **Add a `scripts/start-stack.sh`** in this repo — bring up `forecast`, `forecast-chronos-t5-tiny`, `data`, `trading`, `influxdb` (CPU profile). Hit health endpoints. No Aleutian.
4. **Trim `.env.template`** — drop `ORCHESTRATOR_URL`, `ALEUTIAN_*`, `SAPHENEIA_TRADING_*` cross-stack refs that no longer apply. Add `INFLUXDB_TOKEN` (default `aleutian-dev-token-2026` for dev parity, or rotate to a sapheneia-specific value).
5. **Update RUNBOOK** quick-start to point at the new script and drop the "create aleutian-shared network" step.

## Out of scope (separate tickets)

- HF Spaces packaging (Gradio app, single-image Dockerfile, `app.py`).
- Retention policy + Grafana datasource provisioning.
- Removing the Aleutian-FOSS data-fetcher Go service — that lives in the other repo and stays on its own roadmap.

## Acceptance criteria

- Fresh checkout of this branch + `cp .env.template .env` + `./scripts/start-stack.sh` brings up a green stack with **no Aleutian containers running and no Aleutian repo present**.
- `POST http://localhost:12701/v1/data/fetch` writes SPY history into the sapheneia-managed Influx.
- Chronos init + `POST http://localhost:12700/orchestration/v1/predict` (with inline context values) returns a forecast.
- `podman network ls` shows `sapheneia-network`, no dependency on `aleutian-shared`.

## Risks / open questions

- Container-name collision (`user-influxdb`) if both stacks run on the same host. Acceptable for now; rename later if it bites.
- `start-sapheneia-stack.sh` in the AleutianFOSS repo will continue to work since it references the external network — but if we drop external, that script needs updating in the other repo. Decide: dual-stack still supported, or full split?

---

## Plan review (post-investigation)

Walked the proposed plan against the actual code in `data/main.go`, `orchestration/router.py`, `orchestration/schema.py`, and `docker-compose.yml`. Findings:

### What holds up

- `data/main.go` exposes everything the standalone path needs: `POST /v1/data/fetch` (Yahoo → Influx), `POST /v1/data/query` (Influx read), `POST /v1/data/write_results`. No Aleutian imports.
- `orchestration/router.py` `POST /orchestration/v1/predict` is reachable directly — its docstring still says "primary contract between Aleutian (Go orchestrator) and Sapheneia," but that's just a stale comment; the endpoint itself is HTTP, no upstream coupling.
- Compose `forecast` (gateway) service has zero Aleutian-specific env. CHRONOS_SERVICE_URL points to a sibling container by hostname.
- Adding `influxdb` to compose with `container_name: user-influxdb` means **zero source changes** to satisfy the existing `INFLUXDB_URL=http://user-influxdb:8086` references.

### Gaps in v1 of this plan, and corrections

1. **`/orchestration/v1/predict` does not auto-fetch context.** It requires `context.values: List[float]` inline. The Aleutian orchestrator was the one fetching from Influx and flattening close values into `context.values`. **Correction:** the end-to-end smoke test is **two HTTP calls**, not one — `/v1/data/query` first, flatten close values out of `DataPoint[]`, then `/v1/data/predict`. Acceptance criteria below now reflect this.

2. **`DataQueryResponse.Data` is `[]DataPoint` (typed OHLCV), not `[]float64`.** Caller has to extract `close` values themselves. Documented in the data flow below. If we want a single-call ergonomic endpoint later, that's a follow-up ticket — *not* part of this work.

3. **Model init is required before predict.** Hit `POST :12710/forecast/v1/chronos/initialization` once per container lifetime. A 409 from predict otherwise. Adding to the smoke-test step list.

4. **CPU profile gate.** All `forecast-chronos-*` services declare `profiles: ["cpu"]`. The standalone start script must pass `--profile cpu` (or `--profile gpu` on a CUDA host) or no model containers come up.

5. **Build prerequisites.** First build pulls torch + chronos-forecasting + transformers; needs ~8 GB RAM in the podman VM (4 GB OOMs on `ugorji/go/codec` build) and ~15 GB free disk. Documenting in the runbook update.

6. **Healthcheck semantics are misleading.** `forecast` and `forecast-chronos-t5-tiny` report `status:healthy` while `models.timesfm20.status:uninitialized`. Healthy = service up; doesn't mean any model is loaded. Smoke test cannot rely on healthcheck alone.

### Updated acceptance criteria

- Fresh checkout + `cp .env.template .env` + `./scripts/start-stack.sh --profile cpu` brings up: `influxdb` (user-influxdb), `data`, `forecast`, `forecast-chronos-t5-tiny`, `trading`. **No Aleutian containers running, no Aleutian repo on disk.**
- `podman network ls` shows `sapheneia-network`; `aleutian-shared` is absent.
- `POST :12701/v1/data/fetch {"names":["SPY"], "start_date":"2024-01-01", "end_date":"2024-12-31"}` → `{success, "586 points written"}`.
- `POST :12710/forecast/v1/chronos/initialization` (Bearer token) → `{model_status:"ready"}`.
- `POST :12701/v1/data/query {"ticker":"SPY","days":90,"end_date":"2024-12-31"}` → `{data:[{date, close, ...}, ...], count:90}`.
- Caller flattens to `values=[d.close for d in data]`, then `POST :12700/orchestration/v1/predict` with that `context.values` → `{forecast.values:[10 floats], quantiles:[9 levels], metadata}`.
- Run a `git grep -i aleutian` in the sapheneia working tree — only doc/comment hits, nothing in active service code paths or compose.

---

## Architecture (standalone)

```
                     ┌────────────────────────────────────────────────────────┐
                     │              sapheneia-network (podman)                │
                     │                                                        │
   caller            │   ┌────────────────────┐    ┌─────────────────────┐    │
   (curl /           │   │  sapheneia-forecast│    │ forecast-chronos-   │    │
   Gradio /          │   │  gateway, Python   │    │ t5-tiny, Python     │    │
   notebook)         │   │  ctr :8000         │    │ ctr :8000           │    │
        │            │   │  host :12700       │    │ host :12710         │    │
        │            │   │                    │───►│ /forecast/v1/       │    │
        │ /predict   │   │ /orchestration/    │    │   chronos/init      │    │
        ├────────────┼──►│   v1/predict       │    │ /forecast/v1/       │    │
        │            │   │ /v1/forecast (legacy)   │   chronos/inference │    │
        │            │   └────────────────────┘    └──────────┬──────────┘    │
        │            │                                        │ HF cache     │
        │            │                                        ▼              │
        │            │                              ┌─────────────────────┐  │
        │ /fetch     │   ┌────────────────────┐     │ models_cache (vol)  │  │
        │ /query     │   │  sapheneia-data    │     │ host: ~/models_cache│  │
        ├────────────┼──►│  Go, ctr :8000     │     └─────────────────────┘  │
        │            │   │  host :12701       │                              │
        │            │   │                    │     ┌─────────────────────┐  │
        │            │   │ /v1/data/fetch     │────►│   user-influxdb     │  │
        │            │   │ /v1/data/query     │◄────│   InfluxDB 2.7      │  │
        │            │   │ /v1/data/          │     │   ctr :8086         │  │
        │            │   │   write_results    │     │   host :12130       │  │
        │            │   └─────────┬──────────┘     │   org=aleutian-     │  │
        │            │             │                │     finance         │  │
        │            │             │                │   bucket=           │  │
        │ /trading/* │   ┌─────────▼──────────┐     │     financial-data  │  │
        ├────────────┼──►│ sapheneia-trading  │     │   vol=influxdb_data │  │
        │            │   │ Python, ctr :9000  │     └─────────────────────┘  │
        │            │   │ host :12132        │                              │
        │            │   └────────────────────┘                              │
        │            └────────────────────────────────────────────────────────┘
        │
        │ (egress, only sapheneia-data initiates)
        ▼
  ┌─────────────────────────────────────┐
  │  query1.finance.yahoo.com           │
  │  /v8/finance/chart/{ticker}?period1 │
  │  =...&period2=...&interval=1d       │
  └─────────────────────────────────────┘
```

## Data flow — ticker to forecast, step by step

```
STEP 1 — Ingest history into Influx (one time per ticker / date range)
─────────────────────────────────────────────────────────────────────
  caller          sapheneia-data           Yahoo                  user-influxdb
  ──────          ──────────────           ─────                  ─────────────
    │ POST /v1/data/fetch                   │                          │
    │ {"names":["SPY"],"start":"2024-01-01",│                          │
    │  "end":"2024-12-31"}                  │                          │
    ├─────────────►│                        │                          │
    │              │ GET /v8/finance/chart/SPY?period1=...&period2=... │
    │              ├───────────────────────►│                          │
    │              │ OHLCV bars (chart JSON)│                          │
    │              │◄───────────────────────┤                          │
    │              │ for each bar: NewPoint("market_data", ticker=SPY, │
    │              │   open/high/low/close/volume, ts) → WritePoint    │
    │              ├──────────────────────────────────────────────────►│
    │              │                                          OK       │
    │              │◄──────────────────────────────────────────────────┤
    │ {success,"details":{"SPY":"586 points written"}}                  │
    │◄─────────────┤                                                    │

STEP 2 — Pull context window for the forecast
──────────────────────────────────────────────
  caller          sapheneia-data                                  user-influxdb
  ──────          ──────────────                                  ─────────────
    │ POST /v1/data/query                                              │
    │ {"ticker":"SPY","days":90,"end_date":"2024-12-31"}               │
    ├─────────────►│                                                   │
    │              │ Flux: from(bucket:"financial-data")               │
    │              │   |> range(start:-91d, stop:"2024-12-31T...")     │
    │              │   |> filter(_measurement=="market_data",          │
    │              │             _field=="close", ticker=="SPY")       │
    │              │   |> tail(n:90)                                   │
    │              ├──────────────────────────────────────────────────►│
    │              │ 90 (date, close) rows                             │
    │              │◄──────────────────────────────────────────────────┤
    │ {ticker:"SPY",                                                   │
    │  data:[{date:"2024-08-18",open:..,close:548.50,...},...90 items],│
    │  count:90}                                                       │
    │◄─────────────┤                                                   │

  caller flattens: context_values = [pt["close"] for pt in resp["data"]]
                   start_date     = resp["data"][0]["date"]
                   end_date       = resp["data"][-1]["date"]

STEP 3 — Initialize the model (one time per container lifetime)
───────────────────────────────────────────────────────────────
  caller          forecast-chronos-t5-tiny       HuggingFace       models_cache
  ──────          ────────────────────────       ───────────       ────────────
    │ POST /forecast/v1/chronos/initialization     │                    │
    │ Authorization: Bearer <API_SECRET_KEY>       │                    │
    │ {"model_variant":"amazon/chronos-t5-tiny",   │                    │
    │  "device":"cpu"}                             │                    │
    ├─────────────►│                               │                    │
    │              │ ChronosPipeline.from_pretrained(amazon/chronos-t5-tiny)
    │              │   if not in /models_cache:    │                    │
    │              ├──────────────────────────────►│                    │
    │              │   .safetensors weights        │                    │
    │              │◄──────────────────────────────┤                    │
    │              │   write to /models_cache (mounted from host)       │
    │              ├───────────────────────────────────────────────────►│
    │              │   load to torch on cpu, status=ready               │
    │ {message:"Model initialized successfully",                        │
    │  model_status:"ready",                                            │
    │  model_info:{model_variant:"amazon/chronos-t5-tiny",device:"cpu"}}│
    │◄─────────────┤                                                    │

STEP 4 — Run the forecast
──────────────────────────
  caller          sapheneia-forecast (gateway)         forecast-chronos-t5-tiny
  ──────          ──────────────────────────           ────────────────────────
    │ POST /orchestration/v1/predict                              │
    │ {request_id, timestamp, ticker:"SPY",                       │
    │  model:"amazon/chronos-t5-tiny",                            │
    │  context:{values:<from step 2>, period:"1d",                │
    │    source:"influxdb", start_date, end_date, field:"close"}, │
    │  horizon:{length:10, period:"1d"},                          │
    │  params:{num_samples:20}}                                   │
    ├─────────────►│                                              │
    │              │ router.py: model_family = "chronos"          │
    │              │ service.py: _run_chronos_inference(req)      │
    │              │ POST /forecast/v1/chronos/inference          │
    │              │ Authorization: Bearer <API_SECRET_KEY>       │
    │              │ {context:[...], horizon:10, num_samples:20}  │
    │              ├─────────────────────────────────────────────►│
    │              │      ChronosPipeline.predict(                │
    │              │        torch.tensor(context),                │
    │              │        prediction_length=10,                 │
    │              │        num_samples=20)                       │
    │              │      → samples shape [20, 10]                │
    │              │      median, quantiles(0.1..0.9) per step    │
    │              │ {forecast:{values:[10 floats]},              │
    │              │  quantiles:[{quantile, values}, ...9],       │
    │              │  metadata:{inference_time_ms, model_version}}│
    │              │◄─────────────────────────────────────────────┤
    │ {request_id, response_id, ticker, model,                    │
    │  forecast:{values, period, start_date, end_date},           │
    │  context_summary:{length:90, source:"influxdb", ...},       │
    │  quantiles:[...9], metadata:{...}}                          │
    │◄─────────────┤                                              │

STEP 5 (optional) — Persist backtest results
─────────────────────────────────────────────
  caller          sapheneia-data                                  user-influxdb
  ──────          ──────────────                                  ─────────────
    │ POST /v1/data/write_results                                       │
    │ {strategy_id, run_id,                                             │
    │  points:[{date, forecast, actual, signal,                         │
    │           position, cash, portfolio_value}, ...],                 │
    │  metrics:{sharpe_ratio, max_drawdown, total_return, win_rate}}    │
    ├─────────────►│                                                    │
    │              │ NewPoint("backtest_results", strategy_id, ...)     │
    │              ├───────────────────────────────────────────────────►│
    │ {success}                                                         │
    │◄─────────────┤                                                    │
```

End-to-end smoke test = STEP 1 + 3 + 2 + 4 (skip 5). Steps 1 and 3 are idempotent and only needed first run; steady state is just 2 + 4.
