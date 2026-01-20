# Sapheneia-Aleutian Integration Design v2.0

**Date:** 2026-01-20
**Status:** Ready for Review
**Authors:** Integration Team

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Current State Analysis](#current-state-analysis)
3. [Target Architecture](#target-architecture)
4. [Simulation Storage Design](#simulation-storage-design)
5. [Model Port Configuration](#model-port-configuration)
6. [Docker Compose Updates](#docker-compose-updates)
7. [Environment Variables](#environment-variables)
8. [API Contract Updates](#api-contract-updates)
9. [Implementation Checklist](#implementation-checklist)

---

## Executive Summary

This design document outlines the integration between Sapheneia (Python forecasting platform) and Aleutian (Go orchestration layer) for time series forecasting and backtesting workflows. Key objectives:

1. **Unified API Contract**: Migrate from legacy `/v1/timeseries/forecast` to new `/orchestration/v1/predict` endpoint
2. **Simulation Storage**: Design partitioned storage for forecast simulations by date/ticker/version
3. **Model Isolation**: Each model runs in its own container on a dedicated port
4. **Configuration Centralization**: All ports defined in Sapheneia `.env` file

---

## Current State Analysis

### Aleutian (Go) - Current Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ALEUTIAN TIMESERIES STACK                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────────┐      ┌─────────────────────┐                         │
│  │  CLI / Evaluator │      │   Orchestrator      │                         │
│  │  (Go Binary)     │─────▶│   Port: 12210       │                         │
│  └──────────────────┘      │   (timeseries.go)   │                         │
│                            └──────────┬──────────┘                         │
│                                       │                                     │
│                        ┌──────────────┼──────────────┐                     │
│                        ▼              ▼              ▼                     │
│              ┌─────────────────┐  ┌─────────────┐  ┌─────────────────┐    │
│              │  Sapheneia      │  │  InfluxDB   │  │  Data Fetcher   │    │
│              │  Models         │  │  Port: 12130│  │  Port: 12001    │    │
│              │  12700-12779    │  └─────────────┘  └─────────────────┘    │
│              └─────────────────┘                                           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Current Model Routing (timeseries.go)

| Model Family | Container | Internal Port | External Port |
|--------------|-----------|---------------|---------------|
| Main API (TimesFM) | sapheneia-forecast | 8000 | 12700 |
| Chronos T5 Tiny | forecast-chronos-t5-tiny | 8000 | 12710 |
| Chronos T5 Mini | forecast-chronos-t5-mini | 8000 | 12711 |
| Chronos T5 Small | forecast-chronos-t5-small | 8000 | 12712 |
| Chronos T5 Base | forecast-chronos-t5-base | 8000 | 12713 |
| Chronos T5 Large | forecast-chronos-t5-large | 8000 | 12714 |
| Chronos Bolt Mini | forecast-chronos-bolt-mini | 8000 | 12715 |
| Chronos Bolt Small | forecast-chronos-bolt-small | 8000 | 12716 |
| Chronos Bolt Base | forecast-chronos-bolt-base | 8000 | 12717 |

### Issues with Current State

1. **Legacy API**: Still using `/v1/timeseries/forecast` instead of unified `/orchestration/v1/predict`
2. **No Request Tracing**: Missing request_id/response_id correlation
3. **No Simulation Storage**: Forecast results not persisted for analysis
4. **Hardcoded Ports**: Port assignments buried in docker-compose, not configurable
5. **Missing Model Families**: TimesFM, Moirai, Granite, Moment not deployed

---

## Target Architecture

### Service Topology

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              INTEGRATED SYSTEM ARCHITECTURE                          │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  ALEUTIAN STACK (podman-compose.timeseries.yml)                                     │
│  ┌────────────────────────────────────────────────────────────────────────────────┐ │
│  │                                                                                 │ │
│  │  ┌─────────────────────┐    ┌────────────────┐    ┌────────────────────────┐  │ │
│  │  │ Orchestrator:12210  │───▶│ InfluxDB:12130 │    │ Data Fetcher:12001     │  │ │
│  │  │ (Go Service)        │    │ (Time Series)  │    │ (Yahoo Finance → DB)   │  │ │
│  │  └──────────┬──────────┘    └────────────────┘    └────────────────────────┘  │ │
│  │             │                                                                  │ │
│  │             │ ALEUTIAN_FORECAST_MODE=sapheneia                                │ │
│  │             │ Routes to Sapheneia containers by model name                    │ │
│  │             ▼                                                                  │ │
│  └────────────────────────────────────────────────────────────────────────────────┘ │
│                │                                                                     │
│                │ Network: aleutian-shared                                           │
│                ▼                                                                     │
│  SAPHENEIA STACK (docker-compose.yml)                                               │
│  ┌────────────────────────────────────────────────────────────────────────────────┐ │
│  │                                                                                 │ │
│  │  ┌────────────────────────────────────────────────────────────────────────┐   │ │
│  │  │                    ORCHESTRATION GATEWAY (:12700)                      │   │ │
│  │  │    POST /orchestration/v1/predict  ──────▶  Model Router              │   │ │
│  │  │    POST /v1/timeseries/forecast (legacy)   (routes by model param)    │   │ │
│  │  └─────────────────────────────────┬──────────────────────────────────────┘   │ │
│  │                                    │                                          │ │
│  │           ┌────────────────────────┼────────────────────────┐                │ │
│  │           ▼                        ▼                        ▼                │ │
│  │  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────────────┐  │ │
│  │  │ TIMESFM CLUSTER │    │ CHRONOS CLUSTER │    │ FUTURE MODELS           │  │ │
│  │  │                 │    │                 │    │                         │  │ │
│  │  │ timesfm-2.0:    │    │ t5-tiny:12710  │    │ moirai-1.1-small:12733 │  │ │
│  │  │           12720 │    │ t5-mini:12711  │    │ moirai-1.1-base:12734  │  │ │
│  │  │ timesfm-2.5:    │    │ t5-small:12712 │    │ granite-ttm-r1:12740   │  │ │
│  │  │           12721 │    │ t5-base:12713  │    │ moment-small:12750     │  │ │
│  │  │                 │    │ t5-large:12714 │    │ ...                    │  │ │
│  │  │                 │    │ bolt-mini:12715│    │                         │  │ │
│  │  │                 │    │ bolt-sml:12716 │    │                         │  │ │
│  │  │                 │    │ bolt-base:12717│    │                         │  │ │
│  │  └─────────────────┘    └─────────────────┘    └─────────────────────────┘  │ │
│  │                                                                              │ │
│  │  ┌────────────────────────────────────────────────────────────────────────┐ │ │
│  │  │  SUPPORTING SERVICES                                                    │ │ │
│  │  │                                                                         │ │ │
│  │  │  Trading API:12132   │   Data Service:12701  │   UI:12780              │ │ │
│  │  │  (Strategy Exec)     │   (Yahoo Finance)     │   (Web Interface)       │ │ │
│  │  └────────────────────────────────────────────────────────────────────────┘ │ │
│  │                                                                              │ │
│  │  ┌────────────────────────────────────────────────────────────────────────┐ │ │
│  │  │  SIMULATION STORAGE  (/simulations)                                    │ │ │
│  │  │                                                                         │ │ │
│  │  │  /simulations/                                                          │ │ │
│  │  │    ├── strategies/{strategy_id}/                                       │ │ │
│  │  │    ├── backtests/{run_id}/                                             │ │ │
│  │  │    └── forecasts/{YYYY}/{MM}/{DD}/{ticker}/{model}/{version}/          │ │ │
│  │  └────────────────────────────────────────────────────────────────────────┘ │ │
│  │                                                                              │ │
│  └──────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Simulation Storage Design

### Directory Structure

```
/Users/jin/PycharmProjects/sapheneia/simulations/
├── forecasts/                           # Individual forecast results
│   └── {YYYY}/                          # Year partition
│       └── {MM}/                        # Month partition
│           └── {DD}/                    # Day partition
│               └── {ticker}/            # Asset symbol (SPY, AAPL, BTC-USD)
│                   └── {model}/         # Model family (chronos-t5-tiny)
│                       └── {version}/   # Model version or run variant
│                           ├── forecast_{request_id}.json
│                           └── metadata.json
│
├── backtests/                           # Backtest run outputs
│   └── {run_id}/                        # UUID run identifier
│       ├── config.json                  # BacktestScenario configuration
│       ├── summary.json                 # Aggregate metrics
│       ├── trades.jsonl                 # Trade-by-trade log (JSONL)
│       ├── equity_curve.csv             # Portfolio value over time
│       └── forecasts/                   # All forecasts used in this run
│           └── {date}_{ticker}_{request_id}.json
│
├── strategies/                          # Strategy configurations
│   └── {strategy_id}/
│       ├── config.json                  # Strategy parameters
│       ├── performance.json             # Historical performance
│       └── backtests/                   # Links to backtest runs
│           └── {run_id}.link            # Symlinks to backtest dirs
│
├── models/                              # Model registry & metadata
│   └── {model_family}/
│       └── {model_variant}/
│           ├── metadata.json            # Model info (params, checkpoint)
│           ├── performance.json         # Aggregate accuracy metrics
│           └── versions/
│               └── {version}/
│                   └── metrics.json
│
└── index/                               # Search indices for quick lookup
    ├── by_ticker.json                   # {ticker: [forecast_paths]}
    ├── by_model.json                    # {model: [forecast_paths]}
    ├── by_date.json                     # {date: [forecast_paths]}
    └── runs.json                        # All backtest runs
```

### Forecast File Schema

```json
// simulations/forecasts/2026/01/20/SPY/chronos-t5-tiny/v1/forecast_{uuid}.json
{
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "response_id": "660f9511-f30c-52e5-b827-557766551111",
  "timestamp": "2026-01-20T14:30:02Z",

  "ticker": "SPY",
  "model": "amazon/chronos-t5-tiny",
  "model_version": "1.0.0",

  "context": {
    "values": [450.0, 451.2, 449.8, 452.1, 453.5],
    "period": "1d",
    "source": "influxdb",
    "start_date": "2025-09-01",
    "end_date": "2025-12-30",
    "field": "close"
  },

  "forecast": {
    "values": [454.2, 455.0, 453.8, 456.1, 457.2],
    "period": "1d",
    "start_date": "2026-01-20",
    "end_date": "2026-01-24"
  },

  "quantiles": [
    {"quantile": 0.1, "values": [452.1, 452.8, 451.5, 453.8, 454.9]},
    {"quantile": 0.5, "values": [454.2, 455.0, 453.8, 456.1, 457.2]},
    {"quantile": 0.9, "values": [456.3, 457.2, 456.1, 458.4, 459.5]}
  ],

  "metadata": {
    "inference_time_ms": 245,
    "device": "cpu",
    "num_samples": 20,
    "model_family": "chronos"
  }
}
```

### Backtest Summary Schema

```json
// simulations/backtests/{run_id}/summary.json
{
  "run_id": "abc123-def456",
  "created_at": "2026-01-20T15:00:00Z",
  "completed_at": "2026-01-20T15:30:00Z",

  "config": {
    "ticker": "SPY",
    "model": "amazon/chronos-t5-tiny",
    "strategy_type": "threshold",
    "start_date": "2025-01-01",
    "end_date": "2025-12-31",
    "initial_capital": 100000.0,
    "context_size": 252,
    "horizon_size": 5
  },

  "performance": {
    "total_return": 0.1523,
    "sharpe_ratio": 1.45,
    "max_drawdown": -0.0812,
    "win_rate": 0.58,
    "total_trades": 156,
    "winning_trades": 90,
    "losing_trades": 66
  },

  "forecast_accuracy": {
    "mae": 2.34,
    "rmse": 3.12,
    "mape": 0.0156,
    "directional_accuracy": 0.62
  },

  "forecasts_used": 252,
  "trades_executed": 156,
  "final_portfolio_value": 115230.00
}
```

### Storage Configuration

Add to Sapheneia `.env`:

```bash
# Simulation Storage Configuration
SIMULATIONS_ROOT=/simulations
SIMULATIONS_RETENTION_DAYS=365
SIMULATIONS_INDEX_ENABLED=true
SIMULATIONS_COMPRESSION_ENABLED=true
```

Add Docker volume mount in `docker-compose.yml`:

```yaml
volumes:
  - ./simulations:/simulations
```

---

## Model Port Configuration

### Port Allocation Scheme

Uses the 127xx range to avoid collisions with common services. Consistent with Aleutian's existing 12xxx port scheme.

| Port Range | Model Family | Notes |
|------------|--------------|-------|
| 12700 | Orchestration Gateway | Routes to appropriate model |
| 12701 | Data Service | Yahoo Finance data ingestion |
| 12702 | Metrics API | Financial metrics |
| 12710-12719 | Amazon Chronos | T5 + Bolt variants |
| 12720-12729 | Google TimesFM | 2.0, 2.5 versions |
| 12730-12739 | Salesforce Moirai | 1.0, 1.1, 2.0 |
| 12740-12749 | IBM Granite | TTM-R1, TTM-R2, FlowState |
| 12750-12759 | AutoLab Moment | small, base, large |
| 12760-12769 | Alibaba Yinglong | 6m, 50m, 110m, 300m |
| 12770-12779 | Other Models | Lag-Llama, Kairos, TimeMOE |
| 12780 | UI | Web interface |
| 12132 | Trading API | Strategy execution |

### Complete .env.template Port Configuration

```bash
# =============================================================================
# MODEL PORT CONFIGURATION
# =============================================================================
# All model ports are defined here for centralized configuration.
# Update these values to change port assignments across the system.
#
# Uses 127xx range to avoid collisions with common services.
# Consistent with Aleutian's 12xxx port scheme:
#   12210 - Aleutian Orchestrator
#   12130 - InfluxDB
#   12001 - Data Fetcher

# --- Orchestration Gateway ---
ORCHESTRATION_PORT=12700

# --- Amazon Chronos T5 Series ---
CHRONOS_T5_TINY_PORT=12710
CHRONOS_T5_MINI_PORT=12711
CHRONOS_T5_SMALL_PORT=12712
CHRONOS_T5_BASE_PORT=12713
CHRONOS_T5_LARGE_PORT=12714

# --- Amazon Chronos Bolt Series ---
CHRONOS_BOLT_MINI_PORT=12715
CHRONOS_BOLT_SMALL_PORT=12716
CHRONOS_BOLT_BASE_PORT=12717

# --- Google TimesFM ---
TIMESFM_2_0_PORT=12720
TIMESFM_2_5_PORT=12721

# --- Salesforce Moirai ---
MOIRAI_1_0_SMALL_PORT=12730
MOIRAI_1_0_BASE_PORT=12731
MOIRAI_1_0_LARGE_PORT=12732
MOIRAI_1_1_SMALL_PORT=12733
MOIRAI_1_1_BASE_PORT=12734
MOIRAI_1_1_LARGE_PORT=12735

# --- IBM Granite ---
GRANITE_TTM_R1_PORT=12740
GRANITE_TTM_R2_PORT=12741
GRANITE_FLOWSTATE_PORT=12742
GRANITE_PATCHTSMIXER_PORT=12743
GRANITE_PATCHTST_PORT=12744

# --- AutoLab Moment ---
MOMENT_SMALL_PORT=12750
MOMENT_BASE_PORT=12751
MOMENT_LARGE_PORT=12752

# --- Alibaba Yinglong ---
YINGLONG_6M_PORT=12760
YINGLONG_50M_PORT=12761
YINGLONG_110M_PORT=12762
YINGLONG_300M_PORT=12763

# --- Other Foundation Models ---
LAG_LLAMA_PORT=12770
KAIROS_PORT=12771
TIMEMOE_PORT=12772
TIMER_PORT=12773
SUNDIAL_PORT=12774

# --- Trading & Services ---
TRADING_API_PORT=12132
DATA_API_PORT=12701
UI_PORT=12780
METRICS_PORT=12702
```

---

## Docker Compose Updates

### Updated docker-compose.yml (Sapheneia)

This version uses `.env` variables for all port assignments:

```yaml
# docker-compose.yml - Sapheneia Multi-Model Forecasting Platform
# All ports read from .env file for centralized configuration

services:
  # =========================================================================
  # ORCHESTRATION GATEWAY
  # =========================================================================
  # Main entry point - routes requests to appropriate model containers
  forecast:
    build:
      context: .
      dockerfile: Dockerfile.forecast
      args:
        MODEL_NAME: all
        MODEL_PORT: 8000
    container_name: sapheneia-forecast
    ports:
      - "${ORCHESTRATION_PORT:-12700}:8000"
    env_file:
      - .env
    environment:
      - API_HOST=0.0.0.0
      - API_PORT=8000
      - MODEL_NAME=all
      - PYTHONPATH=/app
      - API_SECRET_KEY=${API_SECRET_KEY:-default_trading_api_key_please_change}
      # Model routing configuration (container names for internal routing)
      - CHRONOS_T5_TINY_URL=http://forecast-chronos-t5-tiny:8000
      - CHRONOS_T5_MINI_URL=http://forecast-chronos-t5-mini:8000
      - CHRONOS_T5_SMALL_URL=http://forecast-chronos-t5-small:8000
      - CHRONOS_T5_BASE_URL=http://forecast-chronos-t5-base:8000
      - CHRONOS_T5_LARGE_URL=http://forecast-chronos-t5-large:8000
      - CHRONOS_BOLT_MINI_URL=http://forecast-chronos-bolt-mini:8000
      - CHRONOS_BOLT_SMALL_URL=http://forecast-chronos-bolt-small:8000
      - CHRONOS_BOLT_BASE_URL=http://forecast-chronos-bolt-base:8000
      - TIMESFM_2_0_URL=http://forecast-timesfm-2-0:8000
    volumes:
      - ./forecast:/app/forecast
      - ./orchestration:/app/orchestration
      - ./data:/app/data
      - ./logs:/app/logs
      - ./simulations:/simulations
      - forecast_models_timesfm20:/app/forecast/models/timesfm20/local
      - ${MODELS_CACHE_PATH:-/Volumes/ai_models/aleutian_data/models_cache}:/models_cache
    networks:
      - aleutian-network
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 120s

  # =========================================================================
  # AMAZON CHRONOS T5 SERIES
  # =========================================================================

  forecast-chronos-t5-tiny:
    build:
      context: .
      dockerfile: Dockerfile.forecast
      args:
        MODEL_NAME: chronos
        MODEL_PORT: 8000
    container_name: forecast-chronos-t5-tiny
    ports:
      - "${CHRONOS_T5_TINY_PORT:-12710}:8000"
    environment:
      - API_HOST=0.0.0.0
      - API_PORT=8000
      - MODEL_NAME=chronos
      - MODEL_VARIANT=amazon/chronos-t5-tiny
      - HF_HOME=/models_cache
      - DEVICE=${DEVICE:-cpu}
      - PYTHONPATH=/app
      - API_SECRET_KEY=${API_SECRET_KEY:-default_trading_api_key_please_change}
      - SIMULATIONS_ROOT=/simulations
    volumes:
      - ./forecast:/app/forecast
      - ./logs:/app/logs
      - ./simulations:/simulations
      - ${MODELS_CACHE_PATH:-/Volumes/ai_models/aleutian_data/models_cache}:/models_cache
    networks:
      - aleutian-network
    restart: "no"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s

  forecast-chronos-t5-mini:
    build:
      context: .
      dockerfile: Dockerfile.forecast
      args:
        MODEL_NAME: chronos
        MODEL_PORT: 8000
    container_name: forecast-chronos-t5-mini
    ports:
      - "${CHRONOS_T5_MINI_PORT:-12711}:8000"
    environment:
      - API_HOST=0.0.0.0
      - API_PORT=8000
      - MODEL_NAME=chronos
      - MODEL_VARIANT=amazon/chronos-t5-mini
      - HF_HOME=/models_cache
      - DEVICE=${DEVICE:-cpu}
      - PYTHONPATH=/app
      - API_SECRET_KEY=${API_SECRET_KEY:-default_trading_api_key_please_change}
      - SIMULATIONS_ROOT=/simulations
    volumes:
      - ./forecast:/app/forecast
      - ./logs:/app/logs
      - ./simulations:/simulations
      - ${MODELS_CACHE_PATH:-/Volumes/ai_models/aleutian_data/models_cache}:/models_cache
    networks:
      - aleutian-network
    restart: "no"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s

  forecast-chronos-t5-small:
    build:
      context: .
      dockerfile: Dockerfile.forecast
      args:
        MODEL_NAME: chronos
        MODEL_PORT: 8000
    container_name: forecast-chronos-t5-small
    ports:
      - "${CHRONOS_T5_SMALL_PORT:-12712}:8000"
    environment:
      - API_HOST=0.0.0.0
      - API_PORT=8000
      - MODEL_NAME=chronos
      - MODEL_VARIANT=amazon/chronos-t5-small
      - HF_HOME=/models_cache
      - DEVICE=${DEVICE:-cpu}
      - PYTHONPATH=/app
      - API_SECRET_KEY=${API_SECRET_KEY:-default_trading_api_key_please_change}
      - SIMULATIONS_ROOT=/simulations
    volumes:
      - ./forecast:/app/forecast
      - ./logs:/app/logs
      - ./simulations:/simulations
      - ${MODELS_CACHE_PATH:-/Volumes/ai_models/aleutian_data/models_cache}:/models_cache
    networks:
      - aleutian-network
    restart: "no"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s

  forecast-chronos-t5-base:
    build:
      context: .
      dockerfile: Dockerfile.forecast
      args:
        MODEL_NAME: chronos
        MODEL_PORT: 8000
    container_name: forecast-chronos-t5-base
    ports:
      - "${CHRONOS_T5_BASE_PORT:-12713}:8000"
    environment:
      - API_HOST=0.0.0.0
      - API_PORT=8000
      - MODEL_NAME=chronos
      - MODEL_VARIANT=amazon/chronos-t5-base
      - HF_HOME=/models_cache
      - DEVICE=${DEVICE:-cpu}
      - PYTHONPATH=/app
      - API_SECRET_KEY=${API_SECRET_KEY:-default_trading_api_key_please_change}
      - SIMULATIONS_ROOT=/simulations
    volumes:
      - ./forecast:/app/forecast
      - ./logs:/app/logs
      - ./simulations:/simulations
      - ${MODELS_CACHE_PATH:-/Volumes/ai_models/aleutian_data/models_cache}:/models_cache
    networks:
      - aleutian-network
    restart: "no"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s

  forecast-chronos-t5-large:
    build:
      context: .
      dockerfile: Dockerfile.forecast
      args:
        MODEL_NAME: chronos
        MODEL_PORT: 8000
    container_name: forecast-chronos-t5-large
    ports:
      - "${CHRONOS_T5_LARGE_PORT:-12714}:8000"
    environment:
      - API_HOST=0.0.0.0
      - API_PORT=8000
      - MODEL_NAME=chronos
      - MODEL_VARIANT=amazon/chronos-t5-large
      - HF_HOME=/models_cache
      - DEVICE=${DEVICE:-cpu}
      - PYTHONPATH=/app
      - API_SECRET_KEY=${API_SECRET_KEY:-default_trading_api_key_please_change}
      - SIMULATIONS_ROOT=/simulations
    volumes:
      - ./forecast:/app/forecast
      - ./logs:/app/logs
      - ./simulations:/simulations
      - ${MODELS_CACHE_PATH:-/Volumes/ai_models/aleutian_data/models_cache}:/models_cache
    networks:
      - aleutian-network
    restart: "no"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s

  # =========================================================================
  # AMAZON CHRONOS BOLT SERIES
  # =========================================================================

  forecast-chronos-bolt-mini:
    build:
      context: .
      dockerfile: Dockerfile.forecast
      args:
        MODEL_NAME: chronos
        MODEL_PORT: 8000
    container_name: forecast-chronos-bolt-mini
    ports:
      - "${CHRONOS_BOLT_MINI_PORT:-12715}:8000"
    environment:
      - API_HOST=0.0.0.0
      - API_PORT=8000
      - MODEL_NAME=chronos
      - MODEL_VARIANT=amazon/chronos-bolt-mini
      - HF_HOME=/models_cache
      - DEVICE=${DEVICE:-cpu}
      - PYTHONPATH=/app
      - API_SECRET_KEY=${API_SECRET_KEY:-default_trading_api_key_please_change}
      - SIMULATIONS_ROOT=/simulations
    volumes:
      - ./forecast:/app/forecast
      - ./logs:/app/logs
      - ./simulations:/simulations
      - ${MODELS_CACHE_PATH:-/Volumes/ai_models/aleutian_data/models_cache}:/models_cache
    networks:
      - aleutian-network
    restart: "no"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s

  forecast-chronos-bolt-small:
    build:
      context: .
      dockerfile: Dockerfile.forecast
      args:
        MODEL_NAME: chronos
        MODEL_PORT: 8000
    container_name: forecast-chronos-bolt-small
    ports:
      - "${CHRONOS_BOLT_SMALL_PORT:-12716}:8000"
    environment:
      - API_HOST=0.0.0.0
      - API_PORT=8000
      - MODEL_NAME=chronos
      - MODEL_VARIANT=amazon/chronos-bolt-small
      - HF_HOME=/models_cache
      - DEVICE=${DEVICE:-cpu}
      - PYTHONPATH=/app
      - API_SECRET_KEY=${API_SECRET_KEY:-default_trading_api_key_please_change}
      - SIMULATIONS_ROOT=/simulations
    volumes:
      - ./forecast:/app/forecast
      - ./logs:/app/logs
      - ./simulations:/simulations
      - ${MODELS_CACHE_PATH:-/Volumes/ai_models/aleutian_data/models_cache}:/models_cache
    networks:
      - aleutian-network
    restart: "no"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s

  forecast-chronos-bolt-base:
    build:
      context: .
      dockerfile: Dockerfile.forecast
      args:
        MODEL_NAME: chronos
        MODEL_PORT: 8000
    container_name: forecast-chronos-bolt-base
    ports:
      - "${CHRONOS_BOLT_BASE_PORT:-12717}:8000"
    environment:
      - API_HOST=0.0.0.0
      - API_PORT=8000
      - MODEL_NAME=chronos
      - MODEL_VARIANT=amazon/chronos-bolt-base
      - HF_HOME=/models_cache
      - DEVICE=${DEVICE:-cpu}
      - PYTHONPATH=/app
      - API_SECRET_KEY=${API_SECRET_KEY:-default_trading_api_key_please_change}
      - SIMULATIONS_ROOT=/simulations
    volumes:
      - ./forecast:/app/forecast
      - ./logs:/app/logs
      - ./simulations:/simulations
      - ${MODELS_CACHE_PATH:-/Volumes/ai_models/aleutian_data/models_cache}:/models_cache
    networks:
      - aleutian-network
    restart: "no"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s

  # =========================================================================
  # GOOGLE TIMESFM (Placeholder - uncomment when implementing)
  # =========================================================================

  # forecast-timesfm-2-0:
  #   build:
  #     context: .
  #     dockerfile: Dockerfile.forecast
  #     args:
  #       MODEL_NAME: timesfm
  #       MODEL_PORT: 8000
  #   container_name: forecast-timesfm-2-0
  #   ports:
  #     - "${TIMESFM_2_0_PORT:-12720}:8000"
  #   environment:
  #     - API_HOST=0.0.0.0
  #     - API_PORT=8000
  #     - MODEL_NAME=timesfm
  #     - MODEL_VARIANT=google/timesfm-2.0-500m-pytorch
  #     - HF_HOME=/models_cache
  #     - DEVICE=${DEVICE:-cpu}
  #     - PYTHONPATH=/app
  #     - API_SECRET_KEY=${API_SECRET_KEY}
  #     - SIMULATIONS_ROOT=/simulations
  #   volumes:
  #     - ./forecast:/app/forecast
  #     - ./logs:/app/logs
  #     - ./simulations:/simulations
  #     - ${MODELS_CACHE_PATH}:/models_cache
  #   networks:
  #     - aleutian-network
  #   restart: "no"

  # =========================================================================
  # SUPPORTING SERVICES
  # =========================================================================

  # Trading Strategies API
  trading:
    build:
      context: .
      dockerfile: Dockerfile.trading
    container_name: sapheneia-trading
    ports:
      - "${TRADING_API_PORT:-12132}:9000"
    env_file:
      - .env
    environment:
      - TRADING_API_KEY=${TRADING_API_KEY:-default_trading_api_key_please_change}
      - TRADING_API_HOST=0.0.0.0
      - TRADING_API_PORT=9000
      - LOG_LEVEL=${LOG_LEVEL:-INFO}
      - ENVIRONMENT=${ENVIRONMENT:-development}
      - PYTHONPATH=/app
      - SIMULATIONS_ROOT=/simulations
    volumes:
      - ./trading:/app/trading
      - ./logs:/app/logs
      - ./simulations:/simulations
    networks:
      - aleutian-network
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  # Finance Data Service (Yahoo Finance → InfluxDB)
  data:
    build:
      context: .
      dockerfile: Dockerfile.data
    container_name: sapheneia-data
    ports:
      - "${DATA_API_PORT:-8001}:8000"
    environment:
      - INFLUXDB_URL=${INFLUXDB_URL:-http://user-influxdb:8086}
      - INFLUXDB_TOKEN=${INFLUXDB_TOKEN:-your_super_secret_admin_token}
      - INFLUXDB_ORG=${INFLUXDB_ORG:-aleutian-finance}
      - INFLUXDB_BUCKET=${INFLUXDB_BUCKET:-financial-data}
    networks:
      - aleutian-network
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 10s
      timeout: 5s
      retries: 20
      start_period: 10s

  # Flask UI
  ui:
    build:
      context: .
      dockerfile: Dockerfile.ui
    container_name: sapheneia-ui
    ports:
      - "${UI_PORT:-8080}:8080"
    environment:
      - UI_API_BASE_URL=http://forecast:8000
      - UI_PORT=8080
      - PYTHONPATH=/app
    volumes:
      - ./ui:/app/ui
      - ./data:/app/data
      - ./logs:/app/logs
      - ./simulations:/simulations
      - ui_results:/app/ui/results
    depends_on:
      forecast:
        condition: service_healthy
    networks:
      - aleutian-network
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s

networks:
  aleutian-network:
    external: true
    name: aleutian-shared

volumes:
  forecast_models_timesfm20:
    driver: local
  ui_results:
    driver: local
```

---

## Environment Variables

### Complete .env Template for Sapheneia

```bash
# =============================================================================
# SAPHENEIA CONFIGURATION - v2.0
# =============================================================================
# Copy to .env and configure with your values

# =============================================================================
# API CONFIGURATION
# =============================================================================

# API Security (REQUIRED - Change in production!)
API_SECRET_KEY=default_trading_api_key_please_change

# API Server Settings
API_HOST=0.0.0.0
API_PORT=8000
LOG_LEVEL=INFO
ENVIRONMENT=development

# Worker Configuration
# IMPORTANT: Keep at 1 for module-level state. Multiple workers require Redis.
UVICORN_WORKERS=1

# CORS Configuration
CORS_ALLOWED_ORIGINS=http://localhost:8080,http://localhost:3000,http://localhost:12210
CORS_ALLOW_CREDENTIALS=true
CORS_ALLOW_METHODS=GET,POST,PUT,DELETE,OPTIONS
CORS_ALLOW_HEADERS=*

# Rate Limiting
RATE_LIMIT_ENABLED=false
RATE_LIMIT_PER_MINUTE=60
RATE_LIMIT_INFERENCE_PER_MINUTE=10
RATE_LIMIT_STORAGE_URI=memory://

# =============================================================================
# MODEL PORT CONFIGURATION
# =============================================================================
# Centralized port assignment for all model containers (127xx range)

# Orchestration Gateway
ORCHESTRATION_PORT=12700

# Amazon Chronos T5 Series (12710-12714)
CHRONOS_T5_TINY_PORT=12710
CHRONOS_T5_MINI_PORT=12711
CHRONOS_T5_SMALL_PORT=12712
CHRONOS_T5_BASE_PORT=12713
CHRONOS_T5_LARGE_PORT=12714

# Amazon Chronos Bolt Series (12715-12717)
CHRONOS_BOLT_MINI_PORT=12715
CHRONOS_BOLT_SMALL_PORT=12716
CHRONOS_BOLT_BASE_PORT=12717

# Google TimesFM (12720-12729)
TIMESFM_2_0_PORT=12720
TIMESFM_2_5_PORT=12721

# Salesforce Moirai (12730-12739)
MOIRAI_1_1_SMALL_PORT=12733
MOIRAI_1_1_BASE_PORT=12734
MOIRAI_1_1_LARGE_PORT=12735

# IBM Granite (12740-12749)
GRANITE_TTM_R1_PORT=12740
GRANITE_TTM_R2_PORT=12741

# AutoLab Moment (12750-12759)
MOMENT_SMALL_PORT=12750
MOMENT_BASE_PORT=12751
MOMENT_LARGE_PORT=12752

# Alibaba Yinglong (12760-12769)
YINGLONG_50M_PORT=12761

# =============================================================================
# TRADING API CONFIGURATION
# =============================================================================

TRADING_API_KEY=dev_trading_api_key_12345678901234567890
TRADING_API_PORT=12132
TRADING_API_HOST=0.0.0.0

# =============================================================================
# DATA SERVICE CONFIGURATION
# =============================================================================

DATA_API_PORT=12701

# InfluxDB Connection (must match Aleutian setup)
INFLUXDB_URL=http://user-influxdb:8086
INFLUXDB_TOKEN=your_super_secret_admin_token
INFLUXDB_ORG=aleutian-finance
INFLUXDB_BUCKET=financial-data

# =============================================================================
# UI CONFIGURATION
# =============================================================================

UI_API_BASE_URL=http://localhost:8000
UI_PORT=8080

# =============================================================================
# SIMULATION STORAGE CONFIGURATION
# =============================================================================

SIMULATIONS_ROOT=/simulations
SIMULATIONS_RETENTION_DAYS=365
SIMULATIONS_INDEX_ENABLED=true
SIMULATIONS_COMPRESSION_ENABLED=false

# =============================================================================
# MODEL DEFAULTS
# =============================================================================

# TimesFM-2.0 Defaults
TIMESFM20_DEFAULT_BACKEND=cpu
TIMESFM20_DEFAULT_CONTEXT_LEN=64
TIMESFM20_DEFAULT_HORIZON_LEN=24
TIMESFM20_DEFAULT_CHECKPOINT=google/timesfm-2.0-500m-pytorch

# Device Configuration (cpu or cuda:0)
DEVICE=cpu

# Models Cache Path (external volume)
MODELS_CACHE_PATH=/Volumes/ai_models/aleutian_data/models_cache

# =============================================================================
# ALEUTIAN INTEGRATION
# =============================================================================

# These must match Aleutian's expectations
# Aleutian connects to these containers by name on aleutian-shared network:
#   - sapheneia-forecast (gateway)
#   - forecast-chronos-t5-tiny, forecast-chronos-t5-mini, etc.
#   - sapheneia-trading

# =============================================================================
# MLOPS INTEGRATION (Optional)
# =============================================================================

MLFLOW_TRACKING_URI=http://localhost:5000
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

### Aleutian Environment Variables

For `podman-compose.timeseries.yml`:

```bash
# Aleutian Timeseries Configuration
# Set ALEUTIAN_FORECAST_MODE=sapheneia to route to Sapheneia containers

# Forecast Service Configuration
ALEUTIAN_FORECAST_MODE=sapheneia  # or 'standalone' for local service
ALEUTIAN_TIMESERIES_TOOL=http://sapheneia-forecast:8000

# Trading Integration
SAPHENEIA_TRADING_SERVICE_URL=http://sapheneia-trading:9000
SAPHENEIA_TRADING_API_KEY=default_trading_api_key_please_change

# Data Services
ALEUTIAN_DATA_FETCHER_URL=http://data-fetcher:8001

# InfluxDB (shared with Sapheneia)
INFLUXDB_URL=http://influxdb:8086
INFLUXDB_TOKEN=${DOCKER_INFLUXDB_INIT_ADMIN_TOKEN}
INFLUXDB_ORG=aleutian-finance
INFLUXDB_BUCKET=financial-data
```

---

## API Contract Updates

### New Unified Predict Endpoint

**Endpoint:** `POST /orchestration/v1/predict`

**Request:**
```json
{
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2026-01-20T14:30:00Z",
  "ticker": "SPY",
  "model": "amazon/chronos-t5-tiny",
  "context": {
    "values": [450.0, 451.2, 449.8, 452.1, 453.5],
    "period": "1d",
    "source": "influxdb",
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

**Response:**
```json
{
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "response_id": "660f9511-f30c-52e5-b827-557766551111",
  "timestamp": "2026-01-20T14:30:02Z",
  "ticker": "SPY",
  "model": "amazon/chronos-t5-tiny",
  "forecast": {
    "values": [454.2, 455.0, 453.8, 456.1, 457.2, 455.9, 458.0, 459.1, 457.8, 460.2],
    "period": "1d",
    "start_date": "2026-01-20",
    "end_date": "2026-02-01"
  },
  "context_summary": {
    "length": 5,
    "period": "1d",
    "source": "influxdb",
    "start_date": "2025-09-01",
    "end_date": "2025-12-30",
    "field": "close"
  },
  "quantiles": [
    {"quantile": 0.1, "values": [452.1, ...]},
    {"quantile": 0.5, "values": [454.2, ...]},
    {"quantile": 0.9, "values": [456.3, ...]}
  ],
  "metadata": {
    "inference_time_ms": 245,
    "model_version": "1.0.0",
    "device": "cpu",
    "model_family": "chronos"
  }
}
```

### Legacy Endpoint (Maintained for Compatibility)

**Endpoint:** `POST /v1/timeseries/forecast`

Still works, internally converts to new format:

**Request:**
```json
{
  "name": "SPY",
  "model": "amazon/chronos-t5-tiny",
  "context_period_size": 252,
  "forecast_period_size": 10
}
```

**Response:**
```json
{
  "name": "SPY",
  "forecast": [454.2, 455.0, 453.8, ...],
  "message": "Success"
}
```

---

## Implementation Checklist

### Phase 1: Infrastructure (Sapheneia)

- [ ] Create `/simulations` directory structure
- [ ] Update `.env` with all port configurations
- [ ] Update `docker-compose.yml` with port variables
- [ ] Add simulation storage volume mounts
- [ ] Test all containers start with new configuration

### Phase 2: API Updates (Sapheneia)

- [ ] Implement `/orchestration/v1/predict` endpoint
- [ ] Add request_id/response_id to all responses
- [ ] Implement simulation storage service
- [ ] Add forecast persistence on inference
- [ ] Update legacy endpoint to use new internal format

### Phase 3: Aleutian Integration

- [ ] Create `datatypes/inference.go` with new types
- [ ] Implement `CallInferenceService` in evaluator
- [ ] Update `RunScenario` to use new API
- [ ] Add `--compute-mode` CLI flag
- [ ] Update environment variable documentation

### Phase 4: Testing

- [ ] Unit tests for new type serialization
- [ ] Integration tests for end-to-end flow
- [ ] Backtest run with simulation storage
- [ ] Verify forecast files created correctly
- [ ] Test with multiple models simultaneously

### Phase 5: Documentation

- [ ] Update RUNBOOK.md with new architecture
- [ ] Update CLI reference documentation
- [ ] Create migration guide for existing users
- [ ] Add troubleshooting section for common issues

---

## Network Diagram

```
┌────────────────────────────────────────────────────────────────────────────┐
│                          aleutian-shared network                           │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  ALEUTIAN CONTAINERS                    SAPHENEIA CONTAINERS               │
│  ─────────────────────                  ────────────────────────           │
│                                                                            │
│  ┌─────────────────────┐               ┌─────────────────────────┐        │
│  │ aleutian-go-        │──────────────▶│ sapheneia-forecast      │        │
│  │ orchestrator        │  /v1/timeseries│ (:8000)                │        │
│  │ (:12210)            │  /orchestration│                        │        │
│  └─────────────────────┘               └──────────┬──────────────┘        │
│                                                   │                        │
│  ┌─────────────────────┐                         │ routes by model        │
│  │ user-influxdb       │◀────────────────────────┼───────────────┐        │
│  │ (:12130)            │                         │               │        │
│  └─────────────────────┘               ┌─────────▼───────────────┴──────┐ │
│                                        │                                │ │
│  ┌─────────────────────┐               │  ┌─────────────────────────┐  │ │
│  │ aleutian-data-      │               │  │ forecast-chronos-t5-*   │  │ │
│  │ fetcher (:12001)    │               │  │ (:12710-12714)          │  │ │
│  └─────────────────────┘               │  └─────────────────────────┘  │ │
│                                        │                                │ │
│  ┌─────────────────────┐               │  ┌─────────────────────────┐  │ │
│  │ aleutian-otel-      │               │  │ forecast-chronos-bolt-* │  │ │
│  │ collector           │               │  │ (:12715-12717)          │  │ │
│  └─────────────────────┘               │  └─────────────────────────┘  │ │
│                                        │                                │ │
│  ┌─────────────────────┐               │  ┌─────────────────────────┐  │ │
│  │ aleutian-jaeger     │               │  │ sapheneia-trading       │  │ │
│  │ (:16686)            │               │  │ (:12132)                │  │ │
│  └─────────────────────┘               │  └─────────────────────────┘  │ │
│                                        │                                │ │
│  ┌─────────────────────┐               │  ┌─────────────────────────┐  │ │
│  │ aleutian-prometheus │               │  │ sapheneia-data          │  │ │
│  │ (:9090)             │               │  │ (:12701)                │  │ │
│  └─────────────────────┘               │  └─────────────────────────┘  │ │
│                                        │                                │ │
│  ┌─────────────────────┐               │  ┌─────────────────────────┐  │ │
│  │ aleutian-grafana    │               │  │ sapheneia-ui            │  │ │
│  │ (:3000)             │               │  │ (:12780)                │  │ │
│  └─────────────────────┘               └──┴─────────────────────────┴──┘ │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## Appendix: Quick Reference

### Start Minimal System

```bash
# Terminal 1: Start Aleutian stack
cd /Users/jin/GolandProjects/AleutianFOSS
./aleutian stack start --profile timeseries

# Terminal 2: Start Sapheneia forecast model
cd /Users/jin/PycharmProjects/sapheneia
podman-compose up -d forecast-chronos-t5-tiny

# Test
./aleutian timeseries forecast SPY --model "amazon/chronos-t5-tiny" --context 90 --horizon 10
```

### Port Summary

| Service | Port | Network Name |
|---------|------|--------------|
| Aleutian Orchestrator | 12210 | aleutian-go-orchestrator |
| InfluxDB | 12130 | user-influxdb |
| Data Fetcher | 12001 | aleutian-data-fetcher |
| Sapheneia Gateway | 12700 | sapheneia-forecast |
| Sapheneia Data | 12701 | sapheneia-data |
| Sapheneia Metrics | 12702 | sapheneia-metrics |
| Chronos T5 (tiny→large) | 12710-12714 | forecast-chronos-t5-* |
| Chronos Bolt (mini→base) | 12715-12717 | forecast-chronos-bolt-* |
| TimesFM 2.0/2.5 | 12720-12721 | forecast-timesfm-* |
| Trading API | 12132 | sapheneia-trading |
| UI | 12780 | sapheneia-ui |
