"""
Shared Data Fetching Utilities

Handles fetching data from various sources (local files, HTTP/HTTPS URLs).
Returns raw data for model-specific transformation.

Updated to use centralized path handling utilities for consistent behavior
across venv and Docker environments.
"""

import os
import logging
import requests
import pandas as pd
from pathlib import Path
from typing import Union, Dict, Any
from urllib.parse import urlparse

from .paths import normalize_data_path

logger = logging.getLogger(__name__)


# Define DataFetchError locally to avoid circular import
# It will be moved to exceptions.py in Phase 7 but kept here for now
class DataFetchError(Exception):
    """Raised when data fetching fails."""
    pass


def fetch_data_source(
    source_url_or_path: str,
    allowed_local_base_dir: str = None  # Deprecated, kept for backward compatibility
) -> Union[pd.DataFrame, Dict[str, Any]]:
    """
    Fetches data from a specified source URL or local path.

    This function supports multiple data source types:
    - Local files: "local://path/to/file.csv", "file.csv", "/absolute/path"
    - HTTP/HTTPS URLs: "http://example.com/data.csv"
    
    Path normalization automatically handles differences between Docker and venv environments.
    All paths are validated for security (prevents path traversal attacks).

    Args:
        source_url_or_path: URL or path to the data source
        allowed_local_base_dir: DEPRECATED - security is now handled automatically

    Returns:
        Raw data as DataFrame or dictionary

    Raises:
        DataFetchError: If fetching fails
        FileNotFoundError: If local file not found
        ValueError: If path is outside allowed directory
    """
    logger.info(f"Fetching data from source: {source_url_or_path}")

    # Check if URL
    if source_url_or_path.startswith(("http://", "https://")):
        return _fetch_http_url(source_url_or_path)

    elif source_url_or_path.startswith(("s3://", "gs://")):
        # Cloud storage (placeholder for future implementation)
        raise NotImplementedError(
            "S3/GCS support not yet implemented. "
            "Please use local files or HTTP URLs."
        )

    else:
        # Local file - normalize path (handles all formats including local:// prefix)
        file_path = normalize_data_path(source_url_or_path)
        logger.info(f"Resolved to local path: {file_path}")
        return _fetch_local_file(file_path)


def _fetch_local_file(file_path: Path) -> pd.DataFrame:
    """
    Fetch data from a local file (path already normalized and validated).
    
    Security validation is performed by normalize_data_path() before this function
    is called, so we don't need to repeat the checks here.

    Args:
        file_path: Normalized Path object (from normalize_data_path)

    Returns:
        DataFrame loaded from file

    Raises:
        FileNotFoundError: If file doesn't exist
        DataFetchError: If file cannot be read
    """
    logger.info(f"Fetching local file: {file_path}")

    # Check if file exists
    if not file_path.exists():
        raise FileNotFoundError(
            f"File not found: {file_path}\n"
            f"Make sure the file is in the data/uploads directory."
        )

    # Determine file type and load
    file_extension = file_path.suffix.lower()

    try:
        if file_extension == ".csv":
            data = pd.read_csv(file_path)
            logger.info(f"Loaded CSV with shape: {data.shape}")
            return data

        elif file_extension == ".json":
            data = pd.read_json(file_path)
            logger.info(f"Loaded JSON with shape: {data.shape}")
            return data

        elif file_extension in [".xlsx", ".xls"]:
            data = pd.read_excel(file_path)
            logger.info(f"Loaded Excel with shape: {data.shape}")
            return data

        else:
            raise DataFetchError(
                f"Unsupported file format: {file_extension}\n"
                f"Supported: .csv, .json, .xlsx, .xls"
            )

    except Exception as e:
        logger.error(f"Failed to load file: {e}")
        raise DataFetchError(f"Failed to load file: {e}")


def _fetch_http_url(url: str, timeout: int = 30) -> pd.DataFrame:
    """
    Fetch data from an HTTP/HTTPS URL.

    Args:
        url: HTTP/HTTPS URL to fetch
        timeout: Request timeout in seconds

    Returns:
        DataFrame loaded from URL

    Raises:
        DataFetchError: If request fails or data cannot be parsed
    """
    logger.info(f"Fetching HTTP URL: {url}")

    try:
        # Make HTTP request
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()  # Raise exception for bad status codes

        # Determine content type
        content_type = response.headers.get("Content-Type", "").lower()

        # Parse based on content type or URL extension
        if "json" in content_type or url.endswith(".json"):
            data = pd.read_json(response.text)
            logger.info(f"Loaded JSON from URL with shape: {data.shape}")
            return data

        elif "csv" in content_type or url.endswith(".csv"):
            from io import StringIO
            data = pd.read_csv(StringIO(response.text))
            logger.info(f"Loaded CSV from URL with shape: {data.shape}")
            return data

        else:
            # Default to CSV
            from io import StringIO
            data = pd.read_csv(StringIO(response.text))
            logger.info(f"Loaded data from URL (default CSV) with shape: {data.shape}")
            return data

    except requests.exceptions.RequestException as e:
        logger.error(f"HTTP request failed: {str(e)}")
        raise DataFetchError(f"Failed to fetch data from URL: {str(e)}")

    except Exception as e:
        logger.error(f"Failed to parse data from URL: {str(e)}")
        raise DataFetchError(f"Failed to parse data from URL: {str(e)}")


def validate_data_structure(data: pd.DataFrame) -> bool:
    """
    Validate that fetched data has the expected structure.

    Args:
        data: DataFrame to validate

    Returns:
        True if validation passes

    Raises:
        ValueError: If validation fails
    """
    if data.empty:
        raise ValueError("Data is empty")

    if not isinstance(data, pd.DataFrame):
        raise ValueError(f"Expected DataFrame, got {type(data)}")

    logger.info(f"Data validation passed: {data.shape}")
    return True
