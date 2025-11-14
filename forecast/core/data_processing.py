"""
Data Processing and Validation Module

This module provides comprehensive data processing capabilities for TimesFM,
including CSV loading, covariate preparation, and data validation.

Key Features:
- CSV data loading with flexible column configuration
- Automatic data type inference and conversion
- Covariates data preparation and validation
- Data structure formatting for TimesFM input requirements
- Support for dynamic and static, numerical and categorical covariates
"""

import pandas as pd
import numpy as np
import json
import logging
from typing import Dict, List, Union, Optional, Tuple, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class DataProcessor:
    """
    Handles data loading, processing, and validation for TimesFM forecasting.
    
    This class provides methods to load CSV data, process covariates according
    to TimesFM requirements, and validate data structures before forecasting.
    
    Example:
        >>> processor = DataProcessor()
        >>> data = processor.load_csv_data("data.csv", data_definition)
        >>> inputs, covariates = processor.prepare_forecast_data(
        ...     data, context_len=100, horizon_len=24
        ... )
    """
    
    def __init__(self):
        """Initialize the DataProcessor."""
        self.data = None
        self.data_definition = None
        self.processed_data = None
        
    def load_csv_data(
        self, 
        csv_file_path: str, 
        data_definition: Union[str, Dict[str, str]]
    ) -> pd.DataFrame:
        """
        Load CSV data with proper column type conversion based on data definition.
        
        Args:
            csv_file_path: Path to the CSV file
            data_definition: Either JSON file path or dictionary defining column types
            
        Returns:
            Loaded and processed DataFrame
            
        Raises:
            FileNotFoundError: If CSV or JSON file not found
            ValueError: If data definition is invalid
        """
        logger.info(f"Loading CSV data from: {csv_file_path}")
        
        # Load data definition
        if isinstance(data_definition, str):
            with open(data_definition, 'r') as f:
                self.data_definition = json.load(f)
        else:
            self.data_definition = data_definition.copy()
        
        logger.info(f"Data definition: {self.data_definition}")
        
        # Load CSV
        try:
            self.data = pd.read_csv(csv_file_path).dropna(axis=0)
            logger.info(f"Loaded CSV with shape: {self.data.shape}")
            logger.info(f"Columns: {list(self.data.columns)}")
        except FileNotFoundError:
            raise FileNotFoundError(f"CSV file not found: {csv_file_path}")
        
        # Validate that 'date' column exists
        if 'date' not in self.data.columns:
            raise ValueError("CSV file must contain a 'date' column as the first column")
        
        # Convert date column
        self.data['date'] = pd.to_datetime(self.data['date'])
        logger.info(f"Date range: {self.data['date'].min()} to {self.data['date'].max()}")
        
        # Apply data type conversions based on definition
        self._apply_data_types()
        
        # Validate data definition
        self._validate_data_definition()
        
        logger.info("✅ CSV data loaded and processed successfully")
        return self.data.copy()
    
    def _apply_data_types(self) -> None:
        """Apply appropriate data types based on the data definition."""
        logger.info("Applying data type conversions...")
        
        for column, data_type in self.data_definition.items():
            if column not in self.data.columns:
                logger.warning(f"Column '{column}' in data definition not found in CSV")
                continue
            
            try:
                if data_type in ['target', 'dynamic_numerical', 'static_numerical']:
                    # Convert to float
                    self.data[column] = pd.to_numeric(self.data[column], errors='coerce')
                    logger.info(f"Converted '{column}' to numerical (float)")
                    
                elif data_type in ['dynamic_categorical', 'static_categorical']:
                    # Convert to string
                    self.data[column] = self.data[column].astype(str)
                    logger.info(f"Converted '{column}' to categorical (string)")
                    
                else:
                    logger.warning(f"Unknown data type '{data_type}' for column '{column}'")
                    
            except Exception as e:
                logger.error(f"Failed to convert column '{column}': {str(e)}")
                raise
    
    def _validate_data_definition(self) -> None:
        """Validate the data definition against the loaded data."""
        logger.info("Validating data definition...")
        
        # Check for required data types
        target_columns = [col for col, dtype in self.data_definition.items() if dtype == 'target']
        if not target_columns:
            raise ValueError("Data definition must contain at least one 'target' column")
        
        if len(target_columns) > 1:
            logger.warning(f"Multiple target columns found: {target_columns}. Using first one for univariate forecasting.")
        
        # Validate column existence
        missing_columns = set(self.data_definition.keys()) - set(self.data.columns)
        if missing_columns:
            raise ValueError(f"Columns defined in data_definition but missing from CSV: {missing_columns}")
        
        # Check for data quality issues
        for column in target_columns:
            if self.data[column].isnull().any():
                null_count = self.data[column].isnull().sum()
                logger.warning(f"Target column '{column}' has {null_count} null values")
        
        logger.info("✅ Data definition validation passed")
    
    def prepare_forecast_data(
        self,
        data: pd.DataFrame,
        context_len: int,
        horizon_len: int,
        target_column: Optional[str] = None
    ) -> Tuple[List[float], Dict[str, Any]]:
        """
        Prepare data for TimesFM forecasting with covariates.
        
        Args:
            data: Input DataFrame
            context_len: Length of context window for forecasting
            horizon_len: Length of forecast horizon
            target_column: Target column name (auto-detected if None)
            
        Returns:
            Tuple of (target_inputs, covariates_dict)
            
        Raises:
            ValueError: If insufficient data or invalid configuration
        """
        logger.info(f"Preparing forecast data (context: {context_len}, horizon: {horizon_len})")
        
        # Auto-detect target column if not specified
        if target_column is None:
            target_columns = [col for col, dtype in self.data_definition.items() if dtype == 'target']
            if not target_columns:
                raise ValueError("No target column found in data definition")
            target_column = target_columns[0]
            logger.info(f"Using target column: {target_column}")
        
        # Validate data length - only need context_len for the data
        if len(data) < context_len:
            raise ValueError(f"Insufficient data: need {context_len} points, have {len(data)}")
        
        # Prepare target inputs using the most recent context window
        target_series = data[target_column].values
        context_start = max(0, len(data) - context_len)
        context_end = len(data)  # Use last context_len periods
        target_inputs = target_series[context_start:context_end].tolist()
        
        logger.info(f"Target data preparation:")
        logger.info(f"  - Target column: {target_column}")
        logger.info(f"  - Context start index: {context_start}")
        logger.info(f"  - Context end index: {context_end}")
        logger.info(f"  - Target inputs length: {len(target_inputs)}")
        logger.info(f"  - Target range: {min(target_inputs):.2f} - {max(target_inputs):.2f}")
        
        # Prepare covariates
        covariates = self._prepare_covariates(data, context_len, horizon_len)
        
        logger.info(f"✅ Prepared forecast data:")
        logger.info(f"  Target inputs length: {len(target_inputs)}")
        logger.info(f"  Target range: {min(target_inputs):.2f} - {max(target_inputs):.2f}")
        logger.info(f"  Covariates: {list(covariates.keys())}")
        
        return target_inputs, covariates
    
    def _prepare_covariates(
        self, 
        data: pd.DataFrame, 
        context_len: int, 
        horizon_len: int
    ) -> Dict[str, Dict[str, List]]:
        """
        Prepare covariates data structure for TimesFM.
        
        Args:
            data: Input DataFrame
            context_len: Context window length
            horizon_len: Forecast horizon length
            
        Returns:
            Dictionary containing organized covariates
        """
        covariates = {
            'dynamic_numerical_covariates': {},
            'dynamic_categorical_covariates': {},
            'static_numerical_covariates': {},
            'static_categorical_covariates': {}
        }
        
        # For dynamic covariates, we need context_len + horizon_len total periods
        # Context period: last context_len periods of available data
        # Horizon period: horizon_len periods (padded with last known values)
        total_len = context_len + horizon_len
        
        logger.info(f"Covariate preparation debug:")
        logger.info(f"  - Data length: {len(data)}")
        logger.info(f"  - Context length: {context_len}")
        logger.info(f"  - Horizon length: {horizon_len}")
        logger.info(f"  - Total periods needed: {total_len}")
        logger.info(f"  - Data date range: {data['date'].min()} to {data['date'].max()}")
        logger.info(f"  - Context period: last {context_len} periods of data")
        logger.info(f"  - Horizon period: {horizon_len} periods (padded with last known values)")

        for column, data_type in self.data_definition.items():
            if column == 'date' or data_type == 'target':
                continue
            
            if data_type == 'dynamic_numerical':
                # Dynamic numerical: need context + horizon values
                # Context: last context_len periods of available data
                # Horizon: horizon_len periods (padded with last known value)
                
                if len(data) < context_len:
                    logger.warning(f"Insufficient data for dynamic covariate '{column}': need {context_len} for context, have {len(data)}")
                    continue
                
                # Get context values (last context_len periods)
                context_values = data[column].iloc[-context_len:].tolist()
                
                # Get horizon values (pad with last known value)
                last_value = context_values[-1]
                horizon_values = [last_value] * horizon_len
                
                # Combine context + horizon
                values = context_values + horizon_values
                
                covariates['dynamic_numerical_covariates'][column] = [values]
                logger.info(f"Added dynamic numerical covariate '{column}': {len(values)} values")
                logger.info(f"  - Context period: {len(context_values)} values (last {context_len} periods)")
                logger.info(f"  - Horizon period: {len(horizon_values)} values (padded with {last_value})")
                
            elif data_type == 'dynamic_categorical':
                # Dynamic categorical: need context + horizon values
                # Context: last context_len periods of available data
                # Horizon: horizon_len periods (padded with last known value)
                
                if len(data) < context_len:
                    logger.warning(f"Insufficient data for dynamic covariate '{column}': need {context_len} for context, have {len(data)}")
                    continue
                
                # Get context values (last context_len periods)
                context_values = data[column].astype(str).iloc[-context_len:].tolist()
                
                # Get horizon values (pad with last known value)
                last_value = context_values[-1]
                horizon_values = [last_value] * horizon_len
                
                # Combine context + horizon
                values = context_values + horizon_values
                
                covariates['dynamic_categorical_covariates'][column] = [values]
                logger.info(f"Added dynamic categorical covariate '{column}': {len(values)} values")
                logger.info(f"  - Context period: {len(context_values)} values (last {context_len} periods)")
                logger.info(f"  - Horizon period: {len(horizon_values)} values (padded with '{last_value}')")
                
            elif data_type == 'static_numerical':
                # Static numerical: single value per time series
                value = float(data[column].iloc[0])
                covariates['static_numerical_covariates'][column] = [value]
                logger.info(f"Added static numerical covariate '{column}': {value}")
                
            elif data_type == 'static_categorical':
                # Static categorical: single value per time series
                value = str(data[column].iloc[0])
                covariates['static_categorical_covariates'][column] = [value]
                logger.info(f"Added static categorical covariate '{column}': {value}")
        
        # Remove empty covariate types
        covariates = {k: v for k, v in covariates.items() if v}
        
        return covariates
    
    def get_data_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the loaded data.
        
        Returns:
            Dictionary containing data summary statistics
        """
        if self.data is None:
            return {"status": "No data loaded"}
        
        summary = {
            "status": "loaded",
            "shape": self.data.shape,
            "date_range": {
                "start": str(self.data['date'].min().date()),
                "end": str(self.data['date'].max().date()),
                "total_periods": len(self.data)
            },
            "columns": list(self.data.columns),
            "data_definition": self.data_definition
        }
        
        # Add column-specific statistics
        column_stats = {}
        for column in self.data.columns:
            if column == 'date':
                continue
                
            col_data = self.data[column]
            data_type = self.data_definition.get(column, 'unknown')
            
            if data_type in ['target', 'dynamic_numerical', 'static_numerical']:
                column_stats[column] = {
                    "type": data_type,
                    "dtype": str(col_data.dtype),
                    "min": float(col_data.min()) if not col_data.isnull().all() else None,
                    "max": float(col_data.max()) if not col_data.isnull().all() else None,
                    "mean": float(col_data.mean()) if not col_data.isnull().all() else None,
                    "null_count": int(col_data.isnull().sum())
                }
            else:
                column_stats[column] = {
                    "type": data_type,
                    "dtype": str(col_data.dtype),
                    "unique_values": int(col_data.nunique()),
                    "null_count": int(col_data.isnull().sum()),
                    "sample_values": col_data.dropna().unique()[:5].tolist()
                }
        
        summary["column_statistics"] = column_stats
        return summary
    
    def validate_forecast_inputs(
        self, 
        inputs: List[float], 
        covariates: Dict[str, Any], 
        context_len: int, 
        horizon_len: int
    ) -> bool:
        """
        Validate that forecast inputs are properly formatted for TimesFM.
        
        Args:
            inputs: Target time series inputs
            covariates: Covariates dictionary
            context_len: Expected context length
            horizon_len: Expected horizon length
            
        Returns:
            True if validation passes
            
        Raises:
            ValueError: If validation fails
        """
        logger.info("Validating forecast inputs...")
        
        # Validate inputs length
        if len(inputs) != context_len:
            raise ValueError(f"Input length {len(inputs)} doesn't match context_len {context_len}")
        
        # Validate inputs are numeric
        if not all(isinstance(x, (int, float)) and not np.isnan(x) for x in inputs):
            raise ValueError("All inputs must be numeric and non-NaN")
        
        # Validate covariates structure
        total_len = context_len + horizon_len
        
        for cov_type, cov_dict in covariates.items():
            if cov_type in ['dynamic_numerical_covariates', 'dynamic_categorical_covariates']:
                for name, values_list in cov_dict.items():
                    if len(values_list) != 1:
                        raise ValueError(f"Dynamic covariate '{name}' must have exactly 1 time series")
                    if len(values_list[0]) != total_len:
                        raise ValueError(f"Dynamic covariate '{name}' must have {total_len} values, got {len(values_list[0])}")
            
            elif cov_type in ['static_numerical_covariates', 'static_categorical_covariates']:
                for name, values_list in cov_dict.items():
                    if len(values_list) != 1:
                        raise ValueError(f"Static covariate '{name}' must have exactly 1 value")
        
        logger.info("✅ Forecast inputs validation passed")
        return True
    
    def create_sample_data_definition(self, output_path: str) -> None:
        """
        Create a sample data definition JSON file.
        
        Args:
            output_path: Path where to save the sample JSON file
        """
        sample_definition = {
            "btc_price": "target",
            "eth_price": "dynamic_numerical", 
            "vix_index": "dynamic_numerical",
            "sp500_price": "dynamic_numerical",
            "quarter": "dynamic_categorical",
            "asset_category": "static_categorical",
            "base_price": "static_numerical"
        }
        
        with open(output_path, 'w') as f:
            json.dump(sample_definition, f, indent=2)
        
        logger.info(f"Sample data definition saved to: {output_path}")
        print(f"Sample data definition structure:")
        print(json.dumps(sample_definition, indent=2))


def prepare_visualization_data(
    processed_data: pd.DataFrame,
    target_inputs: Union[List[float], List[List[float]]],
    target_column: str,
    context_len: int,
    horizon_len: int,
    extended_data: Optional[pd.DataFrame] = None
) -> Dict[str, Any]:
    """
    Centralized function to prepare visualization data from processed data.
    
    This function creates the visualization data structure used by both
    the webapp and notebook for consistent data handling.
    
    Args:
        processed_data: Processed DataFrame with date column
        target_inputs: Target input data used for forecasting (flattenable to a single series)
        target_column: Name of the target column
        context_len: Context length used for forecasting
        horizon_len: Horizon length for forecasting
        
    Returns:
        Dictionary containing visualization data with keys:
        - 'historical_data': Context window used for forecasting (chronologically ordered)
        - 'dates_historical': Corresponding historical dates
        - 'dates_future': Future dates aligned with the forecast horizon
        - 'target_name': Name of the target column
        - 'actual_future': Optional actual values for the forecast horizon (if available)
    """

    if processed_data.empty:
        return {
            'historical_data': [],
            'dates_historical': [],
            'dates_future': [],
            'target_name': target_column,
            'actual_future': []
        }

    # Work on a chronologically sorted copy to ensure alignment
    df = processed_data.dropna(axis=0).sort_values('date').reset_index(drop=True)

    # Flatten target inputs (they may arrive as List[List[float]] or List[float])
    if isinstance(target_inputs, (list, tuple)) and target_inputs:
        if isinstance(target_inputs[0], (list, tuple, np.ndarray)):
            target_inputs_flat = list(target_inputs[0])
        else:
            target_inputs_flat = list(target_inputs)
    else:
        target_inputs_flat = []

    # Respect the actual context length used
    context_len_effective = len(target_inputs_flat) or context_len
    available_len = len(df)

    # Use target_inputs as historical data to ensure exact alignment with forecasting
    # This guarantees that the historical data in visualization matches what was used for forecasting
    if target_inputs_flat:
        historical_slice = list(map(float, target_inputs_flat))
        
        # For dates, we need to find the corresponding dates for the target_inputs
        # Since target_inputs represents the last context_len periods used for forecasting,
        # we need to find the dates that correspond to those exact data points
        if len(df) >= context_len_effective:
            # Get the dates for the last context_len periods (same as target_inputs)
            dates_historical = df['date'].iloc[-context_len_effective:].tolist()
        else:
            # If we don't have enough data, use what we have
            dates_historical = df['date'].tolist()
            
        logger.info(f"Using target_inputs for historical data to ensure forecasting alignment")
    else:
        # Fallback to data-based extraction if target_inputs not available
        if len(df) >= context_len_effective:
            historical_slice = df[target_column].iloc[-context_len_effective:].astype(float).tolist()
            dates_historical = df['date'].iloc[-context_len_effective:].tolist()
        else:
            historical_slice = df[target_column].astype(float).tolist()
            dates_historical = df['date'].tolist()
            
        logger.info(f"Using data-based extraction for historical data")
    
    logger.info(f"Visualization data preparation:")
    logger.info(f"  - Processed data shape: {df.shape}")
    logger.info(f"  - Target column: {target_column}")
    logger.info(f"  - Context length effective: {context_len_effective}")
    logger.info(f"  - Historical slice length: {len(historical_slice)}")
    logger.info(f"  - Target inputs flat length: {len(target_inputs_flat)}")
    logger.info(f"  - Dates historical length: {len(dates_historical)}")
    logger.info(f"  - Historical data range: {min(historical_slice) if historical_slice else 'N/A'} to {max(historical_slice) if historical_slice else 'N/A'}")
    if dates_historical:
        logger.info(f"  - First historical date: {dates_historical[0]}")
        logger.info(f"  - Last historical date: {dates_historical[-1]}")

    # For future dates, we need to generate them since we only have context data
    # Extract actual future values when present (useful for overlaying actuals)
    # The actual future values should start from the day after the last historical date
    # Use extended_data if available (includes horizon period), otherwise use df
    data_for_future_extraction = extended_data if extended_data is not None else df
    
    if len(data_for_future_extraction) > context_len_effective and dates_historical:
        # Find the last historical date (this is the context end date)
        last_historical_date = dates_historical[-1]
        
        # Find data points that come after the last historical date
        future_mask = data_for_future_extraction['date'] > last_historical_date
        future_data = data_for_future_extraction[future_mask]
        
        if len(future_data) > 0:
            # Take only the first horizon_len periods of future data
            future_slice = future_data[target_column].iloc[:horizon_len].astype(float).tolist()
            dates_future = future_data['date'].iloc[:horizon_len].tolist()
            
            logger.info(f"Actual future values extracted:")
            logger.info(f"  - Data for extraction length: {len(data_for_future_extraction)}")
            logger.info(f"  - Context length effective: {context_len_effective}")
            logger.info(f"  - Last historical date (context end): {last_historical_date}")
            logger.info(f"  - Future data available: {len(future_data)} periods")
            logger.info(f"  - Future slice length: {len(future_slice)}")
            logger.info(f"  - Future dates length: {len(dates_future)}")
            if future_slice and dates_future:
                logger.info(f"  - Future values range: {min(future_slice):.4f} to {max(future_slice):.4f}")
                logger.info(f"  - First future date: {dates_future[0]}")
                logger.info(f"  - Last future date: {dates_future[-1]}")
        else:
            future_slice = []
            dates_future = []
            logger.info("No actual future values available - no data after last historical date")
    else:
        # No actual future values available
        future_slice = []
        dates_future = []
        logger.info("No actual future values available - data doesn't extend beyond context period")

    if len(dates_future) < horizon_len:
        # Generate future dates if the dataset stops at the forecast boundary
        inferred_delta: Optional[pd.Timedelta] = None
        if len(dates_historical) >= 2:
            inferred_delta = dates_historical[-1] - dates_historical[-2]
        last_date = dates_historical[-1]
        if hasattr(last_date, 'to_pydatetime'):
            last_date = last_date.to_pydatetime()
        elif isinstance(last_date, np.datetime64):
            last_date = pd.to_datetime(last_date).to_pydatetime()

        step = inferred_delta if isinstance(inferred_delta, pd.Timedelta) and inferred_delta != pd.Timedelta(0) else timedelta(days=1)
        dates_future = [last_date + step * (i + 1) for i in range(horizon_len)]
        future_slice = []  # No actual future data in this case

    visualization_data = {
        'historical_data': historical_slice,
        'dates_historical': [d.isoformat() if hasattr(d, 'isoformat') else str(d) for d in dates_historical],
        'dates_future': [d.isoformat() if hasattr(d, 'isoformat') else str(d) for d in dates_future],
        'target_name': target_column,
        'actual_future': future_slice
    }
    
    return visualization_data
    