# Sapheneia Backtest Strategies

This directory contains YAML-based strategy configurations for evaluating time-series forecasting models across various financial instruments.

## Quick Start

```bash
# Set environment variables (add to ~/.bashrc for persistence)
export ORCHESTRATOR_URL=http://localhost:12700
export SAPHENEIA_API_KEY=default_trading_api_key_please_change
```

### Step 1: Run a Backtest

```bash
aleutian evaluate run --config simulations/strategies/SPY/spy_chronos_tiny.yaml --api-version unified
```

**Output:**
```
Starting Evaluation Run: spy-chronos-tiny_v1.0.0_20260121_153042
   Strategy:       spy-chronos-tiny (v1.0.0)
   Model:          amazon/chronos-t5-tiny
   Ticker:         SPY
   ...

✅ Evaluation completed successfully.
   Run ID: spy-chronos-tiny_v1.0.0_20260121_153042
```

### Step 2: Export Results to CSV

Copy the **Run ID** from the output and use it to export:

```bash
aleutian evaluate export spy-chronos-tiny_v1.0.0_20260121_153042
```

**Output:**
```
Exporting results for Run ID: spy-chronos-tiny_v1.0.0_20260121_153042
✅ Export complete: 250 rows written to backtest_spy-chronos-tiny_v1.0.0_20260121_153042.csv
```

### Step 3: View Results

```bash
# Preview the CSV
head backtest_spy-chronos-tiny_v1.0.0_20260121_153042.csv

# Or open in a spreadsheet application
```

**CSV Columns:**
| Column | Description |
|--------|-------------|
| Time | Timestamp of the trading day |
| Ticker | Stock symbol (SPY, QQQ, etc.) |
| Model | Forecast model used |
| Action | hold, buy, or sell |
| Price | Current price |
| Forecast | Model's predicted price |
| Shares_Traded | Number of shares traded |
| Position_Size | Current position |
| Cash | Available cash |
| Portfolio_Value | Total portfolio value |
| Reason | Why the action was taken |

## Directory Structure

```
strategies/
├── README.md           # This file
├── SPY/                # S&P 500 ETF strategies
│   ├── spy_chronos_tiny.yaml
│   ├── spy_chronos_base.yaml
│   ├── spy_chronos_bolt.yaml
│   └── spy_timesfm.yaml
├── QQQ/                # Nasdaq 100 strategies
├── ...                 # Other tickers (26 total)
```

---

## Available Models

| Model | ID | Speed | Accuracy | GPU Memory |
|-------|-----|-------|----------|------------|
| **Chronos T5-Tiny** | `amazon/chronos-t5-tiny` | ⚡⚡⚡ Fastest | Good | ~1GB |
| **Chronos T5-Base** | `amazon/chronos-t5-base` | ⚡⚡ Fast | Better | ~2GB |
| **Chronos Bolt-Mini** | `amazon/chronos-bolt-mini` | ⚡⚡⚡ Fast | Better | ~1GB |
| **TimesFM 2.0** | `google/timesfm-2.0-500m-pytorch` | ⚡ Slower | Best | ~4GB |

---

## Tickers by Category

### Index ETFs
| Ticker | Description | Strategies |
|--------|-------------|------------|
| SPY | SPDR S&P 500 | `SPY/spy_*.yaml` |
| QQQ | Invesco QQQ Trust (Nasdaq 100) | `QQQ/qqq_*.yaml` |
| IWM | iShares Russell 2000 | `IWM/iwm_*.yaml` |
| VTI | Vanguard Total Stock Market | `VTI/vti_*.yaml` |
| RSP | Invesco S&P 500 Equal Weight | `RSP/rsp_*.yaml` |
| EEM | MSCI Emerging Markets | `EEM/eem_*.yaml` |

### Sector ETFs (SPDR Select Sector)
| Ticker | Sector | Strategies |
|--------|--------|------------|
| XLK | Technology | `XLK/xlk_*.yaml` |
| XLF | Financials | `XLF/xlf_*.yaml` |
| XLV | Health Care | `XLV/xlv_*.yaml` |
| XLE | Energy | `XLE/xle_*.yaml` |
| XLI | Industrials | `XLI/xli_*.yaml` |
| XLY | Consumer Discretionary | `XLY/xly_*.yaml` |
| XLP | Consumer Staples | `XLP/xlp_*.yaml` |
| XLC | Communication Services | `XLC/xlc_*.yaml` |
| XLB | Materials | `XLB/xlb_*.yaml` |
| XLU | Utilities | `XLU/xlu_*.yaml` |
| XLRE | Real Estate | `XLRE/xlre_*.yaml` |

### Commodities
| Ticker | Description | Strategies |
|--------|-------------|------------|
| GLD | SPDR Gold Trust | `GLD/gld_*.yaml` |
| SLV | iShares Silver Trust | `SLV/slv_*.yaml` |
| USO | United States Oil Fund | `USO/uso_*.yaml` |

### Bonds
| Ticker | Description | Strategies |
|--------|-------------|------------|
| TLT | iShares 20+ Year Treasury Bond | `TLT/tlt_*.yaml` |
| BND | Vanguard Total Bond Market | `BND/bnd_*.yaml` |
| FBND | Fidelity Total Bond | `FBND/fbnd_*.yaml` |
| IUSB | iShares Core Total USD Bond | `IUSB/iusb_*.yaml` |

### Cryptocurrency
| Ticker | Description | Strategies |
|--------|-------------|------------|
| BTCUSDT | Bitcoin (USDT pair) | `BTCUSDT/btcusdt_*.yaml` |
| ETHUSD | Ethereum (USD pair) | `ETHUSD/ethusd_*.yaml` |

---

## Running Backtests

### Single Strategy (Manual Export)

```bash
# 1. Run the backtest
aleutian evaluate run \
  --config simulations/strategies/SPY/spy_chronos_tiny.yaml \
  --api-version unified

# 2. Copy the Run ID from output, then export
aleutian evaluate export spy-chronos-tiny_v1.0.0_20260121_153042
```

### Single Strategy (Automatic Export)

Capture the Run ID and export in one go:

```bash
# Run and capture the Run ID
RUN_ID=$(aleutian evaluate run \
  --config simulations/strategies/SPY/spy_chronos_tiny.yaml \
  --api-version unified 2>&1 | grep "Run ID:" | awk '{print $NF}')

# Export to CSV
aleutian evaluate export "$RUN_ID"

echo "Results saved to: backtest_${RUN_ID}.csv"
```

### Batch Run: All Models for One Ticker

Run all 4 models for SPY and export each:

```bash
for strategy in simulations/strategies/SPY/*.yaml; do
  echo "========================================"
  echo "Running: $strategy"
  echo "========================================"

  # Run and capture Run ID
  RUN_ID=$(aleutian evaluate run --config "$strategy" --api-version unified 2>&1 \
    | grep "Run ID:" | awk '{print $NF}')

  # Export results
  if [[ -n "$RUN_ID" ]]; then
    aleutian evaluate export "$RUN_ID"
    echo "Exported: backtest_${RUN_ID}.csv"
  fi

  echo ""
done
```

### Batch Run: One Model Across All Tickers

Run Chronos Tiny on all 26 tickers:

```bash
for ticker_dir in simulations/strategies/*/; do
  ticker=$(basename "$ticker_dir")
  strategy="${ticker_dir}${ticker,,}_chronos_tiny.yaml"

  if [[ -f "$strategy" ]]; then
    echo "Running: $ticker"

    RUN_ID=$(aleutian evaluate run --config "$strategy" --api-version unified 2>&1 \
      | grep "Run ID:" | awk '{print $NF}')

    if [[ -n "$RUN_ID" ]]; then
      aleutian evaluate export "$RUN_ID"
    fi
  fi
done

echo "All exports complete!"
ls -la backtest_*.csv
```

### Full Comparison: All Models × All Tickers

Run every combination (104 backtests) and export all:

```bash
mkdir -p results/$(date +%Y%m%d)

for strategy in simulations/strategies/*/*.yaml; do
  echo "Running: $strategy"

  RUN_ID=$(aleutian evaluate run --config "$strategy" --api-version unified 2>&1 \
    | grep "Run ID:" | awk '{print $NF}')

  if [[ -n "$RUN_ID" ]]; then
    aleutian evaluate export "$RUN_ID"
    mv "backtest_${RUN_ID}.csv" "results/$(date +%Y%m%d)/"
  fi
done

echo "All results saved to results/$(date +%Y%m%d)/"
```

---

## Via Sapheneia API

Strategies can also be served via the orchestration API:

```bash
# List all strategies
curl http://localhost:12210/orchestration/v1/strategies

# Get a specific strategy (returns JSON)
curl http://localhost:12210/orchestration/v1/strategies/spy_chronos_tiny

# Load remote strategy directly with Aleutian
aleutian evaluate run \
  --config http://localhost:12210/orchestration/v1/strategies/spy_chronos_tiny \
  --api-version unified
```

---

## Strategy Schema

Each strategy YAML file follows this structure:

```yaml
metadata:
  id: "spy-chronos-tiny"           # Unique identifier
  version: "1.0.0"                  # Strategy version
  description: "..."                # Human-readable description
  author: "Sapheneia"

evaluation:
  ticker: "SPY"                     # Financial instrument
  fetch_start_date: "20211201"      # Data to fetch (for context)
  start_date: "20230101"            # Backtest start
  end_date: "20240101"              # Backtest end

forecast:
  model: "amazon/chronos-t5-tiny"   # Model to use
  context_size: 252                 # Trading days of history (1 year)
  horizon_size: 20                  # Forecast days ahead

trading:
  initial_capital: 100000.0         # Starting capital ($)
  initial_position: 0.0             # Starting shares
  initial_cash: 100000.0            # Starting cash
  strategy_type: "threshold"        # Trading strategy type
  params:
    threshold_type: "absolute"      # Signal threshold type
    threshold_value: 2.0            # Minimum signal to trade
    execution_size: 10.0            # Position size (shares)
```

---

## Exporting Results

### Basic Export

```bash
# Export a specific run to CSV
aleutian evaluate export spy-chronos-tiny_v1.0.0_20260121_153042

# Output file: backtest_spy-chronos-tiny_v1.0.0_20260121_153042.csv
```

### Understanding Run IDs

Run IDs are generated automatically with this format:
```
{strategy-id}_{version}_{date}_{time}
```

Example: `spy-chronos-tiny_v1.0.0_20260121_153042`
- **Strategy:** spy-chronos-tiny
- **Version:** v1.0.0
- **Date:** 2026-01-21
- **Time:** 15:30:42

### CSV Output Format

| Column | Example | Description |
|--------|---------|-------------|
| Time | 2023-01-03T14:30:00Z | Trading timestamp |
| Ticker | SPY | Symbol |
| Model | amazon/chronos-t5-tiny | Forecast model |
| Action | hold / buy / sell | Trading decision |
| Price | 380.82 | Current price |
| Forecast | 381.76 | Predicted price |
| Shares_Traded | 0.00 | Shares bought/sold |
| Position_Size | 0.00 | Current holdings |
| Cash | 100000.00 | Available cash |
| Portfolio_Value | 100000.00 | Total value |
| Reason | Signal 0.94 below threshold 2.00 | Decision explanation |

### Analyzing Results

```bash
# View first 10 rows
head backtest_spy-chronos-tiny_v1.0.0_20260121_153042.csv

# Count trades
grep -c ",buy,\|,sell," backtest_spy-chronos-tiny_v1.0.0_20260121_153042.csv

# See final portfolio value (last row)
tail -1 backtest_spy-chronos-tiny_v1.0.0_20260121_153042.csv

# Import to Python for analysis
python3 << 'EOF'
import pandas as pd
df = pd.read_csv('backtest_spy-chronos-tiny_v1.0.0_20260121_153042.csv')
print(f"Total days: {len(df)}")
print(f"Final value: ${df['Portfolio_Value'].iloc[-1]:,.2f}")
print(f"Return: {(df['Portfolio_Value'].iloc[-1] / 100000 - 1) * 100:.2f}%")
EOF
```

---

## Required Services

| Service | Port | Health Check |
|---------|------|--------------|
| Sapheneia Orchestration | 12700 | `curl http://localhost:12700/health` |
| Chronos Forecast | 12710 | `curl http://localhost:12710/health` |
| InfluxDB | 12130 | `curl http://localhost:12130/health` |

### Initialize Model Before First Use

```bash
curl -X POST http://localhost:12710/forecast/v1/chronos/initialization \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer default_trading_api_key_please_change" \
  -d '{}'
```

---

## Troubleshooting

| Error | Solution |
|-------|----------|
| "Model is not initialized" | Run the initialization curl above |
| "No data available" | `aleutian timeseries fetch <TICKER> --days 730` |
| Connection refused | Check services: `podman ps` |

---

## Adding New Strategies

1. Create a directory for the ticker: `mkdir -p simulations/strategies/AAPL`
2. Copy an existing strategy: `cp SPY/spy_chronos_tiny.yaml AAPL/aapl_chronos_tiny.yaml`
3. Edit the file to change ticker and description
4. Run: `aleutian evaluate run --config simulations/strategies/AAPL/aapl_chronos_tiny.yaml --api-version unified`
