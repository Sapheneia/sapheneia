"""
TimesFM Forecasting Module

This module provides a simplified and robust interface for TimesFM forecasting,
handling both basic and covariates-enhanced forecasting with consistent quantile output.

Key Features:
- Single forecast method with optional covariates
- Always returns quantiles (never "maybe")
- Simplified logic: IF covariates -> use covariates, ELSE -> use basic
- Consistent return format: (point_forecast, quantile_forecast)
"""

import numpy as np
import pandas as pd
import logging
from typing import List, Dict, Optional, Tuple, Any, Union
import timesfm

logger = logging.getLogger(__name__)


class Forecaster:
    """
    Simplified TimesFM Forecaster with consistent quantile output.
    
    This class provides a single forecast method that handles both basic and
    covariates-enhanced forecasting, always returning quantiles.
    
    Example:
        >>> forecaster = Forecaster(model)
        >>> point_forecast, quantile_forecast = forecaster.forecast(
        ...     inputs=[1,2,3,4,5], 
        ...     use_covariates=True,
        ...     dynamic_numerical_covariates={'feature1': [[1,2,3,4,5]]}
        ... )
    """
    
    def __init__(self, model: timesfm.TimesFm):
        """
        Initialize the Forecaster with a loaded TimesFM model.
        
        Args:
            model: Initialized TimesFM model instance
        """
        self.model = model
        self.capabilities = self._detect_capabilities()
        logger.info(f"Forecaster initialized with capabilities: {list(self.capabilities.keys())}")
    
    def _detect_capabilities(self) -> Dict[str, bool]:
        """Detect available forecasting capabilities of the model."""
        return {
            'basic_forecasting': True,
            'quantile_forecasting': hasattr(self.model, 'experimental_quantile_forecast'),
            'covariates_support': hasattr(self.model, 'forecast_with_covariates')
        }
    
    def forecast(
        self,
        inputs: Union[List[float], List[List[float]]],
        freq: Union[int, List[int]] = 0,
        dynamic_numerical_covariates: Optional[Dict[str, List[List[float]]]] = None,
        dynamic_categorical_covariates: Optional[Dict[str, List[List[str]]]] = None,
        static_numerical_covariates: Optional[Dict[str, List[float]]] = None,
        static_categorical_covariates: Optional[Dict[str, List[str]]] = None,
        use_covariates: bool = False,
        xreg_mode: str = "xreg + timesfm",
        ridge: float = 0.0,
        normalize_xreg_target_per_input: bool = True
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Perform TimesFM forecasting with optional covariates support.
        
        This is the main forecasting method that handles both basic and covariates-enhanced
        forecasting. Quantiles are always returned regardless of covariates usage.
        
        Args:
            inputs: Input time series data
            freq: Frequency indicator(s)
            dynamic_numerical_covariates: Dynamic numerical covariates (if use_covariates=True)
            dynamic_categorical_covariates: Dynamic categorical covariates (if use_covariates=True)
            static_numerical_covariates: Static numerical covariates (if use_covariates=True)
            static_categorical_covariates: Static categorical covariates (if use_covariates=True)
            use_covariates: Whether to use covariates-enhanced forecasting
            xreg_mode: Covariate integration mode ("xreg + timesfm" or "timesfm + xreg")
            ridge: Ridge regression parameter for covariates
            normalize_xreg_target_per_input: Whether to normalize covariates
            
        Returns:
            Tuple of (point_forecast, quantile_forecast) - both are always returned
            
        Raises:
            ValueError: If covariates are requested but not supported
            Exception: If forecasting fails
        """
        logger.info(f"Performing TimesFM forecasting (covariates={use_covariates})...")
        
        # Normalize inputs format
        if isinstance(inputs[0], (int, float)):
            # inputs is a single list of numbers
            inputs_norm = [inputs]
        else:
            # inputs is already a list of lists
            inputs_norm = inputs
            
        if isinstance(freq, int):
            freq_norm = [freq] * len(inputs_norm)
        else:
            freq_norm = freq

        try:
            if use_covariates and any([
                dynamic_numerical_covariates, dynamic_categorical_covariates,
                static_numerical_covariates, static_categorical_covariates
            ]):
                # Validate covariates support
                if not self.capabilities['covariates_support']:
                    raise ValueError("Model does not support covariates forecasting")
                
                # Validate covariates data structure
                self._validate_covariates(
                    inputs_norm, dynamic_numerical_covariates, dynamic_categorical_covariates,
                    static_numerical_covariates, static_categorical_covariates
                )
                
                logger.info(f"Using covariates-enhanced forecasting (mode: {xreg_mode})...")
                logger.info(f"Inputs shape: {[len(x) for x in inputs] if isinstance(inputs[0], list) else len(inputs)}")
                logger.info(f"Inputs type: {type(inputs)}")
                
                # Perform covariates forecasting with original mode
                covariates_result = self.model.forecast_with_covariates(
                    inputs=inputs_norm,
                    dynamic_numerical_covariates=dynamic_numerical_covariates or {},
                    dynamic_categorical_covariates=dynamic_categorical_covariates or {},
                    static_numerical_covariates=static_numerical_covariates or {},
                    static_categorical_covariates=static_categorical_covariates or {},
                    freq=freq_norm,
                    xreg_mode=xreg_mode,
                    ridge=ridge,
                    normalize_xreg_target_per_input=normalize_xreg_target_per_input
                )
                
                # Handle return format from forecast_with_covariates
                if isinstance(covariates_result, tuple) and len(covariates_result) == 2:
                    point_forecast, quantile_forecast = covariates_result
                    point_forecast = np.array(point_forecast)
                    quantile_forecast = np.array(quantile_forecast)
                    
                    logger.info(f"✅ Covariates forecasting completed.")
                    logger.info(f"  Point forecast shape: {point_forecast.shape}")
                    logger.info(f"  Quantile forecast shape: {quantile_forecast.shape}")
                    
                    # Check if we have proper quantiles (multiple quantiles, not just 1)
                    if quantile_forecast.ndim == 2 and (quantile_forecast.shape[0] == 1 or quantile_forecast.shape[1] == 1):
                        logger.warning("⚠️ Covariates forecasting returned insufficient quantiles, falling back to basic forecast for quantiles")
                        # Get quantiles from basic forecast method
                        _, quantile_forecast = self.model.forecast(inputs=inputs_norm, freq=freq_norm)
                        quantile_forecast = np.array(quantile_forecast)
                        logger.info(f"✅ Basic forecast quantiles obtained. Shape: {quantile_forecast.shape}")
                    else:
                        logger.info("✅ Using quantiles from covariates forecasting")
                else:
                    # Fallback: If forecast_with_covariates doesn't return quantiles, get them separately
                    logger.warning("⚠️ Covariates forecasting didn't return quantiles, getting them separately")
                    point_forecast = np.array(covariates_result)
                    _, quantile_forecast = self.model.forecast(inputs=inputs_norm, freq=freq_norm)
                    quantile_forecast = np.array(quantile_forecast)
            
            else:
                logger.info("Using basic forecasting...")
                
                # Perform basic forecasting - this should return (point, quantiles)
                point_forecast, quantile_forecast = self.model.forecast(inputs=inputs_norm, freq=freq_norm)
                point_forecast = np.array(point_forecast)
                quantile_forecast = np.array(quantile_forecast)
                
                logger.info(f"✅ Basic forecasting completed.")
            
            return point_forecast, quantile_forecast
            
        except Exception as e:
            logger.error(f"❌ Forecasting failed: {str(e)}")
            raise
    
    def _validate_covariates(
        self,
        inputs: List[List[float]],
        dynamic_numerical: Optional[Dict],
        dynamic_categorical: Optional[Dict],
        static_numerical: Optional[Dict],
        static_categorical: Optional[Dict]
    ) -> None:
        """Validate covariates data structure and compatibility."""
        logger.info("Validating covariates data structure...")
        
        # Check that all covariates have the same number of series as inputs
        num_series = len(inputs)
        
        for cov_type, cov_data in [
            ("dynamic_numerical", dynamic_numerical),
            ("dynamic_categorical", dynamic_categorical),
            ("static_numerical", static_numerical),
            ("static_categorical", static_categorical)
        ]:
            if cov_data:
                for name, data in cov_data.items():
                    if isinstance(data[0], (list, np.ndarray)):
                        # Dynamic covariates
                        if len(data) != num_series:
                            raise ValueError(f"Dynamic covariate '{name}' has {len(data)} series, expected {num_series}")
                    else:
                        # Static covariates
                        if len(data) != num_series:
                            raise ValueError(f"Static covariate '{name}' has {len(data)} values, expected {num_series}")
        
        logger.info("✅ Covariates validation passed")
    

def run_forecast(
    forecaster: 'Forecaster',
    target_inputs: List[List[float]],
    covariates: Optional[Dict[str, Any]] = None,
    use_covariates: bool = False,
    freq: Union[int, List[int]] = 0
) -> Dict[str, Any]:
    """
    Centralized forecasting function that handles both basic and covariates-enhanced forecasting.
    
    This function implements the logic to decide whether to run forecast_with_covariates
    or the basic forecast, including fallback mechanisms and proper error handling.
    
    Args:
        forecaster: Initialized Forecaster instance
        target_inputs: Input time series data
        covariates: Dictionary containing covariate data (if use_covariates=True)
        use_covariates: Whether to use covariates-enhanced forecasting
        freq: Frequency indicator(s)
        
    Returns:
        Dictionary containing forecast results with keys:
        - 'enhanced_forecast' or 'point_forecast': Main forecast array
        - 'quantile_forecast': Quantile forecast array (always present)
        - 'method': String indicating the forecasting method used
        - 'metadata': Additional forecast metadata
        
    Raises:
        Exception: If forecasting fails
    """
    logger.info(f"🚀 Running centralized forecast (covariates={use_covariates})...")
    
    try:
        results = {}
        
        if use_covariates and covariates:
            logger.info("Using covariates-enhanced forecasting...")
            
            # Extract covariate data
            dynamic_numerical = covariates.get('dynamic_numerical_covariates')
            dynamic_categorical = covariates.get('dynamic_categorical_covariates')
            static_numerical = covariates.get('static_numerical_covariates')
            static_categorical = covariates.get('static_categorical_covariates')
            
            # Perform covariates forecasting
            point_forecast, quantile_forecast = forecaster.forecast(
                inputs=target_inputs,
                freq=freq,
                dynamic_numerical_covariates=dynamic_numerical,
                dynamic_categorical_covariates=dynamic_categorical,
                static_numerical_covariates=static_numerical,
                static_categorical_covariates=static_categorical,
                use_covariates=True
            )
            
            results['point_forecast'] = point_forecast
            results['method'] = 'covariates_enhanced'
            
        else:
            logger.info("Using basic forecasting...")
            
            # Perform basic forecasting
            point_forecast, quantile_forecast = forecaster.forecast(
                inputs=target_inputs,
                freq=freq,
                use_covariates=False
            )
            
            results['point_forecast'] = point_forecast
            results['method'] = 'basic_timesfm'
        
        # Check for NaN values before returning
        if np.any(np.isnan(point_forecast)):
            logger.error(f"❌ NaN values detected in point_forecast: {np.isnan(point_forecast).sum()} out of {point_forecast.size}")
            logger.error(f"Point forecast values: {point_forecast}")
            raise ValueError(f"Forecasting produced NaN values in point forecast. This may be due to insufficient data or model issues.")
        
        if np.any(np.isnan(quantile_forecast)):
            logger.error(f"❌ NaN values detected in quantile_forecast: {np.isnan(quantile_forecast).sum()} out of {quantile_forecast.size}")
            logger.error(f"Quantile forecast shape: {quantile_forecast.shape}")
            raise ValueError(f"Forecasting produced NaN values in quantile forecast. This may be due to insufficient data or model issues.")
        
        # Quantiles are always available
        results['quantile_forecast'] = quantile_forecast
        logger.info(f"✅ Quantile forecast obtained. Shape: {quantile_forecast.shape}")
        
        # Add metadata
        results['metadata'] = {
            'input_series_count': len(target_inputs),
            'forecast_length': results.get('point_forecast').shape[-1],
            'covariates_used': use_covariates and covariates is not None,
            'quantiles_available': True  # Always true now
        }
        
        logger.info(f"✅ Centralized forecast completed successfully!")
        logger.info(f"   Method: {results['method']}")
        logger.info(f"   Forecast shape: {results['metadata']['forecast_length']}")
        logger.info(f"   Quantiles: Yes (shape: {quantile_forecast.shape})")
        logger.info(f"   Point forecast range: {np.min(point_forecast):.2f} to {np.max(point_forecast):.2f}")
        
        return results
        
    except Exception as e:
        logger.error(f"❌ Centralized forecasting failed: {str(e)}")
        raise


def process_quantile_bands(
    quantile_forecast: np.ndarray,
    selected_indices: List[int] = None
) -> Dict[str, Any]:
    """
    Centralized function to process quantile forecasts into quantile bands for visualization.
    
    This function contains the logic for sorting quantiles and creating the quantile band
    dictionary, as used in both the webapp and notebook.
    
    Args:
        quantile_forecast: Array of quantile forecasts with shape (horizon, num_quantiles) or (num_quantiles, horizon)
        selected_indices: List of quantile indices to use for bands (default: [1, 3, 5, 7, 9])
        
    Returns:
        Dictionary of quantile bands ready for visualization with keys:
        - 'quantile_band_0_lower', 'quantile_band_0_upper', 'quantile_band_0_label'
        - 'quantile_band_1_lower', 'quantile_band_1_upper', 'quantile_band_1_label'
        - etc.
    """
    logger.info("🔄 Processing quantile bands...")
    logger.info(f"Input quantile_forecast type: {type(quantile_forecast)}")
    logger.info(f"Input quantile_forecast shape: {quantile_forecast.shape if hasattr(quantile_forecast, 'shape') else 'N/A'}")

    # logger.info(f"!!!!!!!!!!!!! selected_indices: {selected_indices}")
    # logger.info(f"!!!!!!!!!!!!! quantile_forecast.shape: {quantile_forecast.shape}")
    
    if quantile_forecast is None:
        logger.warning("No quantile forecast provided")
        return {}
    
    try:
        # logger.info(f"!!!!!!!!!!!!! selected_indices: {selected_indices}")
        # logger.info(f"!!!!!!!!!!!!! quantile_forecast.shape: {quantile_forecast.shape}")

        # Handle quantile indices - only use default if explicitly None (not empty list)
        if selected_indices is None:
            # This means no quantile selection was made, use default
            selected_indices = [1, 3, 5, 7, 9]  # Q10, Q30, Q50, Q70, Q90
        elif selected_indices == []:
            # This means user explicitly selected no quantiles, return empty
            logger.info("No quantiles selected by user - returning empty quantile bands")
            return {}
        
        # Handle different array dimensions
        if quantile_forecast.ndim == 3:
            # Shape is (1, horizon, num_quantiles) - squeeze out first dimension
            q_mat = quantile_forecast.squeeze(0)
            logger.info(f"3D array detected, squeezed to shape: {q_mat.shape}")
        elif quantile_forecast.ndim == 1:
            # Shape is (horizon,) - reshape to (1, horizon)
            q_mat = quantile_forecast.reshape(1, -1)
            logger.info(f"1D array detected, reshaped to: {q_mat.shape}")
        else:
            # Shape is 2D - determine if we need to transpose
            # For quantiles, we expect (horizon, num_quantiles) format
            # If we have more horizon than quantiles, it's likely (horizon, num_quantiles) and should be kept as-is
            if quantile_forecast.shape[0] > quantile_forecast.shape[1]:
                # Shape is (horizon, num_quantiles) - keep as is
                q_mat = quantile_forecast
                logger.info(f"2D array kept as is (horizon, quantiles): {q_mat.shape}")
            else:
                # Shape is (num_quantiles, horizon) - transpose to (horizon, num_quantiles)
                q_mat = quantile_forecast.T
                logger.info(f"2D array transposed from {quantile_forecast.shape} to {q_mat.shape}")
        
        horizon_len, num_quantiles = q_mat.shape
        logger.info(f"📊 Available quantiles: {num_quantiles} (indices 0-{num_quantiles-1})")
        logger.info(f"📊 Note: Index 0 is legacy mean forecast, using indices 1-{num_quantiles-1} for actual quantiles")
        
        # Check if we have enough quantiles for band creation (need at least 3 total: 0=legacy, 1=Q10, 2=Q20)
        if num_quantiles < 3:
            logger.warning(f"Not enough quantiles for band creation. Have {num_quantiles}, need at least 3")
            return {}
        
        # Filter selected indices to valid range (skip index 0)
        valid_indices = [idx for idx in selected_indices if 1 <= idx < num_quantiles]  # Skip index 0
        if not valid_indices:
            logger.warning("No valid quantile indices selected (after skipping legacy index 0)")
            return {}
        
        # logger.info(f"!!!!!!!!!!!!! valid_indices: {valid_indices}")
        
        # Sort quantiles by their median magnitude to ensure proper ordering
        quantile_medians = np.median(q_mat, axis=0)
        sorted_indices = np.argsort(quantile_medians)
        
        # Create quantile bands from selected indices
        quantile_bands = {}
        band_count = 0
        
        for i in range(len(valid_indices) - 1):
            lower_idx = valid_indices[i]
            upper_idx = valid_indices[i + 1]
            
            # Get the sorted indices for these quantiles
            lower_sorted_idx = sorted_indices[lower_idx]
            upper_sorted_idx = sorted_indices[upper_idx]
            
            # Extract quantile values
            lower_quantile = q_mat[:, lower_sorted_idx]
            upper_quantile = q_mat[:, upper_sorted_idx]
            
            # Create band labels
            lower_pct = idx_to_percent(lower_idx, num_quantiles)
            upper_pct = idx_to_percent(upper_idx, num_quantiles)
            band_label = f"Q{lower_pct:02d}–Q{upper_pct:02d}"
            
            # Store band data
            quantile_bands[f'quantile_band_{band_count}_lower'] = lower_quantile.tolist()
            quantile_bands[f'quantile_band_{band_count}_upper'] = upper_quantile.tolist()
            quantile_bands[f'quantile_band_{band_count}_label'] = band_label
            
            logger.info(f"   Band {band_count}: {band_label} - Lower: {len(lower_quantile)}, Upper: {len(upper_quantile)}")
            band_count += 1
        
        logger.info(f"✅ Created {band_count} quantile bands from indices: {valid_indices}")
        for i in range(band_count):
            label = quantile_bands[f'quantile_band_{i}_label']
            logger.info(f"   Band {i}: {label}")
        
        return quantile_bands
        
    except Exception as e:
        logger.error(f"❌ Quantile band processing failed: {str(e)}")
        raise


def idx_to_percent(idx: int, num_quantiles: int) -> int:
    """
    Convert quantile index to percentage for labeling.
    
    Note: Index 0 is legacy mean forecast and should be skipped.
    Actual quantiles start at index 1: 1->Q10, 2->Q20, ..., 9->Q90
    
    Args:
        idx: Quantile index (1-based for actual quantiles, 0 is legacy)
        num_quantiles: Total number of quantiles (including legacy index 0)
        
    Returns:
        Percentage value (e.g., 10 for Q10, 90 for Q90)
    """
    if num_quantiles == 10:
        # Special case for 10 quantiles: 1->Q10, 2->Q20, ..., 9->Q90
        # Index 0 is legacy mean, so actual quantiles start at index 1
        return idx * 10
    else:
        # General case: distribute evenly, accounting for skipped index 0
        # If we have 10 total quantiles (0-9), actual quantiles are 1-9
        actual_quantiles = num_quantiles - 1  # Subtract 1 for legacy index 0
        return int(100 * idx / actual_quantiles)