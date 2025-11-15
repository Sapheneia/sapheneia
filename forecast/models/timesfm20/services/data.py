"""
TimesFM-2.0 Data Service

Handles data loading, transformation, and validation specific to TimesFM-2.0 model.
Uses core data utilities for fetching and applies model-specific transformations.
"""

import logging
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Any, Optional

# Import core modules (proper Python imports - no sys.path hacks)
from ....core.data_processing import DataProcessor, prepare_visualization_data
from ....core.data import fetch_data_source, DataFetchError

logger = logging.getLogger(__name__)

# Use centralized exception hierarchy (Phase 7: Error Handling)
try:
    from ...core.exceptions import DataError, DataValidationError, DataProcessingError
    
    class TimesFMDataError(DataProcessingError):
        """Raised when TimesFM-specific data processing fails."""
        pass
except ImportError:
    # Fallback if exceptions module not available
    class TimesFMDataError(Exception):
        """Raised when TimesFM-specific data processing fails."""
        pass


def load_and_transform_timesfm_data(
    data_source: str,
    data_definition: Dict[str, str],
    parameters: Dict[str, Any]
) -> Tuple[List[float], Dict[str, Any], pd.DataFrame]:
    """
    Load and transform data for TimesFM inference.

    This is the main entry point for data loading in the TimesFM-2.0 service.
    It fetches raw data and applies TimesFM-specific transformations.

    Args:
        data_source: URL or path to data source
        data_definition: Column type definitions
        parameters: Inference parameters (context_len, horizon_len, etc.)

    Returns:
        Tuple of (target_inputs, covariates, processed_data)

    Raises:
        TimesFMDataError: If data loading or transformation fails
        DataFetchError: If data fetching fails
    """
    logger.info(f"Loading and transforming data from: {data_source}")

    try:
        # Fetch raw data using core utilities
        raw_data = fetch_data_source(data_source)

        # Validate it's a DataFrame
        if not isinstance(raw_data, pd.DataFrame):
            raise TimesFMDataError(
                f"Expected DataFrame from data source, got {type(raw_data)}"
            )

        # Use existing DataProcessor for TimesFM-specific processing
        processor = DataProcessor()

        # Process the fetched data directly (we already have a DataFrame)
        processor.data = raw_data.copy()
        processor.data_definition = data_definition.copy()

        # Ensure 'date' column exists and is converted to datetime
        if 'date' not in processor.data.columns:
            raise TimesFMDataError("CSV file must contain a 'date' column")

        # Convert date column to datetime
        processor.data['date'] = pd.to_datetime(processor.data['date'])
        logger.info(f"Date range: {processor.data['date'].min()} to {processor.data['date'].max()}")

        # Apply data types
        processor._apply_data_types()

        # Validate definition
        processor._validate_data_definition()

        processed_data = processor.data.copy()

        logger.info(f"Data processed successfully with shape: {processed_data.shape}")

        # Extract parameters
        context_len = parameters.get('context_len', 64)
        horizon_len = parameters.get('horizon_len', 24)

        # Determine target column
        target_column = None
        for col, dtype in data_definition.items():
            if dtype == 'target':
                target_column = col
                break

        if not target_column:
            raise TimesFMDataError("No target column found in data definition")

        # Prepare forecast data (target inputs and covariates)
        target_inputs, covariates = processor.prepare_forecast_data(
            data=processed_data,
            context_len=context_len,
            horizon_len=horizon_len,
            target_column=target_column
        )

        logger.info(f"✅ Data transformation complete:")
        logger.info(f"  Target inputs length: {len(target_inputs)}")
        logger.info(f"  Covariates keys: {list(covariates.keys())}")
        logger.info(f"  Processed data shape: {processed_data.shape}")

        return target_inputs, covariates, processed_data

    except DataFetchError:
        # Re-raise data fetch errors as-is
        raise

    except Exception as e:
        logger.error(f"❌ Data transformation failed: {str(e)}")
        raise TimesFMDataError(f"Failed to transform data for TimesFM: {str(e)}")


def prepare_timesfm_visualization_data(
    processed_data: pd.DataFrame,
    target_inputs: List[float],
    target_column: str,
    context_len: int,
    horizon_len: int,
    extended_data: Optional[pd.DataFrame] = None
) -> Dict[str, Any]:
    """
    Prepare visualization data for TimesFM results.

    Uses the existing prepare_visualization_data function from src/data.py.

    Args:
        processed_data: Processed DataFrame
        target_inputs: Target input data
        target_column: Name of target column
        context_len: Context length
        horizon_len: Horizon length
        extended_data: Optional extended data including horizon period

    Returns:
        Dictionary containing visualization data
    """
    logger.info("Preparing visualization data for TimesFM results")

    try:
        viz_data = prepare_visualization_data(
            processed_data=processed_data,
            target_inputs=target_inputs,
            target_column=target_column,
            context_len=context_len,
            horizon_len=horizon_len,
            extended_data=extended_data
        )

        logger.info(f"✅ Visualization data prepared:")
        logger.info(f"  Historical data points: {len(viz_data.get('historical_data', []))}")
        logger.info(f"  Future dates: {len(viz_data.get('dates_future', []))}")
        logger.info(f"  Actual future values: {len(viz_data.get('actual_future', []))}")

        return viz_data

    except Exception as e:
        logger.error(f"❌ Visualization data preparation failed: {str(e)}")
        raise TimesFMDataError(f"Failed to prepare visualization data: {str(e)}")


def validate_timesfm_data_structure(
    target_inputs: List[float],
    covariates: Dict[str, Any],
    context_len: int,
    horizon_len: int
) -> bool:
    """
    Validate data structure is compatible with TimesFM requirements.

    Args:
        target_inputs: Target input data
        covariates: Covariates dictionary
        context_len: Expected context length
        horizon_len: Expected horizon length

    Returns:
        True if validation passes

    Raises:
        TimesFMDataError: If validation fails
    """
    logger.info("Validating TimesFM data structure")

    try:
        # Validate target inputs length
        if len(target_inputs) != context_len:
            raise TimesFMDataError(
                f"Target inputs length {len(target_inputs)} doesn't match "
                f"context_len {context_len}"
            )

        # Validate all values are numeric and not NaN
        if not all(isinstance(x, (int, float)) and not np.isnan(x) for x in target_inputs):
            raise TimesFMDataError("All target inputs must be numeric and non-NaN")

        # Validate covariates structure
        total_len = context_len + horizon_len

        for cov_type, cov_dict in covariates.items():
            if cov_type in ['dynamic_numerical_covariates', 'dynamic_categorical_covariates']:
                for name, values_list in cov_dict.items():
                    if len(values_list) != 1:
                        raise TimesFMDataError(
                            f"Dynamic covariate '{name}' must have exactly 1 time series, "
                            f"got {len(values_list)}"
                        )
                    if len(values_list[0]) != total_len:
                        raise TimesFMDataError(
                            f"Dynamic covariate '{name}' must have {total_len} values "
                            f"(context {context_len} + horizon {horizon_len}), "
                            f"got {len(values_list[0])}"
                        )

            elif cov_type in ['static_numerical_covariates', 'static_categorical_covariates']:
                for name, values_list in cov_dict.items():
                    if len(values_list) != 1:
                        raise TimesFMDataError(
                            f"Static covariate '{name}' must have exactly 1 value, "
                            f"got {len(values_list)}"
                        )

        logger.info("✅ TimesFM data structure validation passed")
        return True

    except TimesFMDataError:
        raise
    except Exception as e:
        logger.error(f"❌ Data validation failed: {str(e)}")
        raise TimesFMDataError(f"Data validation failed: {str(e)}")
