"""MCP test fixtures."""

from __future__ import annotations

import pytest


COMBINATIONS_YAML = """\
metadata:
  experiment_id: "exp-test"
  description: "test grid"
  author: "ci"

matrix:
  ticker:           [SPY, QQQ]
  model:            [amazon/chronos-t5-tiny, google/timesfm-2.0-500m-pytorch]
  trading_horizon:  [1, 5]
  context_size:     [126, 252]
  strategy_type:    [threshold, quantile]

common:
  fetch_start_date: "20211201"
  start_date:       "20230101"
  end_date:         "20240101"
  forecast_horizon: 20
  initial_capital:  100000.0
  initial_position: 0.0

strategy_params:
  threshold:
    threshold_type:  percentage
    threshold_value: 1.5
    execution_size:  10.0
  quantile:
    quantile_signals:
      - { range: [0,   25],  signal: BUY,  multiplier: 1.5 }
      - { range: [75, 100],  signal: SELL, multiplier: 1.5 }

metrics: [sharpe, max_drawdown]

cache:
  enabled: true
  scope:   experiment
  what:    [forecasts]

parallelism:
  max_concurrent_runs: 4
  max_per_model:       2
"""


@pytest.fixture
def combinations_yaml() -> str:
    return COMBINATIONS_YAML
