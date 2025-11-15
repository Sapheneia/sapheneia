# Forecast Application - Code Examples

Code examples for integrating with the Forecast Application API in various languages.

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
API_BASE_URL = "http://localhost:8000"
API_KEY = os.getenv("API_SECRET_KEY", "your_secret_key_change_me_in_production")

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# Initialize model
def initialize_model():
    payload = {
        "backend": "cpu",
        "context_len": 64,
        "horizon_len": 24,
        "checkpoint": "google/timesfm-2.0-500m-pytorch"
    }
    
    response = requests.post(
        f"{API_BASE_URL}/forecast/v1/timesfm20/initialization",
        json=payload,
        headers=headers
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"Model initialized: {result['model_status']}")
        return True
    else:
        print(f"Error: {response.status_code} - {response.text}")
        return False

# Check model status
def check_status():
    response = requests.get(
        f"{API_BASE_URL}/forecast/v1/timesfm20/status",
        headers=headers
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"Model status: {result['model_status']}")
        return result['model_status']
    else:
        print(f"Error: {response.status_code} - {response.text}")
        return None

# Run inference
def run_inference(data_source, data_definition, parameters):
    payload = {
        "data_source_url_or_path": data_source,
        "data_definition": data_definition,
        "parameters": parameters
    }
    
    response = requests.post(
        f"{API_BASE_URL}/forecast/v1/timesfm20/inference",
        json=payload,
        headers=headers
    )
    
    if response.status_code == 200:
        result = response.json()
        return result
    else:
        print(f"Error: {response.status_code} - {response.text}")
        return None

# Complete workflow
def forecast_workflow():
    # 1. Initialize model
    if not initialize_model():
        return
    
    # 2. Check status
    status = check_status()
    if status != "ready":
        print(f"Model not ready: {status}")
        return
    
    # 3. Run inference
    data_source = "data/uploads/sample_data.csv"
    data_definition = {
        "price": "target"
    }
    parameters = {
        "context_len": 64,
        "horizon_len": 24
    }
    
    result = run_inference(data_source, data_definition, parameters)
    if result:
        print(f"Forecast completed: {len(result['prediction']['point_forecast'][0])} points")
        return result
    
    return None

if __name__ == "__main__":
    forecast_workflow()
```

### Advanced Client with Error Handling

```python
import requests
import time
from typing import Optional, Dict, Any

class ForecastClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    def initialize_model(
        self,
        backend: str = "cpu",
        context_len: int = 64,
        horizon_len: int = 24,
        checkpoint: Optional[str] = None
    ) -> Dict[str, Any]:
        """Initialize the model with retry logic."""
        payload = {
            "backend": backend,
            "context_len": context_len,
            "horizon_len": horizon_len
        }
        if checkpoint:
            payload["checkpoint"] = checkpoint
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    f"{self.base_url}/forecast/v1/timesfm20/initialization",
                    json=payload,
                    headers=self.headers,
                    timeout=300  # 5 minutes for model loading
                )
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    print(f"Retry {attempt + 1}/{max_retries} after {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    raise
    
    def check_status(self) -> Dict[str, Any]:
        """Check model status."""
        response = requests.get(
            f"{self.base_url}/forecast/v1/timesfm20/status",
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()
    
    def run_inference(
        self,
        data_source: str,
        data_definition: Dict[str, str],
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Run inference with error handling."""
        payload = {
            "data_source_url_or_path": data_source,
            "data_definition": data_definition,
            "parameters": parameters
        }
        
        response = requests.post(
            f"{self.base_url}/forecast/v1/timesfm20/inference",
            json=payload,
            headers=self.headers,
            timeout=600  # 10 minutes for inference
        )
        response.raise_for_status()
        return response.json()
    
    def shutdown_model(self) -> Dict[str, Any]:
        """Shutdown the model."""
        response = requests.post(
            f"{self.base_url}/forecast/v1/timesfm20/shutdown",
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()

# Usage
client = ForecastClient(
    base_url="http://localhost:8000",
    api_key="your_secret_key_change_me_in_production"
)

# Initialize
result = client.initialize_model()
print(f"Initialized: {result['model_status']}")

# Run inference
forecast = client.run_inference(
    data_source="data/uploads/sample_data.csv",
    data_definition={"price": "target"},
    parameters={"context_len": 64, "horizon_len": 24}
)
print(f"Forecast: {forecast['prediction']['point_forecast'][0][:5]}")
```

### Inference with Covariates

```python
import requests

API_BASE_URL = "http://localhost:8000"
API_KEY = "your_secret_key_change_me_in_production"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# Run inference with covariates
payload = {
    "data_source_url_or_path": "data/uploads/sample_data.csv",
    "data_definition": {
        "price": "target",
        "volume": "dynamic_numerical",
        "promotion": "dynamic_categorical"
    },
    "parameters": {
        "context_len": 64,
        "horizon_len": 24,
        "use_covariates": True,
        "use_quantiles": True,
        "quantile_indices": [1, 3, 5, 7, 9]
    }
}

response = requests.post(
    f"{API_BASE_URL}/forecast/v1/timesfm20/inference",
    json=payload,
    headers=headers
)

if response.status_code == 200:
    result = response.json()
    point_forecast = result['prediction']['point_forecast'][0]
    quantile_bands = result['prediction']['quantile_bands']
    print(f"Point forecast: {point_forecast[:5]}")
    print(f"Quantile bands: {list(quantile_bands.keys())[:3]}")
else:
    print(f"Error: {response.status_code} - {response.text}")
```

## JavaScript/TypeScript Examples

### Basic Client

```javascript
const API_BASE_URL = 'http://localhost:8000';
const API_KEY = 'your_secret_key_change_me_in_production';

const headers = {
  'Authorization': `Bearer ${API_KEY}`,
  'Content-Type': 'application/json'
};

// Initialize model
async function initializeModel() {
  const payload = {
    backend: 'cpu',
    context_len: 64,
    horizon_len: 24,
    checkpoint: 'google/timesfm-2.0-500m-pytorch'
  };
  
  const response = await fetch(
    `${API_BASE_URL}/forecast/v1/timesfm20/initialization`,
    {
      method: 'POST',
      headers: headers,
      body: JSON.stringify(payload)
    }
  );
  
  if (response.ok) {
    const result = await response.json();
    console.log(`Model initialized: ${result.model_status}`);
    return result;
  } else {
    const error = await response.json();
    console.error(`Error: ${response.status} - ${error.message}`);
    throw new Error(error.message);
  }
}

// Check status
async function checkStatus() {
  const response = await fetch(
    `${API_BASE_URL}/forecast/v1/timesfm20/status`,
    { headers: headers }
  );
  
  if (response.ok) {
    const result = await response.json();
    console.log(`Model status: ${result.model_status}`);
    return result;
  } else {
    const error = await response.json();
    console.error(`Error: ${response.status} - ${error.message}`);
    throw new Error(error.message);
  }
}

// Run inference
async function runInference(dataSource, dataDefinition, parameters) {
  const payload = {
    data_source_url_or_path: dataSource,
    data_definition: dataDefinition,
    parameters: parameters
  };
  
  const response = await fetch(
    `${API_BASE_URL}/forecast/v1/timesfm20/inference`,
    {
      method: 'POST',
      headers: headers,
      body: JSON.stringify(payload)
    }
  );
  
  if (response.ok) {
    const result = await response.json();
    return result;
  } else {
    const error = await response.json();
    console.error(`Error: ${response.status} - ${error.message}`);
    throw new Error(error.message);
  }
}

// Complete workflow
async function forecastWorkflow() {
  try {
    // 1. Initialize model
    await initializeModel();
    
    // 2. Check status
    const status = await checkStatus();
    if (status.model_status !== 'ready') {
      console.error(`Model not ready: ${status.model_status}`);
      return;
    }
    
    // 3. Run inference
    const result = await runInference(
      'data/uploads/sample_data.csv',
      { price: 'target' },
      { context_len: 64, horizon_len: 24 }
    );
    
    console.log(`Forecast completed: ${result.prediction.point_forecast[0].length} points`);
    return result;
  } catch (error) {
    console.error('Forecast workflow failed:', error);
    throw error;
  }
}

// Usage
forecastWorkflow();
```

### TypeScript Client Class

```typescript
interface ModelInitInput {
  backend?: string;
  context_len?: number;
  horizon_len?: number;
  checkpoint?: string;
}

interface InferenceInput {
  data_source_url_or_path: string;
  data_definition: Record<string, string>;
  parameters: Record<string, any>;
}

class ForecastClient {
  private baseUrl: string;
  private headers: HeadersInit;

  constructor(baseUrl: string, apiKey: string) {
    this.baseUrl = baseUrl;
    this.headers = {
      'Authorization': `Bearer ${apiKey}`,
      'Content-Type': 'application/json'
    };
  }

  async initializeModel(input: ModelInitInput = {}): Promise<any> {
    const payload = {
      backend: 'cpu',
      context_len: 64,
      horizon_len: 24,
      ...input
    };

    const response = await fetch(
      `${this.baseUrl}/forecast/v1/timesfm20/initialization`,
      {
        method: 'POST',
        headers: this.headers,
        body: JSON.stringify(payload)
      }
    );

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.message);
    }

    return response.json();
  }

  async checkStatus(): Promise<any> {
    const response = await fetch(
      `${this.baseUrl}/forecast/v1/timesfm20/status`,
      { headers: this.headers }
    );

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.message);
    }

    return response.json();
  }

  async runInference(input: InferenceInput): Promise<any> {
    const response = await fetch(
      `${this.baseUrl}/forecast/v1/timesfm20/inference`,
      {
        method: 'POST',
        headers: this.headers,
        body: JSON.stringify(input)
      }
    );

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.message);
    }

    return response.json();
  }
}

// Usage
const client = new ForecastClient(
  'http://localhost:8000',
  'your_secret_key_change_me_in_production'
);

client.initializeModel()
  .then(result => console.log('Initialized:', result.model_status))
  .catch(error => console.error('Error:', error));
```

## curl Examples

### Initialize Model

```bash
curl -X POST http://localhost:8000/forecast/v1/timesfm20/initialization \
  -H "Authorization: Bearer your_secret_key_change_me_in_production" \
  -H "Content-Type: application/json" \
  -d '{
    "backend": "cpu",
    "context_len": 64,
    "horizon_len": 24,
    "checkpoint": "google/timesfm-2.0-500m-pytorch"
  }'
```

### Check Status

```bash
curl http://localhost:8000/forecast/v1/timesfm20/status \
  -H "Authorization: Bearer your_secret_key_change_me_in_production"
```

### Run Inference (Basic)

```bash
curl -X POST http://localhost:8000/forecast/v1/timesfm20/inference \
  -H "Authorization: Bearer your_secret_key_change_me_in_production" \
  -H "Content-Type: application/json" \
  -d '{
    "data_source_url_or_path": "data/uploads/sample_data.csv",
    "data_definition": {
      "price": "target"
    },
    "parameters": {
      "context_len": 64,
      "horizon_len": 24
    }
  }'
```

### Run Inference (With Covariates)

```bash
curl -X POST http://localhost:8000/forecast/v1/timesfm20/inference \
  -H "Authorization: Bearer your_secret_key_change_me_in_production" \
  -H "Content-Type: application/json" \
  -d '{
    "data_source_url_or_path": "data/uploads/sample_data.csv",
    "data_definition": {
      "price": "target",
      "volume": "dynamic_numerical",
      "promotion": "dynamic_categorical"
    },
    "parameters": {
      "context_len": 64,
      "horizon_len": 24,
      "use_covariates": true,
      "use_quantiles": true,
      "quantile_indices": [1, 3, 5, 7, 9]
    }
  }'
```

### Shutdown Model

```bash
curl -X POST http://localhost:8000/forecast/v1/timesfm20/shutdown \
  -H "Authorization: Bearer your_secret_key_change_me_in_production"
```

### List Available Models

```bash
curl http://localhost:8000/models
```

### Health Check

```bash
curl http://localhost:8000/health
```

## Integration Examples

### Integration with UI Application

The UI application (`ui/`) integrates with the forecast API:

```python
# ui/api_client.py example
import requests

class ForecastAPIClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    def initialize_model(self, config: dict):
        response = requests.post(
            f"{self.base_url}/forecast/v1/timesfm20/initialization",
            json=config,
            headers=self.headers
        )
        return response.json()
    
    def run_inference(self, data_source: str, data_definition: dict, parameters: dict):
        payload = {
            "data_source_url_or_path": data_source,
            "data_definition": data_definition,
            "parameters": parameters
        }
        response = requests.post(
            f"{self.base_url}/forecast/v1/timesfm20/inference",
            json=payload,
            headers=self.headers
        )
        return response.json()
```

### Integration with Trading Application

The trading application can use forecast API for price predictions:

```python
# Example: Trading application using forecast API
import requests

def get_price_forecast(api_base_url: str, api_key: str, data_source: str):
    """Get price forecast from forecast API."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # Ensure model is initialized
    status_response = requests.get(
        f"{api_base_url}/forecast/v1/timesfm20/status",
        headers=headers
    )
    
    if status_response.json()['model_status'] != 'ready':
        # Initialize model
        init_response = requests.post(
            f"{api_base_url}/forecast/v1/timesfm20/initialization",
            json={"backend": "cpu", "context_len": 64, "horizon_len": 24},
            headers=headers
        )
    
    # Run inference
    inference_response = requests.post(
        f"{api_base_url}/forecast/v1/timesfm20/inference",
        json={
            "data_source_url_or_path": data_source,
            "data_definition": {"price": "target"},
            "parameters": {"context_len": 64, "horizon_len": 24}
        },
        headers=headers
    )
    
    result = inference_response.json()
    return result['prediction']['point_forecast'][0][0]  # First forecast value
```

### Batch Processing Example

```python
import requests
from typing import List

def batch_forecast(
    api_base_url: str,
    api_key: str,
    data_sources: List[str],
    data_definition: dict,
    parameters: dict
) -> List[dict]:
    """Run forecasts for multiple data sources."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    results = []
    for data_source in data_sources:
        try:
            response = requests.post(
                f"{api_base_url}/forecast/v1/timesfm20/inference",
                json={
                    "data_source_url_or_path": data_source,
                    "data_definition": data_definition,
                    "parameters": parameters
                },
                headers=headers,
                timeout=600
            )
            response.raise_for_status()
            results.append(response.json())
        except requests.exceptions.RequestException as e:
            print(f"Error processing {data_source}: {e}")
            results.append({"error": str(e)})
    
    return results
```

---

**See also:**
- [API Usage Guide](API_USAGE.md) - Detailed API documentation
- [Quick Reference](QUICK_REFERENCE.md) - Quick reference card
- [Architecture](ARCHITECTURE.md) - System architecture

