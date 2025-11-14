# Trading Strategies API - Code Examples

Code examples for integrating with the Trading Strategies API in various languages.

## Table of Contents

1. [Python Examples](#python-examples)
2. [JavaScript/TypeScript Examples](#javascripttypescript-examples)
3. [curl Examples](#curl-examples)
4. [Integration Examples](#integration-examples)

## Python Examples

### Basic Client

```python
import requests
import os

# Configuration
API_BASE_URL = "http://localhost:9000"
API_KEY = os.getenv("TRADING_API_KEY")

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# Execute threshold strategy
def execute_threshold_strategy():
    payload = {
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
    
    response = requests.post(
        f"{API_BASE_URL}/trading/execute",
        json=payload,
        headers=headers
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"Action: {result['action']}")
        print(f"Size: {result['size']}")
        print(f"Value: ${result['value']:.2f}")
        return result
    else:
        print(f"Error: {response.status_code}")
        print(response.json())
        return None

# Execute return strategy
def execute_return_strategy():
    payload = {
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
    
    response = requests.post(
        f"{API_BASE_URL}/trading/execute",
        json=payload,
        headers=headers
    )
    
    return response.json() if response.status_code == 200 else None

# Execute quantile strategy
def execute_quantile_strategy(ohlc_data):
    payload = {
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
        **ohlc_data
    }
    
    response = requests.post(
        f"{API_BASE_URL}/trading/execute",
        json=payload,
        headers=headers
    )
    
    return response.json() if response.status_code == 200 else None

# List available strategies
def list_strategies():
    response = requests.get(f"{API_BASE_URL}/trading/strategies")
    return response.json() if response.status_code == 200 else None

# Health check
def health_check():
    response = requests.get(f"{API_BASE_URL}/health")
    return response.json() if response.status_code == 200 else None
```

### Advanced Client with Error Handling

```python
import requests
from typing import Dict, Optional
from requests.exceptions import RequestException

class TradingAPIClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    def execute_strategy(self, strategy_params: Dict) -> Optional[Dict]:
        """Execute a trading strategy with error handling."""
        try:
            response = requests.post(
                f"{self.base_url}/trading/execute",
                json=strategy_params,
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                print("Rate limit exceeded. Please wait.")
                return None
            elif response.status_code == 401:
                print("Authentication failed. Check API key.")
                return None
            else:
                error = response.json()
                print(f"Error {response.status_code}: {error.get('message', 'Unknown error')}")
                return None
                
        except RequestException as e:
            print(f"Request failed: {e}")
            return None
    
    def list_strategies(self) -> Optional[Dict]:
        """List available strategies."""
        try:
            response = requests.get(
                f"{self.base_url}/trading/strategies",
                timeout=5
            )
            return response.json() if response.status_code == 200 else None
        except RequestException as e:
            print(f"Request failed: {e}")
            return None

# Usage
client = TradingAPIClient("http://localhost:9000", os.getenv("TRADING_API_KEY"))
result = client.execute_strategy({
    "strategy_type": "threshold",
    "forecast_price": 105.0,
    "current_price": 100.0,
    "current_position": 0.0,
    "available_cash": 100000.0,
    "initial_capital": 100000.0,
    "threshold_type": "absolute",
    "threshold_value": 2.0,
    "execution_size": 100.0
})
```

## JavaScript/TypeScript Examples

### Basic Client (JavaScript)

```javascript
const API_BASE_URL = 'http://localhost:9000';
const API_KEY = process.env.TRADING_API_KEY;

// Execute threshold strategy
async function executeThresholdStrategy() {
    const payload = {
        strategy_type: 'threshold',
        forecast_price: 105.0,
        current_price: 100.0,
        current_position: 0.0,
        available_cash: 100000.0,
        initial_capital: 100000.0,
        threshold_type: 'absolute',
        threshold_value: 2.0,
        execution_size: 100.0
    };
    
    try {
        const response = await fetch(`${API_BASE_URL}/trading/execute`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${API_KEY}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });
        
        if (response.ok) {
            const result = await response.json();
            console.log('Action:', result.action);
            console.log('Size:', result.size);
            console.log('Value:', result.value);
            return result;
        } else {
            const error = await response.json();
            console.error('Error:', error);
            return null;
        }
    } catch (error) {
        console.error('Request failed:', error);
        return null;
    }
}

// List strategies
async function listStrategies() {
    try {
        const response = await fetch(`${API_BASE_URL}/trading/strategies`);
        if (response.ok) {
            return await response.json();
        }
        return null;
    } catch (error) {
        console.error('Request failed:', error);
        return null;
    }
}
```

### TypeScript Client

```typescript
interface StrategyResponse {
    action: 'buy' | 'sell' | 'hold';
    size: number;
    value: number;
    reason: string;
    available_cash: number;
    position_after: number;
    stopped: boolean;
}

interface ThresholdStrategyParams {
    strategy_type: 'threshold';
    forecast_price: number;
    current_price: number;
    current_position: number;
    available_cash: number;
    initial_capital: number;
    threshold_type: 'absolute' | 'percentage' | 'std_dev' | 'atr';
    threshold_value: number;
    execution_size: number;
}

class TradingAPIClient {
    private baseUrl: string;
    private apiKey: string;
    
    constructor(baseUrl: string, apiKey: string) {
        this.baseUrl = baseUrl;
        this.apiKey = apiKey;
    }
    
    async executeStrategy(
        params: ThresholdStrategyParams
    ): Promise<StrategyResponse | null> {
        try {
            const response = await fetch(`${this.baseUrl}/trading/execute`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${this.apiKey}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(params)
            });
            
            if (response.ok) {
                return await response.json();
            } else {
                const error = await response.json();
                console.error('Error:', error);
                return null;
            }
        } catch (error) {
            console.error('Request failed:', error);
            return null;
        }
    }
}

// Usage
const client = new TradingAPIClient(
    'http://localhost:9000',
    process.env.TRADING_API_KEY!
);

const result = await client.executeStrategy({
    strategy_type: 'threshold',
    forecast_price: 105.0,
    current_price: 100.0,
    current_position: 0.0,
    available_cash: 100000.0,
    initial_capital: 100000.0,
    threshold_type: 'absolute',
    threshold_value: 2.0,
    execution_size: 100.0
});
```

## curl Examples

### Threshold Strategy

```bash
# Absolute threshold
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

# Percentage threshold
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

### Return Strategy

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
    "open_history": [100.0, 101.0, 99.0, 102.0, 98.0],
    "high_history": [105.0, 106.0, 104.0, 107.0, 103.0],
    "low_history": [95.0, 96.0, 94.0, 97.0, 93.0],
    "close_history": [100.0, 101.0, 99.0, 102.0, 98.0]
  }'
```

## Integration Examples

### Integration with Forecast Application

```python
import requests

# Get forecast from forecast API
forecast_response = requests.post(
    "http://localhost:8000/forecast/v1/timesfm20/inference",
    headers={"Authorization": f"Bearer {FORECAST_API_KEY}"},
    json=forecast_params
)

forecast_price = forecast_response.json()["prediction"]["point_forecast"][0][0]

# Execute trading strategy based on forecast
trading_response = requests.post(
    "http://localhost:9000/trading/execute",
    headers={"Authorization": f"Bearer {TRADING_API_KEY}"},
    json={
        "strategy_type": "threshold",
        "forecast_price": forecast_price,
        "current_price": current_market_price,
        "current_position": current_position,
        "available_cash": available_cash,
        "initial_capital": initial_capital,
        "threshold_type": "absolute",
        "threshold_value": 2.0,
        "execution_size": 100.0
    }
)

trading_signal = trading_response.json()
print(f"Trading action: {trading_signal['action']}")
```

### Orchestrator Example

```python
class TradingOrchestrator:
    def __init__(self, forecast_api_url, trading_api_url, forecast_key, trading_key):
        self.forecast_api_url = forecast_api_url
        self.trading_api_url = trading_api_url
        self.forecast_key = forecast_key
        self.trading_key = trading_key
        self.position = 0.0
        self.cash = 100000.0
        self.initial_capital = 100000.0
    
    def get_forecast(self, data_source):
        """Get price forecast from forecast API."""
        response = requests.post(
            f"{self.forecast_api_url}/forecast/v1/timesfm20/inference",
            headers={"Authorization": f"Bearer {self.forecast_key}"},
            json={"data_source_url_or_path": data_source, ...}
        )
        return response.json()["prediction"]["point_forecast"][0][0]
    
    def execute_trade(self, forecast_price, current_price):
        """Execute trading strategy based on forecast."""
        response = requests.post(
            f"{self.trading_api_url}/trading/execute",
            headers={"Authorization": f"Bearer {self.trading_key}"},
            json={
                "strategy_type": "threshold",
                "forecast_price": forecast_price,
                "current_price": current_price,
                "current_position": self.position,
                "available_cash": self.cash,
                "initial_capital": self.initial_capital,
                "threshold_type": "absolute",
                "threshold_value": 2.0,
                "execution_size": 100.0
            }
        )
        
        result = response.json()
        
        # Update state
        self.position = result["position_after"]
        self.cash = result["available_cash"]
        
        return result
    
    def run_cycle(self, data_source, current_price):
        """Complete forecast + trade cycle."""
        forecast_price = self.get_forecast(data_source)
        trade_result = self.execute_trade(forecast_price, current_price)
        return trade_result

# Usage
orchestrator = TradingOrchestrator(
    "http://localhost:8000",
    "http://localhost:9000",
    forecast_api_key,
    trading_api_key
)

result = orchestrator.run_cycle("data/uploads/stock.csv", 100.0)
print(f"Action: {result['action']}, Size: {result['size']}")
```

## Additional Resources

- **API Usage Guide**: [API_USAGE.md](API_USAGE.md)
- **Strategy Guide**: [STRATEGIES.md](STRATEGIES.md)
- **Quick Reference**: [QUICK_REFERENCE.md](QUICK_REFERENCE.md)
- **Deployment**: [DEPLOYMENT.md](DEPLOYMENT.md)

