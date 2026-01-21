# Sapheneia Strategy Definitions

This folder contains YAML-based strategy configuration files for backtesting
with the Aleutian evaluation framework.

## Available Strategies

| Strategy | Ticker | Model | Type |
|----------|--------|-------|------|
| `spy_threshold_v1` | SPY | chronos-t5-tiny | Threshold |
| `qqq_momentum_v1` | QQQ | timesfm-2.0-500m | Momentum |

## Usage

### Via Sapheneia API

Strategies are served via the orchestration API:

```bash
# List all strategies
curl http://localhost:12210/orchestration/v1/strategies

# Get a specific strategy
curl http://localhost:12210/orchestration/v1/strategies/spy_threshold_v1
```

### Via Aleutian CLI

Load a remote strategy directly:

```bash
aleutian eval --config http://localhost:12210/orchestration/v1/strategies/spy_threshold_v1
```

Or load a local strategy:

```bash
aleutian eval --config strategies/spy_threshold_v1.yaml
```

## Strategy Schema

Each strategy YAML must follow this schema:

```yaml
metadata:
  id: string          # Unique identifier (used in URL)
  version: string     # Semantic version
  description: string # Human-readable description
  author: string      # Creator
  created: string     # Creation date (YYYY-MM-DD)

evaluation:
  ticker: string           # Symbol to evaluate (SPY, QQQ, etc.)
  fetch_start_date: string # Start date for data fetch (YYYYMMDD)
  start_date: string       # Evaluation start date (YYYYMMDD)
  end_date: string         # Evaluation end date (YYYYMMDD)

forecast:
  model: string        # Model identifier (vendor/model-name)
  context_size: int    # Number of historical points for context
  horizon_size: int    # Number of points to forecast
  compute_mode: string # "legacy" or "unified"

trading:
  initial_capital: float   # Starting portfolio value
  initial_position: float  # Starting position (shares)
  initial_cash: float      # Starting cash
  strategy_type: string    # Strategy type (threshold, momentum, etc.)
  params: object           # Strategy-specific parameters
```

## Adding New Strategies

1. Create a new YAML file following the schema above
2. Use a descriptive filename: `{ticker}_{strategy_type}_v{version}.yaml`
3. The `metadata.id` will be used as the URL path segment

## Strategy Types

### Threshold
- `threshold_type`: "absolute" or "percentage"
- `threshold_value`: Numeric threshold for buy/sell signals
- `execution_size`: Fraction of available capital to trade

### Momentum
- `lookback_period`: Number of periods for momentum calculation
- `momentum_threshold`: Threshold for triggering trades
- `execution_size`: Fraction of available capital to trade
