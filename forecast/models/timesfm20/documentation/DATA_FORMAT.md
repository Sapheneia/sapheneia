# TimesFM-2.0 - Data Format Guide

Complete guide to data formats and requirements for TimesFM-2.0.

## Table of Contents

1. [Data Source Types](#data-source-types)
2. [CSV Format Requirements](#csv-format-requirements)
3. [Data Definition Format](#data-definition-format)
4. [Column Types](#column-types)
5. [Validation Rules](#validation-rules)
6. [Path Handling](#path-handling)
7. [Size Limits](#size-limits)
8. [Examples](#examples)
9. [Best Practices](#best-practices)

## Data Source Types

### Local Files

**Format**: File path (relative or absolute)

**Venv Mode:**
```json
{
  "data_source_url_or_path": "data/uploads/sample_data.csv"
}
```

**Docker Mode:**
```json
{
  "data_source_url_or_path": "/app/data/uploads/sample_data.csv"
}
```

**Supported Formats:**
- `.csv` - Comma-separated values
- Must be readable by pandas

### HTTP/HTTPS URLs

**Format**: Full URL

```json
{
  "data_source_url_or_path": "http://example.com/data.csv"
}
```

**Requirements:**
- URL must be publicly accessible
- Server must return CSV content
- Response must be valid CSV format

### Future Support

- **S3**: `s3://bucket/path/to/file.csv` (planned)
- **GCS**: `gs://bucket/path/to/file.csv` (planned)

## CSV Format Requirements

### Required Columns

**`date` Column (Required)**
- Must be present in CSV
- Will be converted to datetime
- Supports various date formats:
  - `YYYY-MM-DD`
  - `YYYY-MM-DD HH:MM:SS`
  - `MM/DD/YYYY`
  - ISO 8601 formats

### Column Structure

```
date,price,volume,promotion
2024-01-01,100.0,1000,active
2024-01-02,101.5,1100,inactive
2024-01-03,99.8,950,active
...
```

### Data Types

- **Numeric**: Integer or float values
- **Categorical**: String values
- **Date**: Automatically converted from `date` column

### Encoding

- **UTF-8**: Recommended (default)
- Other encodings: May work but not guaranteed

## Data Definition Format

### Structure

The `data_definition` maps column names to their types:

```json
{
  "data_definition": {
    "price": "target",
    "volume": "dynamic_numerical",
    "promotion": "dynamic_categorical",
    "base_price": "static_numerical",
    "region": "static_categorical"
  }
}
```

### Requirements

- **Exactly One Target**: Must have exactly one column marked as `"target"`
- **Valid Types**: All types must be from allowed list
- **Column Names**: Must match CSV column names exactly (case-sensitive)

## Column Types

### Target

**Type**: `"target"`

**Description**: The variable to forecast (required, exactly one)

**Example:**
```json
{
  "price": "target"
}
```

**Requirements:**
- Must be numeric
- Must have sufficient data points (≥ context_len)
- Cannot be used with other types

### Dynamic Numerical

**Type**: `"dynamic_numerical"`

**Description**: Time-varying numerical features

**Example:**
```json
{
  "volume": "dynamic_numerical",
  "temperature": "dynamic_numerical"
}
```

**Requirements:**
- Must be numeric
- Must cover context + horizon periods
- Values change over time

**Use Cases:**
- Sales volume
- Temperature
- Market indicators
- Any time-varying numeric feature

### Dynamic Categorical

**Type**: `"dynamic_categorical"`

**Description**: Time-varying categorical features

**Example:**
```json
{
  "promotion": "dynamic_categorical",
  "day_of_week": "dynamic_categorical"
}
```

**Requirements:**
- Must be string or categorical
- Must cover context + horizon periods
- Values change over time

**Use Cases:**
- Promotion status (active/inactive)
- Day of week
- Season
- Any time-varying categorical feature

### Static Numerical

**Type**: `"static_numerical"`

**Description**: Per-series numerical features (constant across time)

**Example:**
```json
{
  "base_price": "static_numerical",
  "region_code": "static_numerical"
}
```

**Requirements:**
- Must be numeric
- Single value per series
- Constant across all time points

**Use Cases:**
- Base price
- Region code
- Product category code
- Any per-series numeric constant

### Static Categorical

**Type**: `"static_categorical"`

**Description**: Per-series categorical features (constant across time)

**Example:**
```json
{
  "region": "static_categorical",
  "product_category": "static_categorical"
}
```

**Requirements:**
- Must be string or categorical
- Single value per series
- Constant across all time points

**Use Cases:**
- Region name
- Product category
- Store type
- Any per-series categorical constant

## Validation Rules

### Data Length

- **Minimum**: Must have at least `context_len` data points
- **Recommended**: Have more than `context_len` for better results
- **Maximum**: No hard limit, but very large datasets may be slow

### Data Quality

- **No Missing Values**: Target column must not have missing values
- **No Infinite Values**: All numeric values must be finite
- **Valid Dates**: Date column must be parseable
- **Consistent Types**: Column types must match data definition

### Covariates Validation

**Dynamic Covariates:**
- Must cover context + horizon periods
- Cannot have missing values in required range
- Must match target series length

**Static Covariates:**
- Must have exactly one value per series
- Cannot vary across time points

## Path Handling

### Venv Mode

Use relative paths from project root:

```json
{
  "data_source_url_or_path": "data/uploads/sample_data.csv"
}
```

**Base Directory**: Project root (`sapheneia/`)

**Allowed Paths:**
- `data/uploads/*`
- `data/results/*`
- Other paths within project (security validated)

### Docker Mode

Use absolute paths:

```json
{
  "data_source_url_or_path": "/app/data/uploads/sample_data.csv"
}
```

**Base Directory**: `/app/`

**Allowed Paths:**
- `/app/data/uploads/*`
- `/app/data/results/*`
- Other paths within container (security validated)

### Security

- **Path Traversal Protection**: Automatically prevents `../` attacks
- **Path Validation**: All paths validated before access
- **Allowed Directories**: Restricted to safe directories

## Size Limits

### File Size

- **Maximum Upload Size**: 50MB (configurable)
- **Recommended**: < 10MB for faster processing
- **Very Large Files**: Consider preprocessing or sampling

### Data Points

- **Minimum**: `context_len` points (typically 64)
- **Recommended**: 2-3x `context_len` for better results
- **Maximum**: No hard limit, but performance degrades with very large datasets

### Memory Considerations

- **RAM Usage**: ~4GB for TimesFM-2.0 model
- **Data Loading**: Additional memory for data processing
- **Large Datasets**: May require more memory

## Examples

### Basic Example (No Covariates)

**CSV (`sample_data.csv`):**
```csv
date,price
2024-01-01,100.0
2024-01-02,101.5
2024-01-03,99.8
...
```

**Data Definition:**
```json
{
  "price": "target"
}
```

### With Dynamic Numerical Covariates

**CSV (`sales_data.csv`):**
```csv
date,price,volume
2024-01-01,100.0,1000
2024-01-02,101.5,1100
2024-01-03,99.8,950
...
```

**Data Definition:**
```json
{
  "price": "target",
  "volume": "dynamic_numerical"
}
```

### With Dynamic Categorical Covariates

**CSV (`promo_data.csv`):**
```csv
date,price,promotion
2024-01-01,100.0,active
2024-01-02,101.5,inactive
2024-01-03,99.8,active
...
```

**Data Definition:**
```json
{
  "price": "target",
  "promotion": "dynamic_categorical"
}
```

### With Static Covariates

**CSV (`regional_data.csv`):**
```csv
date,price,region,base_price
2024-01-01,100.0,North,95.0
2024-01-02,101.5,North,95.0
2024-01-03,99.8,North,95.0
...
```

**Data Definition:**
```json
{
  "price": "target",
  "region": "static_categorical",
  "base_price": "static_numerical"
}
```

### Complete Example (All Covariate Types)

**CSV (`complete_data.csv`):**
```csv
date,price,volume,promotion,region,base_price
2024-01-01,100.0,1000,active,North,95.0
2024-01-02,101.5,1100,inactive,North,95.0
2024-01-03,99.8,950,active,North,95.0
...
```

**Data Definition:**
```json
{
  "price": "target",
  "volume": "dynamic_numerical",
  "promotion": "dynamic_categorical",
  "region": "static_categorical",
  "base_price": "static_numerical"
}
```

## Best Practices

### Data Preparation

1. **Clean Data**: Remove outliers and handle missing values before upload
2. **Consistent Format**: Ensure date format is consistent
3. **Sufficient Data**: Have at least 2x `context_len` data points
4. **Validate Types**: Ensure numeric columns are actually numeric

### Column Naming

1. **Descriptive Names**: Use clear, descriptive column names
2. **No Special Characters**: Avoid special characters in column names
3. **Consistent Case**: Use consistent case (recommend lowercase)

### Covariates

1. **Relevant Features**: Only include covariates that are relevant
2. **Complete Data**: Ensure covariates cover required time periods
3. **Static vs Dynamic**: Correctly identify static vs dynamic features
4. **Categorical Encoding**: Use meaningful categorical values

### File Management

1. **Organize Files**: Keep data files organized in `data/uploads/`
2. **Naming Convention**: Use descriptive file names
3. **Version Control**: Don't commit large data files to git
4. **Backup**: Keep backups of important data files

### Performance

1. **File Size**: Keep files under 10MB when possible
2. **Data Sampling**: For very large datasets, consider sampling
3. **Preprocessing**: Preprocess data to reduce size if needed
4. **Caching**: Reuse data files when possible

---

**See also:**
- [API Reference](API_REFERENCE.md) - Complete API documentation
- [Parameters](PARAMETERS.md) - Parameter guide
- [Usage Guide](USAGE_GUIDE.md) - Step-by-step usage
- [Examples](EXAMPLES.md) - Code examples

