# TimesFM-2.0 - Parameters Guide

Complete guide to TimesFM-2.0 parameters, their ranges, defaults, and recommendations.

## Table of Contents

1. [Model Parameters](#model-parameters)
2. [Parameter Ranges](#parameter-ranges)
3. [Default Values](#default-values)
4. [Recommendations](#recommendations)
5. [Inference Parameters](#inference-parameters)
6. [Covariates Parameters](#covariates-parameters)
7. [Parameter Validation](#parameter-validation)
8. [Performance Implications](#performance-implications)
9. [Examples](#examples)

## Model Parameters

### Core Parameters

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `backend` | string | `"cpu"` | `cpu`, `gpu`, `tpu`, `mps` | Computing backend |
| `context_len` | integer | `64` | 32-2048 | Historical window length |
| `horizon_len` | integer | `24` | 1-128 | Forecast horizon length |
| `checkpoint` | string | `"google/timesfm-2.0-500m-pytorch"` | - | HuggingFace model ID |
| `local_model_path` | string | `null` | - | Local model file path |

### Parameter Details

#### `backend`

**Description**: Computing backend for model execution

**Values**:
- `"cpu"`: CPU computation (default, works everywhere)
- `"gpu"`: GPU acceleration (requires CUDA, faster inference)
- `"tpu"`: TPU acceleration (Google Cloud, fastest)
- `"mps"`: Apple Silicon GPU (macOS, faster than CPU)

**Recommendations**:
- **Development**: Use `"cpu"` for simplicity
- **Production**: Use `"gpu"` if available for 2-5x speedup
- **Cloud**: Use `"tpu"` on Google Cloud for best performance

#### `context_len`

**Description**: Length of historical data (context window) used for forecasting

**Range**: 32-2048

**Default**: `64` (optimized for performance)

**Impact**:
- **Larger values**: Better accuracy, slower inference, more memory
- **Smaller values**: Faster inference, less memory, potentially lower accuracy

**Recommendations by Use Case**:

| Use Case | Recommended | Reason |
|----------|-------------|--------|
| Quick forecasts | 64 | Fast, good accuracy |
| High accuracy | 128-256 | Better context, more patterns |
| Long-term patterns | 512-1024 | Capture seasonal/trend patterns |
| Maximum accuracy | 2048 | Best accuracy, slowest |

**Memory Impact**:
- `context_len=64`: ~4GB RAM
- `context_len=256`: ~6GB RAM
- `context_len=1024`: ~12GB RAM

#### `horizon_len`

**Description**: Number of future time steps to forecast

**Range**: 1-128

**Default**: `24`

**Recommendations**:
- **Short-term**: 1-12 (daily/weekly forecasts)
- **Medium-term**: 24-48 (monthly forecasts)
- **Long-term**: 64-128 (quarterly/yearly forecasts)

**Constraint**: Should be ≤ `context_len` for best results

#### `checkpoint`

**Description**: HuggingFace repository ID for model weights

**Options**:
- `"google/timesfm-2.0-500m-pytorch"` (default, PyTorch, all platforms)
- `"google/timesfm-2.0-500m-jax"` (JAX/PAX, x86_64 only)

**Recommendations**:
- **Most users**: Use PyTorch version (default)
- **x86_64 with JAX**: Use JAX version for better performance

#### `local_model_path`

**Description**: Relative path to local model file

**Format**: Path relative to `forecast/models/timesfm20/local/`

**Use Cases**:
- Offline deployment
- Custom model weights
- Faster initialization (no download)

## Parameter Ranges

### Valid Ranges

| Parameter | Minimum | Maximum | Unit |
|-----------|---------|---------|------|
| `context_len` | 32 | 2048 | time points |
| `horizon_len` | 1 | 128 | time points |
| `backend` | - | - | enum (cpu/gpu/tpu/mps) |

### Constraints

- `horizon_len` ≤ `context_len` (recommended)
- `context_len` must be power of 2 or multiple of 32 (for best performance)
- `horizon_len` should be ≤ `context_len / 2` (for best accuracy)

## Default Values

### Initialization Defaults

```json
{
  "backend": "cpu",
  "context_len": 64,
  "horizon_len": 24,
  "checkpoint": "google/timesfm-2.0-500m-pytorch"
}
```

### Inference Defaults

```json
{
  "context_len": 64,
  "horizon_len": 24,
  "use_covariates": false,
  "use_quantiles": false,
  "quantile_indices": [1, 3, 5, 7, 9]
}
```

## Recommendations

### By Data Frequency

**High Frequency (Daily/Hourly)**:
```json
{
  "context_len": 64,
  "horizon_len": 24
}
```

**Medium Frequency (Weekly/Monthly)**:
```json
{
  "context_len": 128,
  "horizon_len": 48
}
```

**Low Frequency (Quarterly/Yearly)**:
```json
{
  "context_len": 256,
  "horizon_len": 96
}
```

### By Accuracy Requirements

**Fast & Good**:
```json
{
  "context_len": 64,
  "horizon_len": 24
}
```

**Balanced**:
```json
{
  "context_len": 128,
  "horizon_len": 48
}
```

**High Accuracy**:
```json
{
  "context_len": 512,
  "horizon_len": 96
}
```

### By Resource Constraints

**Limited Memory (< 4GB)**:
```json
{
  "context_len": 64,
  "horizon_len": 24,
  "backend": "cpu"
}
```

**Standard (4-8GB)**:
```json
{
  "context_len": 128,
  "horizon_len": 48,
  "backend": "cpu"
}
```

**High Memory (> 8GB)**:
```json
{
  "context_len": 512,
  "horizon_len": 96,
  "backend": "gpu"
}
```

## Inference Parameters

### Core Inference Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `context_len` | integer | `64` | Context window length |
| `horizon_len` | integer | `24` | Forecast horizon length |
| `use_covariates` | boolean | `false` | Enable covariates-enhanced forecasting |
| `use_quantiles` | boolean | `false` | Enable quantile forecasting |
| `quantile_indices` | array | `[1, 3, 5, 7, 9]` | Quantile indices to return |

### Inference Parameter Details

#### `use_covariates`

**Description**: Enable covariates-enhanced forecasting

**Default**: `false`

**When to Use**:
- You have relevant covariates (volume, promotions, etc.)
- Covariates improve forecast accuracy
- You have complete covariate data for context + horizon

**Performance Impact**: +20-50% inference time

#### `use_quantiles`

**Description**: Enable quantile forecasting for uncertainty quantification

**Default**: `false`

**When to Use**:
- Need uncertainty estimates
- Risk analysis
- Confidence intervals

**Performance Impact**: +10-20% inference time

#### `quantile_indices`

**Description**: Which quantiles to return

**Default**: `[1, 3, 5, 7, 9]` (Q10, Q30, Q50, Q70, Q90)

**Available Indices**:
- `0`: Legacy mean (skip)
- `1`: Q10 (10th percentile)
- `2`: Q20
- `3`: Q30
- `4`: Q40
- `5`: Q50 (median)
- `6`: Q60
- `7`: Q70
- `8`: Q80
- `9`: Q90 (90th percentile)

**Recommendations**:
- **Basic**: `[5]` (median only)
- **Standard**: `[1, 5, 9]` (Q10, Q50, Q90)
- **Detailed**: `[1, 3, 5, 7, 9]` (default)
- **Full**: `[1, 2, 3, 4, 5, 6, 7, 8, 9]` (all quantiles)

## Covariates Parameters

### Covariates Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `xreg_mode` | string | `"xreg + timesfm"` | Covariate integration mode |
| `ridge` | float | `0.0` | Ridge regression parameter |
| `normalize_xreg_target_per_input` | boolean | `true` | Normalize covariates per input |

### Covariates Parameter Details

#### `xreg_mode`

**Description**: How covariates are integrated with TimesFM

**Values**:
- `"xreg + timesfm"`: Covariates first, then TimesFM (recommended)
- `"timesfm + xreg"`: TimesFM first, then covariates

**Recommendation**: Use `"xreg + timesfm"` (default)

#### `ridge`

**Description**: Ridge regression parameter to prevent overfitting

**Range**: 0.0 to small positive values (e.g., 0.1)

**Default**: `0.0`

**When to Use**:
- Many covariates
- Overfitting concerns
- Small dataset

**Recommendations**:
- **Default**: `0.0` (no regularization)
- **Many covariates**: `0.01` to `0.1`
- **Small dataset**: `0.1` to `0.5`

#### `normalize_xreg_target_per_input`

**Description**: Normalize covariates per input series

**Default**: `true`

**Recommendation**: Keep `true` for stability

## Parameter Validation

### Validation Rules

1. **`context_len`**: Must be between 32 and 2048
2. **`horizon_len`**: Must be between 1 and 128
3. **`backend`**: Must be one of: `cpu`, `gpu`, `tpu`, `mps`
4. **`checkpoint`**: Must be valid HuggingFace repo ID
5. **`quantile_indices`**: Must be integers between 0 and 9

### Validation Errors

**Invalid `context_len`**:
```json
{
  "error": "INVALID_PARAMETERS",
  "message": "context_len must be between 32 and 2048",
  "details": {
    "field": "context_len",
    "value": 10,
    "valid_range": [32, 2048]
  }
}
```

**Invalid `horizon_len`**:
```json
{
  "error": "INVALID_PARAMETERS",
  "message": "horizon_len must be between 1 and 128",
  "details": {
    "field": "horizon_len",
    "value": 200,
    "valid_range": [1, 128]
  }
}
```

## Performance Implications

### Inference Time

| Configuration | Inference Time (CPU) | Inference Time (GPU) |
|---------------|---------------------|---------------------|
| `context_len=64`, basic | 0.1-0.3s | 0.05-0.1s |
| `context_len=64`, covariates | 0.2-0.5s | 0.1-0.2s |
| `context_len=128`, basic | 0.2-0.5s | 0.1-0.2s |
| `context_len=256`, basic | 0.5-1.0s | 0.2-0.4s |
| `context_len=512`, basic | 1.0-2.0s | 0.4-0.8s |

### Memory Usage

| `context_len` | RAM Usage |
|---------------|-----------|
| 64 | ~4GB |
| 128 | ~5GB |
| 256 | ~6GB |
| 512 | ~8GB |
| 1024 | ~12GB |
| 2048 | ~20GB |

### Initialization Time

| Source | First Time | Subsequent |
|--------|------------|------------|
| HuggingFace | 2-5 min | 30-60s |
| Local | 30-60s | 30-60s |
| GPU | 1-3 min | 20-40s |

## Examples

### Basic Configuration

```json
{
  "backend": "cpu",
  "context_len": 64,
  "horizon_len": 24
}
```

### High Accuracy Configuration

```json
{
  "backend": "gpu",
  "context_len": 512,
  "horizon_len": 96
}
```

### Fast Configuration

```json
{
  "backend": "cpu",
  "context_len": 64,
  "horizon_len": 12
}
```

### With Covariates

```json
{
  "backend": "cpu",
  "context_len": 128,
  "horizon_len": 48,
  "use_covariates": true,
  "xreg_mode": "xreg + timesfm",
  "ridge": 0.01
}
```

### With Quantiles

```json
{
  "backend": "cpu",
  "context_len": 64,
  "horizon_len": 24,
  "use_quantiles": true,
  "quantile_indices": [1, 3, 5, 7, 9]
}
```

### Complete Configuration

```json
{
  "backend": "gpu",
  "context_len": 256,
  "horizon_len": 96,
  "use_covariates": true,
  "use_quantiles": true,
  "quantile_indices": [1, 3, 5, 7, 9],
  "xreg_mode": "xreg + timesfm",
  "ridge": 0.01,
  "normalize_xreg_target_per_input": true
}
```

---

**See also:**
- [Architecture](ARCHITECTURE.md) - Model architecture
- [API Reference](API_REFERENCE.md) - Complete API documentation
- [Data Format](DATA_FORMAT.md) - Data format requirements
- [Usage Guide](USAGE_GUIDE.md) - Step-by-step usage
- [Examples](EXAMPLES.md) - Code examples

