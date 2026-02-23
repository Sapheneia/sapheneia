# Sapheneia Service Contracts

API contract reference for all service-to-service communication within the Sapheneia platform. This document defines the authoritative interface specifications for each internal service.

---

## Port Assignments

| Service         | Port(s)           |
|-----------------|-------------------|
| Orchestration   | 12700             |
| Data            | 12701             |
| Metrics         | 12702             |
| Trading         | 12132             |
| Chronos         | 12710 - 12717     |
| TimesFM         | 12720 - 12721     |

---

## Shared Error Response Format

All services return structured error objects on failure. Clients must handle errors by inspecting the `error` field, not the HTTP status code alone.

```json
{
  "error": "ERROR_CODE",
  "message": "Human-readable description of the failure.",
  "details": {
    "request_id": "abc-123"
  }
}
```

### Error Codes

| Code                  | Meaning                                              |
|-----------------------|------------------------------------------------------|
| `VALIDATION_ERROR`    | Request body failed schema or constraint validation  |
| `MODEL_UNAVAILABLE`   | The requested model is not loaded or reachable       |
| `SERVICE_UNAVAILABLE` | A downstream dependency is not responding            |
| `TIMEOUT`             | The operation exceeded the configured timeout        |
| `COMPUTATION_ERROR`   | A numerical or algorithmic failure occurred          |
| `INTERNAL_ERROR`      | An unexpected server-side failure occurred           |

---

## 1. Orchestration Predict API

**Base URL:** `http://localhost:12700`

### POST /orchestration/v1/predict

Submits a forecast inference request. The orchestration service routes the request to the appropriate forecast container based on the `model` field, collects the result, and returns a unified response.

**Authentication:** Bearer token via `Authorization` header. The token must match the value of the `API_SECRET_KEY` environment variable on the orchestration service.

```
Authorization: Bearer <API_SECRET_KEY>
```

**Timeout:** 300 seconds. Configurable via the `INFERENCE_TIMEOUT` environment variable.

---

#### Request Body — `InferenceRequest`

```json
{
  "ticker": "SPY",
  "model": "amazon/chronos-t5-tiny",
  "context": {
    "values": [450.0, 451.2, 449.8, 452.1, 453.5],
    "period": "1d",
    "source": "yahoo",
    "start_date": "2025-09-01",
    "end_date": "2025-12-30",
    "field": "close"
  },
  "horizon": {
    "length": 10,
    "period": "1d"
  },
  "params": {
    "num_samples": 20,
    "temperature": 1.0
  }
}
```

| Field                    | Type          | Required | Constraints                        | Description                                     |
|--------------------------|---------------|----------|------------------------------------|-------------------------------------------------|
| `ticker`                 | string        | Yes      | 1 - 20 characters                  | Ticker symbol to forecast                       |
| `model`                  | string        | Yes      |                                    | Model identifier (e.g. `amazon/chronos-t5-tiny`)|
| `context`                | ContextData   | Yes      |                                    | Historical data with provenance metadata        |
| `context.values`         | list[float]   | Yes      | min_length=1                       | Time-series values, oldest first                |
| `context.period`         | string        | Yes      | Period enum                        | Data frequency (`1d`, `1h`, `1w`, etc.)         |
| `context.source`         | string        | Yes      | DataSource enum                    | Data origin (`yahoo`, `influxdb`, etc.)         |
| `context.start_date`     | string        | Yes      | YYYY-MM-DD                         | First date in the series                        |
| `context.end_date`       | string        | Yes      | YYYY-MM-DD                         | Last date in the series                         |
| `context.field`          | string        | No       | DataField enum, default `close`    | OHLCV field (`close`, `open`, `high`, etc.)     |
| `horizon`                | HorizonSpec   | Yes      |                                    | Forecast horizon specification                  |
| `horizon.length`         | integer       | Yes      | 1 - 365                            | Number of periods to forecast                   |
| `horizon.period`         | string        | Yes      | Period enum                        | Forecast frequency (should match context)       |
| `params`                 | ModelParams   | No       |                                    | Optional model-level inference parameters       |
| `params.num_samples`     | integer       | No       | default 20, max 100                | Number of sample trajectories                   |
| `params.temperature`     | float         | No       | default 1.0, max 2.0               | Sampling temperature                            |
| `params.top_k`           | integer       | No       | default 50                         | Top-k sampling cutoff                           |
| `params.top_p`           | float         | No       | default 1.0, 0.0 - 1.0             | Nucleus sampling probability                    |
| `request_id`             | string        | No       | Auto-generated UUID if omitted     | Request identifier for distributed tracing      |

---

#### Response Body — `InferenceResponse`

```json
{
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "response_id": "660f9511-f30c-52e5-b827-557766551111",
  "timestamp": "2025-12-31T14:30:02Z",
  "ticker": "SPY",
  "model": "amazon/chronos-t5-tiny",
  "forecast": {
    "values": [452.1, 453.0, 451.8, 454.2, 455.0],
    "period": "1d",
    "start_date": "2025-12-31",
    "end_date": "2026-01-06"
  },
  "context_summary": {
    "length": 90,
    "period": "1d",
    "source": "yahoo",
    "start_date": "2025-09-01",
    "end_date": "2025-12-30",
    "field": "close"
  },
  "quantiles": [
    {"quantile": 0.1, "values": [450.0, 451.0, 449.5, 452.0, 453.0]},
    {"quantile": 0.9, "values": [454.0, 455.0, 454.0, 456.5, 457.0]}
  ],
  "metadata": {
    "inference_time_ms": 1240,
    "model_version": "amazon/chronos-t5-tiny",
    "device": "cpu",
    "model_family": "chronos"
  }
}
```

| Field                          | Type              | Description                                              |
|--------------------------------|-------------------|----------------------------------------------------------|
| `request_id`                   | string            | Echo of the originating request ID                       |
| `response_id`                  | string            | Unique response identifier (auto-generated UUID)         |
| `timestamp`                    | string            | Response creation timestamp (ISO 8601 UTC)               |
| `ticker`                       | string            | Ticker symbol                                            |
| `model`                        | string            | Model that served the request                            |
| `forecast`                     | ForecastData      | Forecast output                                          |
| `forecast.values`              | list[float]       | Point forecast values for each horizon step              |
| `forecast.period`              | string            | Forecast frequency                                       |
| `forecast.start_date`          | string            | First forecast date (YYYY-MM-DD)                         |
| `forecast.end_date`            | string            | Last forecast date (YYYY-MM-DD)                          |
| `context_summary`              | ContextSummary    | Summary of the input context used                        |
| `context_summary.length`       | integer           | Number of context points used                            |
| `context_summary.period`       | string            | Context data frequency                                   |
| `context_summary.source`       | string            | Data origin                                              |
| `context_summary.start_date`   | string            | Context start date                                       |
| `context_summary.end_date`     | string            | Context end date                                         |
| `context_summary.field`        | string            | OHLCV field used                                         |
| `quantiles`                    | list[QuantileForecast] | Optional. Each entry has `quantile` level and `values` |
| `metadata.inference_time_ms`   | integer           | Inference execution time in milliseconds                 |
| `metadata.model_version`       | string            | Model version or checkpoint (optional)                   |
| `metadata.device`              | string            | Compute device used (optional)                           |
| `metadata.model_family`        | string            | Model family identifier (optional)                       |

---

#### Error Responses

| HTTP Status | Error Code              | Condition                                            |
|-------------|-------------------------|------------------------------------------------------|
| 400         | `VALIDATION_ERROR`      | Request body is malformed or fails field constraints |
| 503         | `SERVICE_UNAVAILABLE`   | Forecast container is not reachable                  |
| 503         | `MODEL_UNAVAILABLE`     | The requested model is not loaded                    |
| 504         | `TIMEOUT`               | Forecast container did not respond within the timeout |

---

## 2. Trading Execute API

**Base URL:** `http://localhost:12132`

### POST /trading/execute

Executes a trading strategy decision given a forecast price, current market state, and account position. This endpoint is for internal use only and is not exposed to public ingress.

**Authentication:** Bearer token via `Authorization` header. The token must match the value of the `TRADING_API_KEY` environment variable.

```
Authorization: Bearer <TRADING_API_KEY>
```

**Timeout:** 30 seconds.

---

#### Request Body

```json
{
  "strategy_type": "threshold",
  "forecast_price": 155.0,
  "current_price": 150.0,
  "current_position": 10.0,
  "available_cash": 5000.0,
  "initial_capital": 10000.0,
  "threshold_type": "absolute",
  "threshold_value": 2.0,
  "execution_size": 10.0
}
```

| Field               | Type    | Required | Description                                                   |
|---------------------|---------|----------|---------------------------------------------------------------|
| `strategy_type`     | string  | Yes      | Strategy identifier: `threshold`, `return`, or `quantile`     |
| `forecast_price`    | float   | Yes      | Model-predicted price for the horizon                         |
| `current_price`     | float   | Yes      | Current observed market price                                 |
| `current_position`  | float   | Yes      | Number of shares/units currently held                         |
| `available_cash`    | float   | Yes      | Cash available for purchase                                   |
| `initial_capital`   | float   | Yes      | Original starting capital, used for position sizing           |
| Additional fields   | varies  | No       | Strategy-specific params (e.g. `threshold_type`, `threshold_value`) |

---

#### Response Body

```json
{
  "action": "buy",
  "size": 5.0,
  "value": 750.0,
  "reason": "Forecast price exceeds threshold of 2.0 above current price.",
  "available_cash": 4250.0,
  "position_after": 15.0,
  "stopped": false
}
```

| Field            | Type    | Description                                                      |
|------------------|---------|------------------------------------------------------------------|
| `action`         | string  | Decision: `buy`, `sell`, or `hold`                               |
| `size`           | float   | Number of shares/units to transact                               |
| `value`          | float   | Total value of the transaction at `current_price`                |
| `reason`         | string  | Human-readable explanation of the decision                       |
| `available_cash` | float   | Remaining cash after the transaction                             |
| `position_after` | float   | Share/unit count after the transaction                           |
| `stopped`        | boolean | True if no capital/position remains and strategy should halt     |

---

#### Error Responses

| HTTP Status | Error Code            | Condition                                         |
|-------------|-----------------------|---------------------------------------------------|
| 400         | `VALIDATION_ERROR`    | Missing or invalid request fields                 |
| 503         | `SERVICE_UNAVAILABLE` | Trading service is unavailable                    |

---

## 3. Metrics Compute API

**Base URL:** `http://localhost:12702`

### POST /metrics/v1/compute/

Computes quantitative performance metrics from a return series. No authentication is required. An optional `X-Run-ID` header can be supplied for tracing.

**Authentication:** None.

**Optional Header:** `X-Run-ID: <run-identifier>`

**Timeout:** 30 seconds.

---

#### Request Body

```json
{
  "returns": [0.01, -0.005, 0.02, 0.003, -0.01],
  "metric": "all",
  "risk_free_rate": 0.0,
  "periods_per_year": 252,
  "include_interpretation": true
}
```

| Field                    | Type         | Required | Default | Description                                                                              |
|--------------------------|--------------|----------|---------|------------------------------------------------------------------------------------------|
| `returns`                | list[float]  | Yes      |         | Sequence of period returns (e.g. daily log returns or simple returns)                    |
| `metric`                 | string       | No       | `performance` | One of: `all`, `performance`, `sharpe`, `max_drawdown`, `cagr`, `calmar`, `win_rate` |
| `risk_free_rate`         | float        | No       | 0.0     | Annualized risk-free rate for Sharpe and Calmar calculations                             |
| `periods_per_year`       | integer      | No       | 252     | Number of return periods per year (252 for daily, 52 for weekly, 12 for monthly)         |
| `include_interpretation` | boolean      | No       | false   | If true, include a human-readable interpretation of results in the response              |

---

#### Response Body — metric: `all`

```json
{
  "sharpe_ratio": 1.42,
  "max_drawdown": -0.18,
  "cagr": 0.23,
  "calmar_ratio": 1.28,
  "win_rate": 0.54
}
```

#### Response Body — metric: `performance`

Returns all fields from `all`, plus interpretation and metadata when `include_interpretation` is true.

```json
{
  "sharpe_ratio": 1.42,
  "max_drawdown": -0.18,
  "cagr": 0.23,
  "calmar_ratio": 1.28,
  "win_rate": 0.54,
  "interpretation": "The strategy produces risk-adjusted returns above the benchmark threshold.",
  "metadata": {
    "periods": 252,
    "risk_free_rate": 0.0,
    "periods_per_year": 252
  }
}
```

For singular metric requests (e.g. `metric: "sharpe"`), only the corresponding field is returned.

---

#### Error Responses

| HTTP Status | Error Code           | Condition                                         |
|-------------|----------------------|---------------------------------------------------|
| 400         | `VALIDATION_ERROR`   | Invalid metric name or malformed returns list     |
| 500         | `COMPUTATION_ERROR`  | Numerical failure during metric calculation       |

---

## 4. Forecast Container APIs

Forecast containers are internal-only services. They accept requests exclusively from the orchestration service and must not be exposed to public ingress.

**Authentication:** Bearer token via `Authorization` header.

**Timeout:** 300 seconds.

### Chronos

**Ports:** 12710 - 12717 (one container per port)

#### POST /forecast/v1/inference

Runs a Chronos model inference pass on a supplied time series context.

---

### TimesFM

**Ports:** 12720 - 12721

#### POST /forecast/v1/timesfm20/inference

Runs a TimesFM 2.0 model inference pass on a supplied time series context.

---

Both forecast endpoints accept and return data in a format consistent with the `InferenceRequest` and `InferenceResponse` schemas defined in the Orchestration Predict API section above. The orchestration service is responsible for translating between the public contract and the internal container protocol.

---

## 5. Data Service API

**Base URL:** `http://localhost:12701`

**Timeout:** 60 seconds.

The data service provides access to historical OHLCV data from InfluxDB, ingestion from Yahoo Finance, and persistence of backtest results.

---

### POST /v1/data/query

Queries historical OHLCV price data from InfluxDB for a given ticker.

**Authentication:** None (internal network only).

#### Request Body

```json
{
  "ticker": "AAPL",
  "days": 90,
  "end_date": "2024-12-31"
}
```

| Field      | Type    | Required | Description                                              |
|------------|---------|----------|----------------------------------------------------------|
| `ticker`   | string  | Yes      | Ticker symbol to query                                   |
| `days`     | integer | Yes      | Number of calendar days of history to retrieve           |
| `end_date` | string  | No       | ISO 8601 date. Defaults to today if omitted              |

#### Response Body

```json
{
  "ticker": "AAPL",
  "data": [
    {
      "time": "2024-12-31T00:00:00Z",
      "open": 148.5,
      "high": 152.0,
      "low": 147.8,
      "close": 150.2,
      "volume": 82000000,
      "adj_close": 150.2
    }
  ],
  "count": 90
}
```

| Field           | Type         | Description                                        |
|-----------------|--------------|----------------------------------------------------|
| `ticker`        | string       | Echo of the requested ticker                       |
| `data`          | list[object] | Array of OHLCV records sorted ascending by time    |
| `data[].time`   | string       | ISO 8601 UTC timestamp                             |
| `data[].open`   | float        | Opening price                                      |
| `data[].high`   | float        | Daily high price                                   |
| `data[].low`    | float        | Daily low price                                    |
| `data[].close`  | float        | Closing price                                      |
| `data[].volume` | integer      | Share volume                                       |
| `data[].adj_close` | float     | Adjusted closing price                             |
| `count`         | integer      | Number of records returned                         |

---

### POST /v1/data/fetch

Fetches fresh data from Yahoo Finance and writes it to InfluxDB.

**Authentication:** None (internal network only).

#### Request Body

```json
{
  "names": ["AAPL", "MSFT", "GOOG"],
  "start_date": "2024-01-01",
  "interval": "1d"
}
```

| Field        | Type         | Required | Description                                             |
|--------------|--------------|----------|---------------------------------------------------------|
| `names`      | list[string] | Yes      | List of ticker symbols to fetch                         |
| `start_date` | string       | Yes      | ISO 8601 date. Start of the fetch window                |
| `interval`   | string       | Yes      | Data interval (e.g. `1d`, `1h`)                         |

#### Response Body

```json
{
  "status": "success",
  "message": "Fetched and wrote 3 tickers.",
  "details": {
    "AAPL": "252 records written",
    "MSFT": "252 records written",
    "GOOG": "251 records written"
  }
}
```

---

### POST /v1/data/write_results

Persists backtest results and associated metrics for a completed run.

**Authentication:** None (internal network only).

#### Request Body

```json
{
  "run_id": "run-20241231-001",
  "ticker": "AAPL",
  "model": "amazon/chronos-t5-tiny",
  "strategy": "threshold",
  "results": [
    {
      "date": "2024-12-31",
      "forecast": 155.0,
      "actual": 150.2,
      "signal": "buy",
      "position": 10.0,
      "cash": 4250.0,
      "portfolio_value": 5752.0
    }
  ],
  "metrics": {
    "sharpe_ratio": 1.42,
    "max_drawdown": -0.18,
    "cagr": 0.23,
    "calmar_ratio": 1.28,
    "win_rate": 0.54
  }
}
```

| Field                       | Type         | Required | Description                                       |
|-----------------------------|--------------|----------|---------------------------------------------------|
| `run_id`                    | string       | Yes      | Unique identifier for this backtest run           |
| `ticker`                    | string       | Yes      | Ticker symbol used in the backtest                |
| `model`                     | string       | Yes      | Model identifier used for forecasting             |
| `strategy`                  | string       | Yes      | Strategy identifier used for trade decisions      |
| `results`                   | list[object] | Yes      | Per-step result log for the backtest run          |
| `results[].date`            | string       | Yes      | Evaluation date (YYYY-MM-DD)                      |
| `results[].forecast`        | float        | Yes      | Model-predicted price                             |
| `results[].actual`          | float        | Yes      | Actual observed price                             |
| `results[].signal`          | string       | Yes      | Trade signal (buy, sell, hold)                    |
| `results[].position`        | float        | Yes      | Position size after this step                     |
| `results[].cash`            | float        | Yes      | Cash remaining after this step                    |
| `results[].portfolio_value` | float        | Yes      | Total portfolio value after this step             |
| `metrics`                   | object       | Yes      | Aggregate performance metrics for the run         |

#### Response Body

```json
{
  "status": "success",
  "points_written": 2,
  "run_id": "run-20241231-001"
}
```

---

#### Error Responses (Data Service)

| HTTP Status | Error Code            | Condition                                             |
|-------------|-----------------------|-------------------------------------------------------|
| 400         | `VALIDATION_ERROR`    | Missing required fields or invalid types              |
| 503         | `SERVICE_UNAVAILABLE` | InfluxDB or Yahoo Finance connection failure          |
| 500         | `INTERNAL_ERROR`      | Unexpected write or serialization failure             |

---

## Environment Variable Reference

| Variable            | Service       | Description                                          |
|---------------------|---------------|------------------------------------------------------|
| `API_SECRET_KEY`    | Orchestration | Bearer token for authenticating predict requests     |
| `INFERENCE_TIMEOUT` | Orchestration | Inference timeout in seconds (default: 300)          |
| `TRADING_API_KEY`   | Trading       | Bearer token for authenticating execute requests     |
