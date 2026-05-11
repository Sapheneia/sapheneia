# Quickstart: Sapheneia (standalone)

End-to-end forecast in ~5 minutes, no other repos required. Copy-paste each block in order.

## 0. Prereqs (one-time)

Pick one container runtime — Docker or Podman. Everything below works with both; just swap the command name. The guide writes `podman-compose`; if you're on Docker, use `docker compose` (note the space).

**macOS**

```bash
# Option A — Docker Desktop
# Install from https://www.docker.com/products/docker-desktop  (open it once so the daemon starts)

# Option B — Podman
brew install podman podman-compose
podman machine init   # first run only
podman machine start
```

**Linux**

Podman runs natively — no VM needed.

```bash
# Fedora / RHEL / CentOS Stream
sudo dnf install -y podman podman-compose

# Debian / Ubuntu 22.04+
sudo apt update && sudo apt install -y podman podman-compose

# Docker as an alternative (any distro)
# https://docs.docker.com/engine/install/  → install Docker Engine + Compose plugin
```

> **SELinux note (Fedora/RHEL)**: the compose file bind-mounts source dirs (e.g. `./forecast:/app/forecast`). If the containers can't read them, you'll need `:Z` suffixes on the mounts or `sudo setenforce 0` for testing. Run `getenforce` to check — if it says `Enforcing`, this applies to you.

**This repo**

```bash
git clone <sapheneia-url> ~/code/sapheneia
cd ~/code/sapheneia
```

## 1. Start the stack

```bash
cd ~/code/sapheneia
podman-compose --profile cpu up -d forecast forecast-chronos-t5-tiny trading data influxdb
# Docker users:
# docker compose --profile cpu up -d forecast forecast-chronos-t5-tiny trading data influxdb
```

> The `--profile cpu` is required — the `forecast*` services are profile-gated and the tool will silently skip them without it.

Wait ~30 seconds, then check:

```bash
podman ps --format "table {{.Names}}\t{{.Status}}"
# or: docker ps --format "table {{.Names}}\t{{.Status}}"
```

You should see all five `(healthy)`:

| Container | Port | Role |
| --- | --- | --- |
| `sapheneia-forecast` | 12700 | Forecast gateway (calls into models) |
| `forecast-chronos-t5-tiny` | 12710 | Chronos model container |
| `sapheneia-data` | 12701 | Data service (Yahoo/InfluxDB) |
| `sapheneia-trading` | 12132 | Trading strategies |
| `user-influxdb` | 12130 | TSDB |

## 2. Get some data

Set the API key once for this shell:

```bash
export API_KEY="default_trading_api_key_please_change"
```

**Option A — fetch live from Yahoo** (may rate-limit):

```bash
curl -X POST http://localhost:12701/v1/data/fetch \
  -H 'Content-Type: application/json' \
  -d '{"names":["SPY"],"start_date":"2026-01-01","interval":"1d"}'
```

**Option B — seed synthetic data** (always works):

```bash
python3 - <<'PY' > /tmp/seed.lp
import time, random, math
random.seed(42); now=int(time.time()); price=500.0
for i in range(86):
    ts=(now-(85-i)*86400)*1_000_000_000
    price+=math.sin(i/10)*5+random.uniform(-2,2)
    o=price+random.uniform(-1,1); c=price+random.uniform(-1,1)
    h=max(o,c)+abs(random.uniform(0,1.5)); l=min(o,c)-abs(random.uniform(0,1.5))
    print(f'stock_prices,ticker=SPY open={o:.4f},high={h:.4f},low={l:.4f},close={c:.4f},adj_close={c:.4f},volume={random.randint(50_000_000,120_000_000)}i {ts}')
PY
podman cp /tmp/seed.lp user-influxdb:/tmp/seed.lp
podman exec user-influxdb influx write \
  --bucket financial-data --org aleutian-finance \
  --token aleutian-dev-token-2026 --file /tmp/seed.lp
# Docker users: replace `podman` with `docker` in the two commands above.
```

Verify the data is queryable:

```bash
curl -X POST http://localhost:12701/v1/data/query \
  -H 'Content-Type: application/json' \
  -d '{"ticker":"SPY","days":120}' | python3 -m json.tool | head -20
```

## 3. Initialize the Chronos model

```bash
curl -X POST http://localhost:12700/forecast/v1/chronos/initialization \
  -H "Authorization: Bearer $API_KEY" -H 'Content-Type: application/json' \
  -d '{"model_variant":"amazon/chronos-t5-tiny","device":"cpu"}'
```

You should see `"model_status":"ready"`. First run may take a minute while the model downloads.

## 4. Run a forecast

Pull the closes you just seeded and forecast 7 days ahead:

```bash
python3 - <<'PY' > /tmp/infer.json
import json, urllib.request
req = urllib.request.Request('http://localhost:12701/v1/data/query',
    data=json.dumps({"ticker":"SPY","days":120}).encode(),
    headers={'Content-Type':'application/json'})
closes = [pt['close'] for pt in json.loads(urllib.request.urlopen(req).read())['data']]
print(json.dumps({"context": closes, "prediction_length": 7, "num_samples": 20}))
PY

curl -X POST http://localhost:12700/forecast/v1/chronos/inference \
  -H "Authorization: Bearer $API_KEY" -H 'Content-Type: application/json' \
  --data @/tmp/infer.json | python3 -m json.tool > /tmp/forecast.json
head -40 /tmp/forecast.json
```

You'll get back `prediction.median`, `prediction.mean`, `prediction.quantiles`, and `prediction.samples`. The full response is saved to `/tmp/forecast.json` for the next step.

## 5. Execute a trade from the forecast

The trading service uses a **different** API key than the forecast service (`TRADING_API_KEY`, baked into the container). Set it for this shell:

```bash
export TRADING_API_KEY="dev_trading_api_key_12345678901234567890"
```

Build a trade payload that compares the day-7 median forecast against the current close, then POST it to the trading service:

```bash
python3 - <<'PY' > /tmp/trade.json
import json, urllib.request
q = urllib.request.Request('http://localhost:12701/v1/data/query',
    data=json.dumps({"ticker":"SPY","days":120}).encode(),
    headers={'Content-Type':'application/json'})
current = json.loads(urllib.request.urlopen(q).read())['data'][-1]['close']
forecast_median = json.load(open('/tmp/forecast.json'))['prediction']['median'][-1]
print(json.dumps({
  "strategy_type":"threshold","forecast_price": forecast_median,"current_price": current,
  "current_position": 0.0,"available_cash": 100000.0,"initial_capital": 100000.0,
  "threshold_type":"absolute","threshold_value": 0.0,"execution_size": 100.0}))
PY

curl -X POST http://localhost:12132/trading/execute \
  -H "Authorization: Bearer $TRADING_API_KEY" -H 'Content-Type: application/json' \
  --data @/tmp/trade.json | python3 -m json.tool
```

You'll get back the strategy decision: `action` (`buy`/`sell`/`hold`), `size`, `value`, `reason`, plus post-trade `available_cash` and `position_after`. With the seeded data, expect a `buy` of 100 shares around $57k.

## Optional: API docs in a browser

http://localhost:12700/docs — interactive Swagger UI for the forecast service.
http://localhost:12701/docs — same for the data service.

## Stopping

```bash
cd ~/code/sapheneia
podman-compose --profile cpu down
# Docker: docker compose --profile cpu down
```

## When stuff breaks

| Symptom | Fix |
| --- | --- |
| `missing services [forecast,...]` from podman-compose | You forgot `--profile cpu`. |
| `401 Unauthorized` on `/forecast/v1/chronos/*` | Missing or wrong `Authorization: Bearer …` header. Use the key in Step 2. |
| Yahoo `429 Too Many Requests` | Use Option B (synthetic seed) in Step 2. |
| `/forecast/v1/chronos/inference` returns `409 Model not initialized` | Run Step 3 first. |
| Containers "Up X seconds (starting)" forever | Wait 60s on first run — chronos pulls a HuggingFace model. Needs internet egress from the container. |
| `/openapi.json` returns 500 | Restart the forecast container; if it persists, you're on an old commit — pull. |
| Linux: containers can't read mounted source files (`Permission denied`) | SELinux. Add `:Z` to volume mounts in `docker-compose.yml`, or `sudo setenforce 0` for testing. |
| Chronos init hangs / `ConnectionError` on HuggingFace | Container has no internet (corp proxy / air-gapped). Set `HTTPS_PROXY` in the `forecast-chronos-t5-tiny` service env, or pre-populate `HF_HOME`. |

## Reference: ports & creds

InfluxDB org: `aleutian-finance`, bucket: `financial-data`, token: `aleutian-dev-token-2026`
Forecast API key (`:12700`): `default_trading_api_key_please_change`
Trading API key (`:12132`): `dev_trading_api_key_12345678901234567890`

The forecast and trading services have **independent** API keys. Use `Authorization: Bearer <key>` (or `Authorization: Api-Key <key>`) on `/forecast/v1/*` and `/trading/*` endpoints respectively. The data service (`:12701`) does not require auth.
