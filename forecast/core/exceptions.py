"""
Custom Exception Hierarchy for Sapheneia API.

Provides structured error handling with consistent error codes and messages.
Allows for better error tracking, debugging, and user-friendly error responses.

Usage:
    # In service code
    raise DataFetchError("File not found", path="/data/file.csv")
    
    # In endpoints - caught automatically by exception handlers
    # Returns structured JSON response with error_code, message, details
"""

from typing import Optional, Dict, Any


class SapheneiaException(Exception):
    """
    Base exception for all Sapheneia API errors.
    
    Provides structured error information with:
    - error_code: Machine-readable error code
    - message: Human-readable error message
    - details: Additional context for debugging
    - suggested_status_code: Suggested HTTP status code
    """
    
    def __init__(
        self,
        message: str,
        error_code: str = "SAPHENEIA_ERROR",
        details: Optional[Dict[str, Any]] = None,
        suggested_status_code: int = 500
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.suggested_status_code = suggested_status_code
        super().__init__(message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary format."""
        return {
            "error": self.error_code,
            "message": self.message,
            "details": self.details
        }


# --- Data Errors ---

class DataError(SapheneiaException):
    """Base class for all data-related errors."""
    
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        super().__init__(
            message,
            error_code="DATA_ERROR",
            details=details,
            suggested_status_code=400,
            **kwargs
        )


class DataFetchError(DataError):
    """Failed to fetch data from source (file, URL, etc.)."""
    
    def __init__(
        self,
        message: str = "Failed to fetch data from source",
        source: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        if details is None:
            details = {}
        if source:
            details["source"] = source
        super().__init__(message, details)


class DataValidationError(DataError):
    """Data validation failed (wrong structure, missing fields, etc.)."""
    
    def __init__(
        self,
        message: str = "Data validation failed",
        validation_errors: Optional[Dict[str, Any]] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        if details is None:
            details = {}
        if validation_errors:
            details["validation_errors"] = validation_errors
        super().__init__(message, details)


class DataProcessingError(DataError):
    """Error during data processing/transformation."""
    
    def __init__(
        self,
        message: str = "Data processing failed",
        step: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        if details is None:
            details = {}
        if step:
            details["processing_step"] = step
        super().__init__(message, details)


# --- Model Errors ---

class ModelError(SapheneiaException):
    """Base class for all model-related errors."""
    
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        suggested_status_code: int = 500,
        **kwargs
    ):
        super().__init__(
            message,
            error_code="MODEL_ERROR",
            details=details,
            suggested_status_code=suggested_status_code,
            **kwargs
        )


class ModelNotInitializedError(ModelError):
    """Model is not initialized (must call initialization first)."""
    
    def __init__(
        self,
        model_name: str = "TimesFM-2.0",
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        if message is None:
            message = f"Model '{model_name}' is not initialized. Please call /initialization first."
        if details is None:
            details = {"model_name": model_name}
        else:
            details["model_name"] = model_name
        super().__init__(message, details, suggested_status_code=409)


class ModelInitializationError(ModelError):
    """Model initialization failed."""
    
    def __init__(
        self,
        message: str = "Model initialization failed",
        source: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        if details is None:
            details = {}
        if source:
            details["initialization_source"] = source
        super().__init__(message, details, suggested_status_code=500)


class InferenceError(ModelError):
    """Inference operation failed."""
    
    def __init__(
        self,
        message: str = "Inference operation failed",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, details, suggested_status_code=500)


class ModelNotFoundError(ModelError):
    """Model not found (checkpoint, local file, etc.)."""
    
    def __init__(
        self,
        message: str = "Model not found",
        resource_path: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        if details is None:
            details = {}
        if resource_path:
            details["resource_path"] = resource_path
        super().__init__(message, details, suggested_status_code=404)


# --- Configuration Errors ---

class ConfigurationError(SapheneiaException):
    """Configuration errors (missing settings, invalid values, etc.)."""
    
    def __init__(
        self,
        message: str = "Configuration error",
        setting: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        if details is None:
            details = {}
        if setting:
            details["setting"] = setting
        super().__init__(
            message,
            error_code="CONFIG_ERROR",
            details=details,
            suggested_status_code=500
        )


# --- Security Errors ---

class SecurityError(SapheneiaException):
    """Security-related errors (unauthorized access, path traversal, etc.)."""
    
    def __init__(
        self,
        message: str = "Security violation",
        violation_type: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        if details is None:
            details = {}
        if violation_type:
            details["violation_type"] = violation_type
        super().__init__(
            message,
            error_code="SECURITY_ERROR",
            details=details,
            suggested_status_code=403
        )


class UnauthorizedError(SecurityError):
    """Unauthorized access attempt."""
    
    def __init__(
        self,
        message: str = "Unauthorized access",
        resource: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        if details is None:
            details = {}
        if resource:
            details["resource"] = resource
        super().__init__(
            message,
            violation_type="unauthorized",
            details=details
        )


# --- API Errors ---

class APIError(SapheneiaException):
    """General API errors (rate limits, request size, etc.)."""
    
    def __init__(
        self,
        message: str,
        error_code: str = "API_ERROR",
        details: Optional[Dict[str, Any]] = None,
        suggested_status_code: int = 400
    ):
        super().__init__(message, error_code, details, suggested_status_code)


class RateLimitExceededError(APIError):
    """Rate limit exceeded."""
    
    def __init__(
        self,
        limit: Optional[str] = None,
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        if message is None:
            message = f"Rate limit exceeded" + (f": {limit}" if limit else "")
        if details is None:
            details = {}
        if limit:
            details["rate_limit"] = limit
        super().__init__(
            message,
            error_code="RATE_LIMIT_EXCEEDED",
            details=details,
            suggested_status_code=429
        )


class RequestTooLargeError(APIError):
    """Request size exceeds limits."""
    
    def __init__(
        self,
        max_size: int,
        actual_size: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        message = f"Request size exceeds maximum allowed size of {max_size} bytes"
        if details is None:
            details = {"max_size": max_size}
        if actual_size:
            details["actual_size"] = actual_size
            details["percentage"] = f"{(actual_size / max_size * 100):.1f}%"
        super().__init__(
            message,
            error_code="REQUEST_TOO_LARGE",
            details=details,
            suggested_status_code=413
        )
