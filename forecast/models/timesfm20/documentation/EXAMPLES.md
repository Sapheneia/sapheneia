# TimesFM-2.0 - Code Examples

TimesFM-2.0 specific code examples and use cases.

## Table of Contents

1. [Basic Examples](#basic-examples)
2. [Covariates Examples](#covariates-examples)
3. [Quantile Examples](#quantile-examples)
4. [Batch Examples](#batch-examples)
5. [Integration Examples](#integration-examples)
6. [Error Handling Examples](#error-handling-examples)

## Basic Examples

### Python: Basic Forecast

```python
import requests

API_BASE_URL = "http://localhost:8000"
API_KEY = "your_secret_key_change_me_in_production"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# 1. Initialize model
init_response = requests.post(
    f"{API_BASE_URL}/forecast/v1/timesfm20/initialization",
    json={
        "backend": "cpu",
        "context_len": 64,
        "horizon_len": 24
    },
    headers=headers
)
print(f"Initialized: {init_response.json()['model_status']}")

# 2. Check status
status_response = requests.get(
    f"{API_BASE_URL}/forecast/v1/timesfm20/status",
    headers=headers
)
print(f"Status: {status_response.json()['model_status']}")

# 3. Run inference
inference_response = requests.post(
    f"{API_BASE_URL}/forecast/v1/timesfm20/inference",
    json={
        "data_source_url_or_path": "data/uploads/sample_data.csv",
        "data_definition": {
            "price": "target"
        },
        "parameters": {
            "context_len": 64,
            "horizon_len": 24
        }
    },
    headers=headers
)

result = inference_response.json()
forecast = result['prediction']['point_forecast'][0]
print(f"Forecast: {forecast[:5]}")  # First 5 values
```

### Python: Complete Workflow with Error Handling

```python
import requests
import time

class TimesFMClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    def initialize(self, backend="cpu", context_len=64, horizon_len=24):
        """Initialize model with retry logic."""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    f"{self.base_url}/forecast/v1/timesfm20/initialization",
                    json={
                        "backend": backend,
                        "context_len": context_len,
                        "horizon_len": horizon_len
                    },
                    headers=self.headers,
                    timeout=300
                )
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    print(f"Retry {attempt + 1}/{max_retries} after {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    raise
    
    def check_status(self):
        """Check model status."""
        response = requests.get(
            f"{self.base_url}/forecast/v1/timesfm20/status",
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()
    
    def forecast(self, data_source, data_definition, parameters=None):
        """Run forecast."""
        if parameters is None:
            parameters = {}
        
        payload = {
            "data_source_url_or_path": data_source,
            "data_definition": data_definition,
            "parameters": parameters
        }
        
        response = requests.post(
            f"{self.base_url}/forecast/v1/timesfm20/inference",
            json=payload,
            headers=self.headers,
            timeout=600
        )
        response.raise_for_status()
        return response.json()
    
    def shutdown(self):
        """Shutdown model."""
        response = requests.post(
            f"{self.base_url}/forecast/v1/timesfm20/shutdown",
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()

# Usage
client = TimesFMClient(
    "http://localhost:8000",
    "your_secret_key_change_me_in_production"
)

# Initialize
client.initialize()

# Wait for ready
while True:
    status = client.check_status()
    if status['model_status'] == 'ready':
        break
    elif status['model_status'] == 'error':
        raise Exception(f"Model error: {status.get('details')}")
    time.sleep(1)

# Forecast
result = client.forecast(
    data_source="data/uploads/sample_data.csv",
    data_definition={"price": "target"},
    parameters={"context_len": 64, "horizon_len": 24}
)

print(f"Forecast: {result['prediction']['point_forecast'][0][:5]}")
```

## Covariates Examples

### Python: With Dynamic Numerical Covariates

```python
import requests

API_BASE_URL = "http://localhost:8000"
API_KEY = "your_secret_key_change_me_in_production"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# Run inference with volume as covariate
response = requests.post(
    f"{API_BASE_URL}/forecast/v1/timesfm20/inference",
    json={
        "data_source_url_or_path": "data/uploads/sales_data.csv",
        "data_definition": {
            "sales": "target",
            "volume": "dynamic_numerical"
        },
        "parameters": {
            "context_len": 64,
            "horizon_len": 24,
            "use_covariates": True
        }
    },
    headers=headers
)

result = response.json()
print(f"Method: {result['prediction']['method']}")
print(f"Forecast: {result['prediction']['point_forecast'][0][:5]}")
```

### Python: With Dynamic Categorical Covariates

```python
# Run inference with promotion as categorical covariate
response = requests.post(
    f"{API_BASE_URL}/forecast/v1/timesfm20/inference",
    json={
        "data_source_url_or_path": "data/uploads/promo_data.csv",
        "data_definition": {
            "price": "target",
            "promotion": "dynamic_categorical"
        },
        "parameters": {
            "context_len": 64,
            "horizon_len": 24,
            "use_covariates": True
        }
    },
    headers=headers
)
```

### Python: With Static Covariates

```python
# Run inference with static region and base_price
response = requests.post(
    f"{API_BASE_URL}/forecast/v1/timesfm20/inference",
    json={
        "data_source_url_or_path": "data/uploads/regional_data.csv",
        "data_definition": {
            "price": "target",
            "region": "static_categorical",
            "base_price": "static_numerical"
        },
        "parameters": {
            "context_len": 64,
            "horizon_len": 24,
            "use_covariates": True
        }
    },
    headers=headers
)
```

### Python: Complete Covariates Example

```python
# All covariate types
response = requests.post(
    f"{API_BASE_URL}/forecast/v1/timesfm20/inference",
    json={
        "data_source_url_or_path": "data/uploads/complete_data.csv",
        "data_definition": {
            "price": "target",
            "volume": "dynamic_numerical",
            "promotion": "dynamic_categorical",
            "region": "static_categorical",
            "base_price": "static_numerical"
        },
        "parameters": {
            "context_len": 128,
            "horizon_len": 48,
            "use_covariates": True,
            "xreg_mode": "xreg + timesfm",
            "ridge": 0.01
        }
    },
    headers=headers
)
```

## Quantile Examples

### Python: Basic Quantile Forecast

```python
# Run inference with quantiles
response = requests.post(
    f"{API_BASE_URL}/forecast/v1/timesfm20/inference",
    json={
        "data_source_url_or_path": "data/uploads/price.csv",
        "data_definition": {
            "price": "target"
        },
        "parameters": {
            "context_len": 64,
            "horizon_len": 24,
            "use_quantiles": True,
            "quantile_indices": [1, 3, 5, 7, 9]
        }
    },
    headers=headers
)

result = response.json()
point_forecast = result['prediction']['point_forecast'][0]
quantile_bands = result['prediction']['quantile_bands']

print(f"Point forecast: {point_forecast[:5]}")
print(f"Q10-Q30 lower: {quantile_bands['quantile_band_0_lower'][:5]}")
print(f"Q10-Q30 upper: {quantile_bands['quantile_band_0_upper'][:5]}")
```

### Python: Quantile Visualization

```python
import matplotlib.pyplot as plt

result = client.forecast(
    data_source="data/uploads/price.csv",
    data_definition={"price": "target"},
    parameters={
        "context_len": 64,
        "horizon_len": 24,
        "use_quantiles": True,
        "quantile_indices": [1, 3, 5, 7, 9]
    }
)

# Extract data
historical = result['visualization_data']['historical_data']
forecast = result['prediction']['point_forecast'][0]
bands = result['prediction']['quantile_bands']

# Plot
plt.figure(figsize=(12, 6))
plt.plot(historical, label='Historical', color='blue')
plt.plot(range(len(historical), len(historical) + len(forecast)), 
         forecast, label='Forecast', color='red')
plt.fill_between(
    range(len(historical), len(historical) + len(forecast)),
    bands['quantile_band_0_lower'],
    bands['quantile_band_0_upper'],
    alpha=0.3,
    label='Q10-Q30 Band'
)
plt.legend()
plt.title('Forecast with Uncertainty Bands')
plt.show()
```

## Batch Examples

### Python: Batch Forecasting

```python
def batch_forecast(data_sources, data_definition, parameters):
    """Forecast multiple series."""
    results = []
    
    for data_source in data_sources:
        try:
            response = requests.post(
                f"{API_BASE_URL}/forecast/v1/timesfm20/inference",
                json={
                    "data_source_url_or_path": data_source,
                    "data_definition": data_definition,
                    "parameters": parameters
                },
                headers=headers,
                timeout=600
            )
            response.raise_for_status()
            results.append({
                "source": data_source,
                "forecast": response.json()['prediction']['point_forecast'][0],
                "status": "success"
            })
        except Exception as e:
            results.append({
                "source": data_source,
                "error": str(e),
                "status": "error"
            })
    
    return results

# Usage
data_sources = [
    "data/uploads/series1.csv",
    "data/uploads/series2.csv",
    "data/uploads/series3.csv"
]

results = batch_forecast(
    data_sources=data_sources,
    data_definition={"value": "target"},
    parameters={"context_len": 64, "horizon_len": 24}
)

for result in results:
    if result['status'] == 'success':
        print(f"{result['source']}: {len(result['forecast'])} points")
    else:
        print(f"{result['source']}: Error - {result['error']}")
```

## Integration Examples

### Python: Integration with Trading Application

```python
import requests

def get_price_forecast(forecast_api_url, forecast_api_key, data_source):
    """Get price forecast for trading application."""
    headers = {
        "Authorization": f"Bearer {forecast_api_key}",
        "Content-Type": "application/json"
    }
    
    # Ensure model is initialized
    status_response = requests.get(
        f"{forecast_api_url}/forecast/v1/timesfm20/status",
        headers=headers
    )
    
    if status_response.json()['model_status'] != 'ready':
        # Initialize model
        init_response = requests.post(
            f"{forecast_api_url}/forecast/v1/timesfm20/initialization",
            json={"backend": "cpu", "context_len": 64, "horizon_len": 24},
            headers=headers,
            timeout=300
        )
        init_response.raise_for_status()
    
    # Run inference
    inference_response = requests.post(
        f"{forecast_api_url}/forecast/v1/timesfm20/inference",
        json={
            "data_source_url_or_path": data_source,
            "data_definition": {"price": "target"},
            "parameters": {"context_len": 64, "horizon_len": 24}
        },
        headers=headers,
        timeout=600
    )
    inference_response.raise_for_status()
    
    result = inference_response.json()
    # Return first forecast value
    return result['prediction']['point_forecast'][0][0]

# Usage in trading application
forecast_price = get_price_forecast(
    forecast_api_url="http://localhost:8000",
    forecast_api_key="your_secret_key_change_me_in_production",
    data_source="data/uploads/price_data.csv"
)

print(f"Forecast price: {forecast_price}")
```

## Error Handling Examples

### Python: Comprehensive Error Handling

```python
import requests
from typing import Optional, Dict, Any

def safe_forecast(
    api_url: str,
    api_key: str,
    data_source: str,
    data_definition: Dict[str, str],
    parameters: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """Run forecast with comprehensive error handling."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    try:
        # Check model status
        status_response = requests.get(
            f"{api_url}/forecast/v1/timesfm20/status",
            headers=headers,
            timeout=10
        )
        
        if status_response.status_code != 200:
            print(f"Status check failed: {status_response.status_code}")
            return None
        
        status = status_response.json()
        
        if status['model_status'] != 'ready':
            print(f"Model not ready: {status['model_status']}")
            return None
        
        # Run inference
        inference_response = requests.post(
            f"{api_url}/forecast/v1/timesfm20/inference",
            json={
                "data_source_url_or_path": data_source,
                "data_definition": data_definition,
                "parameters": parameters
            },
            headers=headers,
            timeout=600
        )
        
        if inference_response.status_code == 200:
            return inference_response.json()
        elif inference_response.status_code == 400:
            error = inference_response.json()
            print(f"Bad request: {error.get('message')}")
            return None
        elif inference_response.status_code == 429:
            print("Rate limit exceeded. Please wait.")
            return None
        else:
            print(f"Error: {inference_response.status_code}")
            return None
            
    except requests.exceptions.Timeout:
        print("Request timed out")
        return None
    except requests.exceptions.ConnectionError:
        print("Connection error. Is the API running?")
        return None
    except Exception as e:
        print(f"Unexpected error: {e}")
        return None

# Usage
result = safe_forecast(
    api_url="http://localhost:8000",
    api_key="your_secret_key_change_me_in_production",
    data_source="data/uploads/sample_data.csv",
    data_definition={"price": "target"},
    parameters={"context_len": 64, "horizon_len": 24}
)

if result:
    print(f"Forecast: {result['prediction']['point_forecast'][0][:5]}")
else:
    print("Forecast failed")
```

---

**See also:**
- [Architecture](ARCHITECTURE.md) - Model architecture
- [API Reference](API_REFERENCE.md) - Complete API documentation
- [Data Format](DATA_FORMAT.md) - Data format requirements
- [Parameters](PARAMETERS.md) - Parameter guide
- [Usage Guide](USAGE_GUIDE.md) - Step-by-step usage

