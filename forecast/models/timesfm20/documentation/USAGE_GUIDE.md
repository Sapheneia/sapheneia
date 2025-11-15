# TimesFM-2.0 - Usage Guide

Step-by-step usage guide for TimesFM-2.0.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Workflow](#workflow)
3. [Common Use Cases](#common-use-cases)
4. [Best Practices](#best-practices)
5. [Troubleshooting](#troubleshooting)
6. [Performance Tips](#performance-tips)

## Quick Start

### 1. Initialize Model

```bash
curl -X POST http://localhost:8000/forecast/v1/timesfm20/initialization \
  -H "Authorization: Bearer your_secret_key_change_me_in_production" \
  -H "Content-Type: application/json" \
  -d '{
    "backend": "cpu",
    "context_len": 64,
    "horizon_len": 24
  }'
```

### 2. Check Status

```bash
curl http://localhost:8000/forecast/v1/timesfm20/status \
  -H "Authorization: Bearer your_secret_key_change_me_in_production"
```

### 3. Run Inference

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

## Workflow

### Complete Workflow

```
1. Initialize Model
   ↓
2. Check Status (verify "ready")
   ↓
3. Prepare Data (CSV file with date column)
   ↓
4. Run Inference
   ↓
5. Process Results
   ↓
6. (Optional) Shutdown Model
```

### Step-by-Step

#### Step 1: Initialize Model

**Purpose**: Load model weights into memory

**Request**:
```json
{
  "backend": "cpu",
  "context_len": 64,
  "horizon_len": 24
}
```

**Response**:
```json
{
  "message": "Model initialized successfully",
  "model_status": "ready",
  "model_info": {
    "backend": "cpu",
    "context_len": 64,
    "horizon_len": 24
  }
}
```

**Time**: 30-60 seconds (subsequent), 2-5 minutes (first time)

#### Step 2: Check Status

**Purpose**: Verify model is ready for inference

**Request**: `GET /forecast/v1/timesfm20/status`

**Response**:
```json
{
  "model_status": "ready",
  "details": "Source: hf:google/timesfm-2.0-500m-pytorch"
}
```

**Status Values**:
- `uninitialized`: Model not loaded
- `initializing`: Model is loading
- `ready`: Model ready for inference ✅
- `error`: Model encountered an error

#### Step 3: Prepare Data

**Requirements**:
- CSV file with `date` column
- At least `context_len` data points
- Target column identified in data definition

**Example CSV**:
```csv
date,price
2024-01-01,100.0
2024-01-02,101.5
2024-01-03,99.8
...
```

#### Step 4: Run Inference

**Purpose**: Generate forecast

**Request**:
```json
{
  "data_source_url_or_path": "data/uploads/sample_data.csv",
  "data_definition": {
    "price": "target"
  },
  "parameters": {
    "context_len": 64,
    "horizon_len": 24
  }
}
```

**Response**:
```json
{
  "prediction": {
    "point_forecast": [[39808.79, 40049.30, ...]],
    "method": "basic",
    "metadata": {
      "forecast_length": 24
    }
  },
  "visualization_data": {
    "historical_data": [...],
    "dates_future": [...]
  }
}
```

**Time**: 0.1-0.5 seconds (basic), 0.2-0.8 seconds (with covariates)

#### Step 5: Process Results

**Point Forecast**: Main forecast values
```python
point_forecast = result['prediction']['point_forecast'][0]
# [39808.79, 40049.30, 40379.86, ...]
```

**Quantile Forecasts** (if enabled):
```python
quantile_forecast = result['prediction']['quantile_forecast']
# [[Q10 values], [Q30 values], [Q50 values], ...]
```

**Visualization Data**:
```python
historical = result['visualization_data']['historical_data']
future_dates = result['visualization_data']['dates_future']
```

#### Step 6: Shutdown Model (Optional)

**Purpose**: Free memory

**Request**: `POST /forecast/v1/timesfm20/shutdown`

**Response**:
```json
{
  "message": "Model shutdown successfully",
  "model_status": "uninitialized"
}
```

## Common Use Cases

### Use Case 1: Basic Forecasting

**Scenario**: Simple time series forecast without covariates

**Steps**:
1. Initialize model
2. Prepare CSV with target column
3. Run inference with basic parameters

**Example**:
```json
{
  "data_source_url_or_path": "data/uploads/sales.csv",
  "data_definition": {
    "sales": "target"
  },
  "parameters": {
    "context_len": 64,
    "horizon_len": 24
  }
}
```

### Use Case 2: Forecasting with Covariates

**Scenario**: Forecast with additional features (volume, promotions, etc.)

**Steps**:
1. Initialize model
2. Prepare CSV with target + covariates
3. Run inference with `use_covariates: true`

**Example**:
```json
{
  "data_source_url_or_path": "data/uploads/sales_with_covariates.csv",
  "data_definition": {
    "sales": "target",
    "volume": "dynamic_numerical",
    "promotion": "dynamic_categorical"
  },
  "parameters": {
    "context_len": 64,
    "horizon_len": 24,
    "use_covariates": true
  }
}
```

### Use Case 3: Quantile Forecasting

**Scenario**: Need uncertainty estimates and confidence intervals

**Steps**:
1. Initialize model
2. Prepare data
3. Run inference with `use_quantiles: true`

**Example**:
```json
{
  "data_source_url_or_path": "data/uploads/price.csv",
  "data_definition": {
    "price": "target"
  },
  "parameters": {
    "context_len": 64,
    "horizon_len": 24,
    "use_quantiles": true,
    "quantile_indices": [1, 3, 5, 7, 9]
  }
}
```

### Use Case 4: High Accuracy Forecasting

**Scenario**: Maximum accuracy requirements

**Steps**:
1. Initialize model with larger `context_len`
2. Prepare data with sufficient history
3. Run inference with optimized parameters

**Example**:
```json
{
  "backend": "gpu",
  "context_len": 512,
  "horizon_len": 96
}
```

### Use Case 5: Batch Forecasting

**Scenario**: Forecast multiple series

**Approach**: Run inference multiple times (one per series)

**Example**:
```python
series_list = ["series1.csv", "series2.csv", "series3.csv"]
results = []

for series in series_list:
    result = run_inference(
        data_source=series,
        data_definition={"value": "target"},
        parameters={"context_len": 64, "horizon_len": 24}
    )
    results.append(result)
```

## Best Practices

### Model Initialization

1. **Initialize Once**: Initialize model once and reuse for multiple inferences
2. **Check Status**: Always check status before running inference
3. **Handle Errors**: Implement retry logic for initialization failures
4. **Monitor Memory**: Monitor memory usage when loading large models

### Data Preparation

1. **Clean Data**: Remove outliers and handle missing values
2. **Sufficient Data**: Have at least 2x `context_len` data points
3. **Consistent Format**: Ensure date format is consistent
4. **Validate Types**: Verify column types match data definition

### Parameter Selection

1. **Start Simple**: Begin with default parameters
2. **Optimize Gradually**: Adjust parameters based on results
3. **Consider Resources**: Choose parameters based on available resources
4. **Test Performance**: Test different parameter combinations

### Inference

1. **Reuse Model**: Don't reinitialize model for each inference
2. **Batch When Possible**: Process multiple requests together
3. **Monitor Performance**: Track inference times
4. **Handle Errors**: Implement proper error handling

### Covariates

1. **Relevant Features**: Only include relevant covariates
2. **Complete Data**: Ensure covariates cover required periods
3. **Validate Types**: Correctly identify static vs dynamic features
4. **Test Impact**: Test with and without covariates

### Quantiles

1. **Select Indices**: Choose quantile indices based on needs
2. **Standard Set**: Use `[1, 3, 5, 7, 9]` for standard uncertainty bands
3. **Performance**: Quantiles add 10-20% to inference time
4. **Visualization**: Use quantile bands for visualization

## Troubleshooting

### Model Not Initializing

**Symptoms**:
- Status remains `"initializing"`
- Initialization times out
- Memory errors

**Solutions**:
- Check available memory (need 4GB+)
- Verify internet connection (HuggingFace download)
- Try smaller `context_len`
- Check logs for errors

### Inference Fails

**Symptoms**:
- `MODEL_NOT_INITIALIZED` error
- Data errors
- Timeout errors

**Solutions**:
- Verify model status is `"ready"`
- Check data file exists and is readable
- Validate data format and definition
- Ensure sufficient data points

### Poor Forecast Accuracy

**Symptoms**:
- Forecasts don't match expectations
- High forecast errors

**Solutions**:
- Increase `context_len` for more history
- Add relevant covariates
- Check data quality
- Try different parameters

### Slow Performance

**Symptoms**:
- Long inference times
- Timeout errors

**Solutions**:
- Use GPU backend if available
- Reduce `context_len`
- Disable quantiles if not needed
- Optimize data size

### Memory Issues

**Symptoms**:
- Out of memory errors
- System slowdown

**Solutions**:
- Reduce `context_len`
- Use CPU backend (less memory)
- Process smaller datasets
- Increase system memory

## Performance Tips

### Speed Optimization

1. **Use GPU**: 2-5x faster inference
2. **Optimize Context**: Use smallest `context_len` that gives good accuracy
3. **Disable Quantiles**: If not needed, saves 10-20% time
4. **Batch Processing**: Process multiple requests efficiently

### Accuracy Optimization

1. **Increase Context**: Larger `context_len` captures more patterns
2. **Add Covariates**: Relevant covariates improve accuracy
3. **More Data**: More historical data improves results
4. **Tune Parameters**: Experiment with different parameter combinations

### Memory Optimization

1. **Smaller Context**: Reduce `context_len` to save memory
2. **CPU Backend**: Uses less memory than GPU
3. **Process in Batches**: Don't load all data at once
4. **Shutdown When Done**: Free memory when not using model

### Resource Management

1. **Monitor Usage**: Track CPU, memory, and GPU usage
2. **Scale Appropriately**: Choose resources based on workload
3. **Reuse Model**: Don't reinitialize unnecessarily
4. **Clean Up**: Shutdown model when done

---

**See also:**
- [Architecture](ARCHITECTURE.md) - Model architecture
- [API Reference](API_REFERENCE.md) - Complete API documentation
- [Data Format](DATA_FORMAT.md) - Data format requirements
- [Parameters](PARAMETERS.md) - Parameter guide
- [Examples](EXAMPLES.md) - Code examples

