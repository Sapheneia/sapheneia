# Trading Strategies API - Quick Reference

Quick reference card for the Trading Strategies API.

## Common Commands

```bash
# Initialize
./setup.sh init trading

# Run (venv)
./setup.sh run-venv trading

# Run (Docker)
./setup.sh run-docker trading

# Stop
./setup.sh stop trading
```

## Endpoint URLs

| Endpoint | Method | Auth | Rate Limit |
|----------|--------|------|------------|
| `/trading/execute` | POST | ✅ | 10/min |
| `/trading/strategies` | GET | ❌ | 30/min |
| `/trading/status` | GET | ❌ | 30/min |
| `/health` | GET | ❌ | 30/min |
| `/` | GET | ❌ | 30/min |

**Base URL**: `http://localhost:9000`

## Request Templates

### Threshold Strategy (Absolute)

```json
{
  "strategy_type": "threshold",
  "forecast_price": 105.0,
  "current_price": 100.0,
  "current_position": 0.0,
  "available_cash": 100000.0,
  "initial_capital": 100000.0,
  "threshold_type": "absolute",
  "threshold_value": 2.0,
  "execution_size": 100.0
}
```

### Return Strategy (Fixed)

```json
{
  "strategy_type": "return",
  "forecast_price": 108.0,
  "current_price": 100.0,
  "current_position": 0.0,
  "available_cash": 100000.0,
  "initial_capital": 100000.0,
  "position_sizing": "fixed",
  "threshold_value": 0.05,
  "execution_size": 10.0
}
```

### Quantile Strategy

```json
{
  "strategy_type": "quantile",
  "forecast_price": 92.0,
  "current_price": 100.0,
  "current_position": 0.0,
  "available_cash": 100000.0,
  "initial_capital": 100000.0,
  "which_history": "close",
  "window_history": 20,
  "quantile_signals": {
    "1": {"range": [0, 20], "signal": "buy", "multiplier": 1.0},
    "2": {"range": [80, 100], "signal": "sell", "multiplier": 1.0}
  },
  "position_sizing": "fixed",
  "execution_size": 10.0,
  "open_history": [...],
  "high_history": [...],
  "low_history": [...],
  "close_history": [...]
}
```

## Response Schema

```json
{
  "action": "buy|sell|hold",
  "size": 0.0,
  "value": 0.0,
  "reason": "string",
  "available_cash": 0.0,
  "position_after": 0.0,
  "stopped": false
}
```

## Error Codes

| Code | Status | Description |
|------|--------|-------------|
| `INVALID_STRATEGY` | 400 | Unknown strategy type |
| `INVALID_PARAMETERS` | 400 | Invalid parameter values |
| `INSUFFICIENT_CAPITAL` | 400 | Insufficient cash for trade |
| `STRATEGY_STOPPED` | 400 | Strategy stopped (no capital) |
| `RATE_LIMIT_EXCEEDED` | 429 | Too many requests |
| Validation Error | 422 | Invalid request format |

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TRADING_API_KEY` | ✅ | - | API key (min 32 chars in production) |
| `TRADING_API_HOST` | ❌ | `0.0.0.0` | API host |
| `TRADING_API_PORT` | ❌ | `9000` | API port |
| `ENVIRONMENT` | ❌ | `development` | Environment |
| `LOG_LEVEL` | ❌ | `INFO` | Logging level |
| `RATE_LIMIT_ENABLED` | ❌ | `true` | Enable rate limiting |
| `RATE_LIMIT_EXECUTE_PER_MINUTE` | ❌ | `10` | Execute endpoint limit |

## Strategy Types Quick Reference

### Threshold Types
- `absolute`: Absolute price difference
- `percentage`: Percentage-based
- `std_dev`: Standard deviation-based
- `atr`: Average True Range-based

### Position Sizing
- `fixed`: Fixed position size
- `proportional`: Scales with return
- `normalized`: Risk-adjusted (requires history)

### History Types
- `open`: Open price history
- `high`: High price history
- `low`: Low price history
- `close`: Close price history (recommended)

## curl Examples

### Execute Strategy
```bash
curl -X POST http://localhost:9000/trading/execute \
  -H "Authorization: Bearer $TRADING_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{...}'
```

### List Strategies
```bash
curl http://localhost:9000/trading/strategies
```

### Health Check
```bash
curl http://localhost:9000/health
```

## Common Issues

| Issue | Solution |
|-------|----------|
| 401 Unauthorized | Check `TRADING_API_KEY` in `.env` |
| 429 Rate Limited | Wait or increase rate limit |
| 422 Validation Error | Check request format and required fields |
| Insufficient Capital | Check `available_cash` value |
| Missing History | Provide OHLC data for ATR/quantile strategies |

## Documentation Links

- **Full API Guide**: [API_USAGE.md](API_USAGE.md)
- **Strategy Guide**: [STRATEGIES.md](STRATEGIES.md)
- **Deployment**: [DEPLOYMENT.md](DEPLOYMENT.md)
- **Examples**: [EXAMPLES.md](EXAMPLES.md)
- **Swagger Docs**: http://localhost:9000/docs

