# Trading Strategy Evaluation Guide

## Overview

The Aleutian evaluation framework allows you to backtest trading strategies using historical data and forecasting models. It integrates with the Sapheneia trading API to execute strategy logic and stores results in InfluxDB for analysis.

## Quick Start

### 1. Prerequisites

- **Sapheneia Services Running**: Ensure the following Sapheneia containers are running:
  - `sapheneia-trading` (port 12132)
  - `sapheneia-data` (port 8001)
  - `user-influxdb` (port 12130)

- **Environment Variables**: Set the Sapheneia trading API key:
  ```bash
  export SAPHENEIA_TRADING_API_KEY=dev_trading_api_key_12345678901234567890

2. Fetch Historical Data

Before running an evaluation, fetch historical data for your ticker:

./aleutian timeseries fetch SPY --days 1800

This fetches approximately 1800 days (~7 years) of historical OHLC data.

3. Create a Strategy Configuration

Create a YAML file in strategies/ directory. Example strategies/spy_threshold_v1.yaml:

metadata:
  id: "spy-threshold-demo"
  version: "1.0.0"
  description: "Basic threshold strategy testing SPY 2023 performance"
  author: "Your Name"

evaluation:
  ticker: "SPY"
  fetch_start_date: "20220101"  # Start fetching data from this date
  start_date: "20230101"        # Start evaluation from this date
  end_date: "20240101"          # End evaluation at this date

forecast:
  model: "google/timesfm-2.0-500m-pytorch"
  context_size: 252  # Days of historical context (1 trading year)
  horizon_size: 20   # Forecast horizon in days

trading:
  initial_capital: 100000.0
  initial_position: 0.0
  initial_cash: 100000.0
  strategy_type: "threshold"
  params:
    threshold_type: "absolute"
    threshold_value: 2.0
    execution_size: 10.0

4. Run the Evaluation

./aleutian evaluate run --ticker SPY --config strategies/spy_threshold_v1.yaml

5. Analyze Results

Results are stored in InfluxDB under the forecast_evaluations measurement.

Use the Sapheneia inspection script:

cd /Users/jin/PycharmProjects/sapheneia
python tests/manual/inspect_influxdb_results.py

This generates a CSV file with all backtest results.

Configuration Reference

Metadata Section

- id: Unique identifier for the strategy
- version: Strategy version (semver format)
- description: Human-readable description
- author: Strategy author name

Evaluation Section

- ticker: Stock ticker symbol (e.g., "SPY", "QQQ", "AAPL")
- fetch_start_date: Date to start fetching historical data (YYYYMMDD or YYYY-MM-DD)
- start_date: Date to start the backtest evaluation
- end_date: Date to end the backtest evaluation

Important: fetch_start_date should be earlier than start_date by at least context_size trading days to provide sufficient historical context.

Forecast Section

- model: Forecasting model identifier (e.g., "google/timesfm-2.0-500m-pytorch")
- context_size: Number of historical days used for forecasting
- horizon_size: Number of days to forecast ahead

Trading Section

- initial_capital: Starting capital for the backtest
- initial_position: Initial position size (0 for no position)
- initial_cash: Available cash at start (typically equals initial_capital)
- strategy_type: Strategy type ("threshold", "return", "quantile")
- params: Strategy-specific parameters

Threshold Strategy Parameters

- threshold_type: "absolute" or "percent"
- threshold_value: Minimum forecast magnitude to trigger action
- execution_size: Position size per trade

Strategy Types

1. Threshold Strategy

Buys when the forecast price exceeds the current price by a threshold amount.

strategy_type: "threshold"
params:
  threshold_type: "absolute"  # or "percent"
  threshold_value: 2.0        # $2 for absolute, 0.02 for 2% percent
  execution_size: 10.0        # Buy/sell 10 shares per signal

2. Return Strategy

(Coming soon)

3. Quantile Strategy

(Coming soon)

Troubleshooting

Connection Refused Errors

If you see connection refused errors:

1. Check that Sapheneia services are running:
cd /Users/jin/PycharmProjects/sapheneia
podman-compose ps
2. Verify port mappings in docker-compose.yml:
  - Trading: 12132:9000
  - Data: 8001:8000
  - InfluxDB: 12130:8086

Rate Limit Exceeded

If you hit rate limits, increase or disable them in Sapheneia's .env:

RATE_LIMIT_ENABLED=false
# or
RATE_LIMIT_EXECUTE_PER_MINUTE=1000

Then restart the trading service:

cd /Users/jin/PycharmProjects/sapheneia
podman-compose restart trading

No Historical Data Found

Ensure you've fetched data covering the entire evaluation range:

# Fetch data from earlier than fetch_start_date
./aleutian timeseries fetch SPY --days 2000

Date Parsing Errors

The system supports both date formats:
- YYYYMMDD: "20230101"
- YYYY-MM-DD: "2023-01-01"

Use either format consistently in your configuration.

Advanced Usage

Custom Run IDs

Run IDs are automatically generated as: {strategy_id}_v{version}_{timestamp}

Example: spy-threshold-demo_v1.0.0_20251219_222820

Querying Results

Connect to InfluxDB to query results:

influx -host localhost -port 12130 -org aleutian-finance -token your_super_secret_admin_token

# Query recent evaluations
from(bucket: "financial-data")
  |> range(start: -30d)
  |> filter(fn: (r) => r._measurement == "forecast_evaluations")
  |> filter(fn: (r) => r.run_id == "spy-threshold-demo_v1.0.0_20251219_222820")

Multiple Ticker Backtests

Run evaluations for multiple tickers sequentially:

for ticker in SPY QQQ IWM; do
  ./aleutian evaluate run --ticker $ticker --config strategies/${ticker,,}_threshold_v1.yaml
done

Integration with Sapheneia

The evaluation framework integrates with three Sapheneia services:

1. Data Service (sapheneia-data): Fetches historical data from Yahoo Finance
2. Trading Service (sapheneia-trading): Executes trading strategy logic
3. InfluxDB: Stores time-series data and evaluation results

Architecture

AleutianLocal (Go)
    │
    ├─> Data Fetcher ──> Yahoo Finance ──> InfluxDB
    │
    └─> Evaluator ──> InfluxDB (read) ──> Trading Service ──> Results ──> InfluxDB (write)

Contributing

To add new strategy types:

1. Implement the strategy in Sapheneia's trading/ directory
2. Add the strategy type to the validation in datatypes/trading.go
3. Update this documentation with parameters and examples

License

See LICENSE file in the project root.

---

Would you like me to:
1. Create additional test files for specific components?
2. Add more detailed examples to the documentation?
3. Create a separate quick-start guide?