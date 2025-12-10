# Trading Strategies Guide

Complete guide to the three trading strategy types supported by the Trading Strategies API.

## Table of Contents

1. [Strategy Overview](#strategy-overview)
2. [Threshold Strategy](#threshold-strategy)
3. [Return Strategy](#return-strategy)
4. [Quantile Strategy](#quantile-strategy)
5. [Strategy Selection Guide](#strategy-selection-guide)
6. [Best Practices](#best-practices)

## Strategy Overview

The Trading Strategies API supports three distinct strategy types, each designed for different market conditions and use cases:

1. **Threshold Strategy**: Price difference-based with configurable thresholds
2. **Return Strategy**: Expected return-based with position sizing
3. **Quantile Strategy**: Empirical quantile-based using historical distribution

All strategies are:
- **Stateless**: All state (position, capital) provided in each request
- **Long-only**: No short selling allowed
- **Capital-aware**: Automatically handles insufficient capital scenarios

## Threshold Strategy

### Description

The threshold strategy compares the forecast price to the current price and generates buy/sell signals when the price difference exceeds a configurable threshold.

**Use Cases:**
- Simple price-based trading signals
- Trend-following strategies
- Mean reversion strategies (with appropriate thresholds)

### Threshold Types

#### 1. Absolute Threshold

Uses an absolute price difference threshold.

**Example:**
- Current price: $100
- Forecast price: $105
- Threshold: $2.0
- Signal: **BUY** (difference $5 > threshold $2)

```json
{
  "threshold_type": "absolute",
  "threshold_value": 2.0
}
```

#### 2. Percentage Threshold

Uses a percentage-based threshold relative to current price.

**Example:**
- Current price: $100
- Forecast price: $108
- Threshold: 5% (0.05)
- Signal: **BUY** (8% difference > 5% threshold)

```json
{
  "threshold_type": "percentage",
  "threshold_value": 0.05
}
```

#### 3. Standard Deviation Threshold

Uses historical price volatility (standard deviation) to set dynamic thresholds.

**Requirements:**
- History data (close_history recommended)
- Minimum 2 periods of history

**Example:**
- Current price: $100
- Forecast price: $105
- Historical std_dev: $3.0
- Threshold multiplier: 1.5
- Effective threshold: $4.5
- Signal: **BUY** (difference $5 > threshold $4.5)

```json
{
  "threshold_type": "std_dev",
  "threshold_value": 1.5,
  "close_history": [100.0, 101.0, 99.0, 102.0, ...]
}
```

**Fallback:** If insufficient history, falls back to absolute threshold.

#### 4. ATR (Average True Range) Threshold

Uses Average True Range from OHLC data to set volatility-based thresholds.

**Requirements:**
- All OHLC histories (open, high, low, close)
- Minimum 2 periods of history

**Example:**
- Current price: $100
- Forecast price: $105
- ATR: $4.0
- Threshold multiplier: 1.2
- Effective threshold: $4.8
- Signal: **BUY** (difference $5 > threshold $4.8)

```json
{
  "threshold_type": "atr",
  "threshold_value": 1.2,
  "open_history": [100.0, 101.0, ...],
  "high_history": [105.0, 106.0, ...],
  "low_history": [95.0, 96.0, ...],
  "close_history": [100.0, 101.0, ...]
}
```

**Fallback:** If insufficient OHLC data, falls back to absolute threshold.

### Parameters

**Required:**
- `threshold_type`: `"absolute"`, `"percentage"`, `"std_dev"`, or `"atr"`
- `execution_size`: Position size to trade (shares/units)

**Optional:**
- `threshold_value`: Threshold value or multiplier (default: 0.0)
- `which_history`: History type for std_dev (`"open"`, `"high"`, `"low"`, `"close"`, default: `"close"`)
- `window_history`: Number of periods to use (default: 20, max: 10,000)
- `min_history_length`: Minimum history required (default: 2)
- OHLC histories: Required for ATR, optional for std_dev

### Signal Logic

- **BUY**: `forecast_price > current_price + threshold`
- **SELL**: `forecast_price < current_price - threshold`
- **HOLD**: Price difference within threshold

## Return Strategy

### Description

The return strategy uses expected return (forecast vs current price) to generate signals with configurable position sizing.

**Use Cases:**
- Return-based trading strategies
- Risk-adjusted position sizing
- Portfolio optimization

### Position Sizing Methods

#### 1. Fixed Position Sizing

Uses a fixed position size regardless of return magnitude.

```json
{
  "position_sizing": "fixed",
  "execution_size": 100.0
}
```

#### 2. Proportional Position Sizing

Position size scales with expected return magnitude.

**Example:**
- Expected return: 8%
- Execution size base: 100 shares
- Actual size: 100 * (8% / threshold) = 160 shares (if threshold is 5%)

```json
{
  "position_sizing": "proportional",
  "execution_size": 100.0,
  "threshold_value": 0.05
}
```

#### 3. Normalized Position Sizing

Position size normalized by historical return volatility.

**Requirements:**
- History data (close_history recommended)
- Minimum 2 periods of history

**Example:**
- Expected return: 8%
- Historical return volatility: 2%
- Normalized return: 8% / 2% = 4x
- Position size scales with normalized return

```json
{
  "position_sizing": "normalized",
  "execution_size": 100.0,
  "which_history": "close",
  "window_history": 20,
  "close_history": [100.0, 101.0, 99.0, ...]
}
```

**Fallback:** If insufficient history, falls back to proportional sizing.

### Parameters

**Required:**
- `position_sizing`: `"fixed"`, `"proportional"`, or `"normalized"`
- `threshold_value`: Return threshold (must be > 0)
- `execution_size`: Base position size

**Optional:**
- `max_position_size`: Maximum position size constraint
- `min_position_size`: Minimum position size constraint
- `which_history`: History type for normalized sizing
- `window_history`: Number of periods to use (default: 20, max: 10,000)
- `min_history_length`: Minimum history required
- OHLC histories: Required for normalized sizing

**Note:** Large `window_history` values (>1000) may impact performance. The maximum allowed value is 10,000 to prevent performance degradation.

### Signal Logic

- **BUY**: `expected_return > threshold_value`
- **SELL**: `expected_return < -threshold_value`
- **HOLD**: Return within threshold range

## Quantile Strategy

### Description

The quantile strategy uses empirical quantiles from historical price distribution to generate signals based on where the forecast price falls in the historical distribution.

**Use Cases:**
- Mean reversion strategies
- Statistical arbitrage
- Distribution-based trading

### How It Works

1. Calculate the percentile of the forecast price within historical distribution
2. Match percentile to configured quantile signal ranges
3. Generate signal (buy/sell/hold) based on matched range
4. Apply multiplier to position size

### Quantile Signal Configuration

Quantile signals are configured as ranges (0-100 percentile) with associated actions:

```json
{
  "quantile_signals": {
    "1": {
      "range": [0, 20],
      "signal": "buy",
      "multiplier": 1.0
    },
    "2": {
      "range": [80, 100],
      "signal": "sell",
      "multiplier": 1.0
    }
  }
}
```

**Example:**
- Historical prices: [90, 95, 100, 105, 110]
- Forecast price: 92
- Percentile: 20th percentile (falls in [0, 20] range)
- Signal: **BUY** with multiplier 1.0

### Parameters

**Required:**
- `which_history`: OHLC history type (`"open"`, `"high"`, `"low"`, `"close"`)
- `window_history`: Number of periods to use (max: 10,000)
- `quantile_signals`: Dictionary of quantile signal configurations
- All OHLC histories: `open_history`, `high_history`, `low_history`, `close_history`

**Note:** Large `window_history` values (>1000) may impact performance. The maximum allowed value is 10,000 to prevent performance degradation.

**Optional:**
- `position_sizing`: `"fixed"` or `"normalized"` (default: `"fixed"`)
- `execution_size`: Base position size
- `max_position_size`: Maximum position size constraint
- `min_position_size`: Minimum position size constraint
- `min_history_length`: Minimum history required (default: 2)

### Signal Logic

- Percentile calculated from historical distribution
- First matching quantile signal range determines action
- Position size = `execution_size * multiplier`
- If no range matches, action is **HOLD**

### Quantile Signal Range Rules

- Ranges must be 0-100 percentile
- Range min < range max
- **Ranges must not overlap** - Each percentile value should map to exactly one signal configuration
- Multiplier typically 0.0-1.0 (can be > 1.0 for leverage)

**Note**: Overlapping ranges are not allowed. If ranges overlap, the API will return a validation error (422). This ensures predictable behavior and prevents ambiguous signal generation.

## Strategy Selection Guide

### When to Use Threshold Strategy

✅ **Use when:**
- Simple price-based signals needed
- Clear price targets or thresholds
- Trend-following or mean reversion
- Minimal historical data available

❌ **Avoid when:**
- Need risk-adjusted position sizing
- Complex return-based logic required
- Statistical distribution analysis needed

### When to Use Return Strategy

✅ **Use when:**
- Return-based trading logic
- Risk-adjusted position sizing needed
- Portfolio optimization
- Return thresholds are meaningful

❌ **Avoid when:**
- Simple price difference signals sufficient
- Distribution-based signals needed
- Minimal return calculation requirements

### When to Use Quantile Strategy

✅ **Use when:**
- Statistical distribution analysis
- Mean reversion strategies
- Historical percentile-based signals
- Complex quantile-based logic

❌ **Avoid when:**
- Simple price or return signals sufficient
- Insufficient historical data
- Real-time distribution calculation not feasible

## Best Practices

### 1. Threshold Selection

- **Absolute**: Use for fixed price targets
- **Percentage**: Use for relative price movements
- **Std_dev/ATR**: Use for volatility-adjusted thresholds

### 2. Position Sizing

- **Fixed**: Simple, predictable
- **Proportional**: Scales with opportunity
- **Normalized**: Risk-adjusted, requires history

### 3. History Requirements

- Provide sufficient history for std_dev/ATR/normalized sizing
- Minimum 20 periods recommended for stable calculations
- Use `close_history` for most cases (most commonly available)

### 4. Capital Management

- Monitor `available_cash` and `stopped` flags
- Handle `InsufficientCapitalError` gracefully
- Implement position size constraints (`max_position_size`, `min_position_size`)

### 5. Error Handling

- Validate all required parameters
- Handle missing history data gracefully (fallbacks provided)
- Check `stopped` flag before executing trades

### 6. Testing

- Test with various market conditions
- Validate edge cases (insufficient capital, no position, etc.)
- Verify threshold calculations match expectations

## Additional Resources

- **API Usage Guide**: [API_USAGE.md](API_USAGE.md)
- **Quick Reference**: [QUICK_REFERENCE.md](QUICK_REFERENCE.md)
- **Examples**: [EXAMPLES.md](EXAMPLES.md)

