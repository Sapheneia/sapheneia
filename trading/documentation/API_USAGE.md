# Trading Strategies API - Usage Guide

Complete guide for using the Trading Strategies API.

## Table of Contents

1. [Authentication](#authentication)
2. [Endpoints](#endpoints)
3. [Request Examples](#request-examples)
4. [Response Format](#response-format)
5. [Error Handling](#error-handling)
6. [Rate Limiting](#rate-limiting)

## Authentication

All protected endpoints require API key authentication via HTTP Bearer token.

### Setting Up Authentication

1. Set `TRADING_API_KEY` in your `.env` file (minimum 32 characters in production):
```bash
TRADING_API_KEY=your_secure_api_key_minimum_32_characters_long
```

2. Include the API key in request headers:
```bash
Authorization: Bearer your_secure_api_key_minimum_32_characters_long
```

### Example with curl

```bash
curl -X POST http://localhost:9000/trading/execute \
  -H "Authorization: Bearer $TRADING_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{...}'
```

### Public Endpoints

The following endpoints do not require authentication:
- `GET /health` - Health check
- `GET /` - Root endpoint
- `GET /trading/strategies` - List available strategies
- `GET /trading/status` - Service status

## Endpoints

### POST /trading/execute

Execute a trading strategy and receive a recommended action.

**Authentication**: Required  
**Rate Limit**: 10 requests per minute  
**Content-Type**: `application/json`

#### Request Body

The request body varies by strategy type. All strategies share common parameters:

**Common Parameters (all strategies):**
- `strategy_type` (string, required): Strategy type - `"threshold"`, `"return"`, or `"quantile"`
- `forecast_price` (float, required, > 0): Forecasted price
- `current_price` (float, required, > 0): Current market price
- `current_position` (float, required, >= 0): Current position size (long-only)
- `available_cash` (float, required, >= 0): Available cash for trading
- `initial_capital` (float, required, > 0): Initial capital invested

#### Response

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

**Status Codes:**
- `200`: Successful execution
- `400`: Invalid parameters or strategy error
- `401`: Invalid or missing API key
- `422`: Validation error (invalid request format)
- `429`: Rate limit exceeded
- `500`: Internal server error

### GET /trading/strategies

List all available trading strategies with their descriptions and parameter requirements.

**Authentication**: Not required  
**Rate Limit**: 30 requests per minute

#### Response

```json
{
  "strategies": [
    {
      "name": "threshold",
      "description": "Price difference-based strategy with configurable thresholds",
      "parameters": {
        "required": ["threshold_type", "execution_size"],
        "optional": ["threshold_value", "which_history", "window_history", "min_history_length", "open_history", "high_history", "low_history", "close_history"]
      }
    },
    ...
  ]
}
```

### GET /trading/status

Get service status and health information.

**Authentication**: Not required  
**Rate Limit**: 30 requests per minute

#### Response

```json
{
  "status": "healthy",
  "service": "trading-strategies",
  "version": "1.0.0",
  "available_strategies": ["threshold", "return", "quantile"]
}
```

### GET /health

Health check endpoint for monitoring.

**Authentication**: Not required  
**Rate Limit**: 30 requests per minute

#### Response

```json
{
  "status": "healthy",
  "service": "trading-strategies",
  "version": "1.0.0",
  "available_strategies": ["threshold", "return", "quantile"]
}
```

## Request Examples

### Threshold Strategy

**Absolute Threshold:**
```bash
curl -X POST http://localhost:9000/trading/execute \
  -H "Authorization: Bearer $TRADING_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "strategy_type": "threshold",
    "forecast_price": 105.0,
    "current_price": 100.0,
    "current_position": 0.0,
    "available_cash": 100000.0,
    "initial_capital": 100000.0,
    "threshold_type": "absolute",
    "threshold_value": 2.0,
    "execution_size": 100.0
  }'
```

**Percentage Threshold:**
```bash
curl -X POST http://localhost:9000/trading/execute \
  -H "Authorization: Bearer $TRADING_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "strategy_type": "threshold",
    "forecast_price": 108.0,
    "current_price": 100.0,
    "current_position": 0.0,
    "available_cash": 100000.0,
    "initial_capital": 100000.0,
    "threshold_type": "percentage",
    "threshold_value": 0.05,
    "execution_size": 50.0
  }'
```

**ATR Threshold (requires OHLC history):**
```bash
curl -X POST http://localhost:9000/trading/execute \
  -H "Authorization: Bearer $TRADING_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "strategy_type": "threshold",
    "forecast_price": 105.0,
    "current_price": 100.0,
    "current_position": 0.0,
    "available_cash": 100000.0,
    "initial_capital": 100000.0,
    "threshold_type": "atr",
    "threshold_value": 1.5,
    "execution_size": 100.0,
    "open_history": [100.0, 101.0, 99.0, 102.0, 98.0],
    "high_history": [105.0, 106.0, 104.0, 107.0, 103.0],
    "low_history": [95.0, 96.0, 94.0, 97.0, 93.0],
    "close_history": [100.0, 101.0, 99.0, 102.0, 98.0]
  }'
```

### Return Strategy

**Fixed Position Sizing:**
```bash
curl -X POST http://localhost:9000/trading/execute \
  -H "Authorization: Bearer $TRADING_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "strategy_type": "return",
    "forecast_price": 108.0,
    "current_price": 100.0,
    "current_position": 0.0,
    "available_cash": 100000.0,
    "initial_capital": 100000.0,
    "position_sizing": "fixed",
    "threshold_value": 0.05,
    "execution_size": 10.0
  }'
```

**Proportional Position Sizing:**
```bash
curl -X POST http://localhost:9000/trading/execute \
  -H "Authorization: Bearer $TRADING_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "strategy_type": "return",
    "forecast_price": 110.0,
    "current_price": 100.0,
    "current_position": 0.0,
    "available_cash": 100000.0,
    "initial_capital": 100000.0,
    "position_sizing": "proportional",
    "threshold_value": 0.05,
    "execution_size": 100.0
  }'
```

**Normalized Position Sizing (requires history):**
```bash
curl -X POST http://localhost:9000/trading/execute \
  -H "Authorization: Bearer $TRADING_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "strategy_type": "return",
    "forecast_price": 108.0,
    "current_price": 100.0,
    "current_position": 0.0,
    "available_cash": 100000.0,
    "initial_capital": 100000.0,
    "position_sizing": "normalized",
    "threshold_value": 0.05,
    "execution_size": 100.0,
    "which_history": "close",
    "window_history": 20,
    "close_history": [100.0, 101.0, 99.0, 102.0, 98.0, ...]
  }'
```

### Quantile Strategy

```bash
curl -X POST http://localhost:9000/trading/execute \
  -H "Authorization: Bearer $TRADING_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
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
    "open_history": [100.0, 101.0, 99.0, ...],
    "high_history": [105.0, 106.0, 104.0, ...],
    "low_history": [95.0, 96.0, 94.0, ...],
    "close_history": [100.0, 101.0, 99.0, ...]
  }'
```

## Response Format

All successful responses follow this structure:

```json
{
  "action": "buy",
  "size": 100.0,
  "value": 10000.0,
  "reason": "Forecast 105.00 > Price 100.00, magnitude 5.0000 > threshold 0.0000",
  "available_cash": 90000.0,
  "position_after": 100.0,
  "stopped": false
}
```

**Fields:**
- `action` (string): Trading action - `"buy"`, `"sell"`, or `"hold"`
- `size` (float): Position size executed in shares/units
- `value` (float): Dollar value of the trade
- `reason` (string): Human-readable explanation of the action
- `available_cash` (float): Cash remaining after the trade
- `position_after` (float): Position size after the trade
- `stopped` (boolean): Whether the strategy is stopped (no capital remaining)

## Error Handling

### Error Response Format

```json
{
  "error": "ERROR_CODE",
  "message": "Human-readable error message",
  "details": {
    "field": "additional context"
  }
}
```

### Common Error Codes

- `INVALID_STRATEGY`: Unknown or invalid strategy type
- `INVALID_PARAMETERS`: Invalid parameter values or missing required parameters
- `INSUFFICIENT_CAPITAL`: Insufficient cash for the requested trade
- `STRATEGY_STOPPED`: Strategy stopped due to capital exhaustion
- `RATE_LIMIT_EXCEEDED`: Too many requests (429 status)

### Example Error Responses

**Invalid Strategy:**
```json
{
  "error": "INVALID_STRATEGY",
  "message": "Invalid strategy type provided",
  "details": {
    "strategy_type": "unknown"
  }
}
```

**Insufficient Capital:**
```json
{
  "error": "INSUFFICIENT_CAPITAL",
  "message": "Insufficient capital for trade",
  "details": {
    "required": 10000.0,
    "available": 5000.0
  }
}
```

**Validation Error (422):**
```json
{
  "detail": [
    {
      "loc": ["body", "forecast_price"],
      "msg": "ensure this value is greater than 0",
      "type": "value_error.number.not_gt"
    }
  ]
}
```

## Rate Limiting

Rate limiting is enabled by default to prevent abuse.

### Rate Limits

- **Default**: 60 requests per minute
- **Execute Endpoint**: 10 requests per minute (stricter)
- **Strategies/Status Endpoints**: 30 requests per minute

### Rate Limit Headers

Responses include rate limit information in headers:

```
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 9
X-RateLimit-Reset: 1700000000
```

### Rate Limit Exceeded

When rate limit is exceeded, you'll receive a 429 status:

```json
{
  "error": "RATE_LIMIT_EXCEEDED",
  "message": "Too many requests. Please try again later.",
  "detail": "Rate limit exceeded: 10 per 1 minute"
}
```

### Disabling Rate Limiting

Set in `.env`:
```bash
RATE_LIMIT_ENABLED=false
```

## Additional Resources

- **Strategy Guide**: [STRATEGIES.md](STRATEGIES.md) - Detailed strategy documentation
- **Deployment Guide**: [DEPLOYMENT.md](DEPLOYMENT.md) - Deployment instructions
- **Quick Reference**: [QUICK_REFERENCE.md](QUICK_REFERENCE.md) - Quick reference card
- **Examples**: [EXAMPLES.md](EXAMPLES.md) - Code examples in multiple languages
- **API Documentation**: http://localhost:9000/docs - Interactive Swagger documentation

