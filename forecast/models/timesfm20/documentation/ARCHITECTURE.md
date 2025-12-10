# TimesFM-2.0 - Architecture

Complete architecture documentation for the TimesFM-2.0 model implementation.

## Table of Contents

1. [Model Overview](#model-overview)
2. [Architecture Details](#architecture-details)
3. [Model Parameters](#model-parameters)
4. [Initialization Process](#initialization-process)
5. [Inference Workflow](#inference-workflow)
6. [Data Processing](#data-processing)
7. [Covariates Support](#covariates-support)
8. [Quantile Forecasting](#quantile-forecasting)
9. [State Management](#state-management)
10. [Integration with Core Modules](#integration-with-core-modules)

## Model Overview

TimesFM-2.0 is Google's 500M parameter foundation model for time series forecasting. It is a decoder-only transformer model pre-trained on 100 billion real-world time-points.

### Key Features

- **Foundation Model**: Pre-trained on massive time series dataset
- **Zero-Shot Forecasting**: Works without model-specific training
- **Covariates Support**: Supports dynamic and static, numerical and categorical covariates
- **Quantile Forecasting**: Provides uncertainty quantification (10-90th percentiles)
- **Flexible Context**: Configurable context window (32-2048)
- **Multiple Backends**: Supports CPU, GPU, and TPU backends

### Model Specifications

- **Parameters**: 500M
- **Architecture**: Decoder-only transformer
- **Pre-training**: 100 billion time-points
- **Checkpoint**: `google/timesfm-2.0-500m-pytorch` (PyTorch) or `google/timesfm-2.0-500m-jax` (JAX/PAX)

## Architecture Details

### Model Structure

```
TimesFM-2.0 Model
├── Input Processing
│   ├── Patch Encoding
│   ├── Positional Embeddings
│   └── Frequency Encoding
├── Transformer Layers (20 layers)
│   ├── Self-Attention
│   ├── Feed-Forward Networks
│   └── Layer Normalization
├── Output Decoding
│   ├── Point Forecast
│   └── Quantile Forecast
└── Covariates Integration (optional)
    ├── Dynamic Covariates
    └── Static Covariates
```

### Transformer Architecture

- **Layers**: 20 transformer layers
- **Model Dimensions**: 1280
- **Input Patch Length**: 32 (fixed)
- **Output Patch Length**: 128 (fixed)
- **Attention Heads**: Multi-head self-attention
- **Activation**: GELU

### Patch-Based Processing

TimesFM-2.0 processes time series in patches:
- **Input Patches**: Fixed length of 32 time points
- **Output Patches**: Fixed length of 128 time points
- **Patch Overlap**: Handled automatically by the model

## Model Parameters

### Core Parameters

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `backend` | str | `"cpu"` | `cpu`, `gpu`, `tpu`, `mps` | Computing backend |
| `context_len` | int | `64` | 32-2048 | Historical window length |
| `horizon_len` | int | `24` | 1-128 | Forecast horizon length |
| `checkpoint` | str | `"google/timesfm-2.0-500m-pytorch"` | - | HuggingFace model ID |
| `local_model_path` | str | `None` | - | Local model file path |

### Parameter Details

**`backend`**
- `"cpu"`: CPU computation (default, works everywhere)
- `"gpu"`: GPU acceleration (requires CUDA)
- `"tpu"`: TPU acceleration (Google Cloud)
- `"mps"`: Apple Silicon GPU (macOS)

**`context_len`**
- Length of historical data used for forecasting
- Default: 64 (optimized for performance)
- Range: 32-2048
- Larger values: Better accuracy, slower inference, more memory
- Smaller values: Faster inference, less memory, potentially lower accuracy

**`horizon_len`**
- Number of future time steps to forecast
- Default: 24
- Range: 1-128
- Must be ≤ `context_len` for best results

**`checkpoint`**
- HuggingFace repository ID for model weights
- PyTorch: `"google/timesfm-2.0-500m-pytorch"`
- JAX/PAX: `"google/timesfm-2.0-500m-jax"` (x86_64 only)

## Initialization Process

### Initialization Flow

```
1. Receive initialization request
   ↓
2. Validate parameters
   ↓
3. Check current model status
   ↓
4. Acquire model lock (thread-safe)
   ↓
5. Set status to "initializing"
   ↓
6. Load model from source:
   - HuggingFace: Download and load
   - Local: Load from file
   - MLflow: Load from MLflow registry
   ↓
7. Create TimesFMModel wrapper
   ↓
8. Create Forecaster instance
   ↓
9. Set status to "ready"
   ↓
10. Release model lock
   ↓
11. Return initialization status
```

### Initialization Sources

**HuggingFace (Default)**
- Downloads model weights from HuggingFace Hub
- Requires internet connection
- First-time download: ~3.8GB
- Cached for subsequent uses

**Local Model**
- Loads from local file path
- Path relative to `forecast/models/timesfm20/local/`
- Useful for offline deployment
- Faster initialization (no download)

**MLflow (Future)**
- Loads from MLflow model registry
- Supports model versioning
- Production deployment workflow

### Initialization Time

- **First-time (HuggingFace)**: 2-5 minutes (download + load)
- **Subsequent (Cached)**: 30-60 seconds
- **Local Model**: 30-60 seconds
- **GPU Backend**: Faster initialization

## Inference Workflow

### Inference Flow

```
1. Receive inference request
   ↓
2. Validate request (InferenceInput schema)
   ↓
3. Check model status (must be "ready")
   ↓
4. Submit to thread pool executor
   ↓
5. In thread pool:
   a. Fetch data source (local file or HTTP URL)
   b. Load and transform data (DataProcessor)
   c. Prepare covariates (if applicable)
   d. Run forecast (Forecaster.forecast())
   e. Process quantile bands (if requested)
   f. Prepare visualization data
   ↓
6. Return inference results
```

### Thread Pool Execution

- **Purpose**: Avoid blocking async event loop
- **Workers**: 4 threads (configurable)
- **Benefits**: Concurrent request handling
- **Limitation**: Single model instance (module-level state)

### Inference Time

- **Basic Forecast**: 0.1-0.5 seconds
- **With Covariates**: 0.2-0.8 seconds
- **With Quantiles**: 0.3-1.0 seconds
- **GPU Backend**: 2-5x faster

## Data Processing

### Data Flow

```
Data Source (CSV file or HTTP URL)
   ↓
fetch_data_source() [forecast/core/data.py]
   - Path normalization
   - Security validation
   - File/URL fetching
   ↓
Raw DataFrame
   ↓
load_and_transform_timesfm_data() [forecast/models/timesfm20/services/data.py]
   - Data validation
   - Data type conversion
   - Data definition validation
   ↓
DataProcessor.prepare_forecast_data() [forecast/core/data_processing.py]
   - Extract target series
   - Prepare covariates (dynamic/static, numerical/categorical)
   - Validate data length
   ↓
Target Inputs + Covariates Dictionary
```

### Data Requirements

- **Format**: CSV with `date` column
- **Target Column**: One column marked as `"target"` in data definition
- **Minimum Length**: Must have at least `context_len` data points
- **Date Column**: Required, will be converted to datetime

### Data Transformation

1. **Date Conversion**: `date` column converted to datetime
2. **Type Conversion**: Columns converted based on data definition
3. **Target Extraction**: Target series extracted for forecasting
4. **Covariates Preparation**: Covariates formatted for TimesFM input
5. **Context Window**: Most recent `context_len` points used

## Covariates Support

### Covariate Types

**Dynamic Numerical**
- Time-varying numerical features
- Example: `volume`, `temperature`, `sales`
- Must cover context + horizon periods

**Dynamic Categorical**
- Time-varying categorical features
- Example: `day_of_week`, `promotion_active`, `season`
- Must cover context + horizon periods

**Static Numerical**
- Per-series numerical features
- Example: `base_price`, `region_code`
- Single value per series

**Static Categorical**
- Per-series categorical features
- Example: `region`, `product_category`
- Single value per series

### Covariates Integration

**XReg Modes:**
- `"xreg + timesfm"`: Covariates first, then TimesFM (recommended)
- `"timesfm + xreg"`: TimesFM first, then covariates

**Ridge Regression:**
- Parameter: `ridge` (default: 0.0)
- Prevents overfitting with covariates
- Range: 0.0 to small positive values (e.g., 0.1)

**Normalization:**
- `normalize_xreg_target_per_input`: Normalize covariates per input
- Default: `True`
- Improves stability

## Quantile Forecasting

### Quantile Output

TimesFM-2.0 outputs 10 quantile forecasts:

| Index | Quantile | Description |
|-------|----------|-------------|
| 0 | Mean (Legacy) | Legacy mean forecast (skip) |
| 1 | Q10 | 10th percentile |
| 2 | Q20 | 20th percentile |
| 3 | Q30 | 30th percentile |
| 4 | Q40 | 40th percentile |
| 5 | Q50 | Median |
| 6 | Q60 | 60th percentile |
| 7 | Q70 | 70th percentile |
| 8 | Q80 | 80th percentile |
| 9 | Q90 | 90th percentile |

### Quantile Band Processing

Quantile bands are created from selected quantiles:

- **Lower Bands**: Q10, Q20, Q30
- **Upper Bands**: Q70, Q80, Q90
- **Band Labels**: "Q10–Q30", "Q20–Q40", etc.

### Quantile Selection

Specify quantile indices in inference request:

```json
{
  "parameters": {
    "use_quantiles": true,
    "quantile_indices": [1, 3, 5, 7, 9]  // Q10, Q30, Q50, Q70, Q90
  }
}
```

## State Management

### Module-Level State

TimesFM-2.0 uses module-level state management:

```python
# forecast/models/timesfm20/services/model.py
_forecaster_instance: Optional[Forecaster] = None
_model_wrapper: Optional[TimesFMModel] = None
_model_status: str = "uninitialized"
_model_lock = threading.Lock()
```

### State Values

- `"uninitialized"`: Model not loaded
- `"initializing"`: Model is loading
- `"ready"`: Model ready for inference
- `"error"`: Model encountered an error

### Thread Safety

- **Thread Lock**: `_model_lock` ensures thread-safe state access
- **Concurrent Requests**: Single worker handles concurrent requests safely
- **Limitation**: Only one worker per model instance

### State Limitations

⚠️ **Current Limitations:**
- Single worker only (`--workers 1`)
- No horizontal scaling
- State non-persistent (lost on restart)

**Future**: Redis state backend for distributed state management

## Integration with Core Modules

### Core Module Usage

**`forecast/core/model_wrapper.py`**
- `TimesFMModel` class: Wraps TimesFM model
- Handles model initialization from various sources
- Manages model configuration

**`forecast/core/forecasting.py`**
- `Forecaster` class: Forecasting logic
- `run_forecast()`: Centralized forecast execution
- `process_quantile_bands()`: Quantile band processing

**`forecast/core/data_processing.py`**
- `DataProcessor` class: Data processing and validation
- `prepare_forecast_data()`: Prepare data for forecasting
- `prepare_visualization_data()`: Prepare visualization data

**`forecast/core/data.py`**
- `fetch_data_source()`: Fetch data from various sources
- Path normalization and security validation

**`forecast/core/paths.py`**
- Path handling utilities
- Environment detection (venv vs Docker)
- Security validation

### Module Dependencies

```
forecast/models/timesfm20/services/model.py
├── forecast/core/model_wrapper.py (TimesFMModel)
├── forecast/core/forecasting.py (Forecaster, run_forecast)
└── forecast/core/config.py (settings)

forecast/models/timesfm20/services/data.py
├── forecast/core/data_processing.py (DataProcessor)
└── forecast/core/data.py (fetch_data_source)

forecast/models/timesfm20/routes/endpoints.py
├── forecast/core/security.py (get_api_key)
├── forecast/core/rate_limit.py (limiter)
└── forecast/core/exceptions.py (error handling)
```

---

**See also:**
- [API Reference](API_REFERENCE.md) - Complete API documentation
- [Data Format](DATA_FORMAT.md) - Data format requirements
- [Parameters](PARAMETERS.md) - Parameter guide
- [Usage Guide](USAGE_GUIDE.md) - Step-by-step usage
- [Examples](EXAMPLES.md) - Code examples

