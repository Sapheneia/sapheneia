"""Path handling utilities for Sapheneia.

Provides consistent path resolution across venv and Docker environments.
Addresses issues found in CODEREVIEW.md: path handling inconsistencies.

This module centralizes all path handling logic to ensure:
1. Consistent behavior between venv and Docker environments
2. Automatic security validation (prevent path traversal attacks)
3. Support for multiple path input formats
"""

import os
from pathlib import Path
from typing import Union
from logging import getLogger

logger = getLogger(__name__)

# Detect environment (similar to ui/app.py but centralized)
IS_DOCKER = os.path.exists('/app')

# PROJECT_ROOT detection
if IS_DOCKER:
    PROJECT_ROOT = Path('/app')
else:
    # In venv: go up from forecast/core/ to project root
    PROJECT_ROOT = Path(__file__).parent.parent.parent

# Base directories (consistent across environments)
DATA_DIR = PROJECT_ROOT / 'data'
UPLOADS_DIR = DATA_DIR / 'uploads'
RESULTS_DIR = DATA_DIR / 'results'
LOGS_DIR = PROJECT_ROOT / 'logs'

# Initialize logger if not already configured (defensive)
try:
    logger.info(f"Path utilities initialized: IS_DOCKER={IS_DOCKER}, PROJECT_ROOT={PROJECT_ROOT}")
except (AttributeError, RuntimeError):
    # Logger not configured yet, configure basic logging
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    logger.info(f"Path utilities initialized: IS_DOCKER={IS_DOCKER}, PROJECT_ROOT={PROJECT_ROOT}")


def normalize_data_path(path: Union[str, Path]) -> Path:
    """
    Normalize a data file path for the current environment.
    
    Handles multiple input formats:
    - Absolute paths: "/app/data/uploads/file.csv" (Docker)
    - Absolute paths: "/path/to/project/data/uploads/file.csv" (venv)
    - Relative paths: "data/uploads/file.csv"
    - Prefixed paths: "local://data/uploads/file.csv" (from ui/app.py)
    - Bare filenames: "file.csv" → resolves to uploads directory
    
    Args:
        path: Input path in any format
        
    Returns:
        Absolute Path object for the current environment
        
    Raises:
        ValueError: If path is outside allowed directories
        
    Example:
        >>> # In Docker
        >>> normalize_data_path("file.csv")
        Path('/app/data/uploads/file.csv')
        
        >>> # In venv
        >>> normalize_data_path("file.csv")
        Path('/path/to/project/data/uploads/file.csv')
        
        >>> # With local:// prefix (from UI)
        >>> normalize_data_path("local:///app/data/uploads/file.csv")
        Path('/app/data/uploads/file.csv')
        
        >>> # Security validation
        >>> normalize_data_path("../../../etc/passwd")
        ValueError: Security: Path is outside allowed data directory
    """
    path_str = str(path)
    logger.debug(f"Normalizing path: {path_str}")
    
    # Remove local:// prefix (from CODEREVIEW.md line 363)
    if path_str.startswith('local://'):
        path_str = path_str.replace('local://', '')
        logger.debug(f"Removed local:// prefix: {path_str}")
    
    path_obj = Path(path_str)
    
    # Resolve path based on environment
    if path_obj.is_absolute():
        # Absolute path - check if it needs conversion between environments
        abs_path = path_obj
        
        # If Docker path in venv environment, convert
        if not IS_DOCKER and str(abs_path).startswith('/app'):
            # Running in venv, but path is Docker-style
            relative_path = str(abs_path).replace('/app/', '')
            abs_path = PROJECT_ROOT / relative_path
            logger.debug(f"Converted Docker path to venv: {abs_path}")
        
        # If venv path in Docker, we may need to convert
        # But if it's already under /app, keep as-is
        elif IS_DOCKER and not str(abs_path).startswith('/app'):
            # Running in Docker but path is venv-style - check if it's a relative conversion
            if 'data' in str(abs_path):
                # Try to find the data part
                parts = Path(abs_path).parts
                if 'data' in parts:
                    data_idx = parts.index('data')
                    relative_path = Path(*parts[data_idx:])
                    abs_path = PROJECT_ROOT / relative_path
                    logger.debug(f"Converted venv path to Docker: {abs_path}")
            
    else:
        # Relative path - resolve based on environment
        if path_str.startswith('data/'):
            # Already includes data/ prefix
            abs_path = PROJECT_ROOT / path_str
            logger.debug(f"Resolved data/ prefixed path: {abs_path}")
        elif '/' not in path_str:
            # Bare filename - assume uploads directory
            abs_path = UPLOADS_DIR / path_str
            logger.debug(f"Resolved bare filename to: {abs_path}")
        else:
            # Other relative path - resolve from project root
            abs_path = PROJECT_ROOT / path_str
            logger.debug(f"Resolved relative path: {abs_path}")
    
    # Resolve to absolute path (follow symlinks, remove .., etc.)
    abs_path = abs_path.resolve()
    
    # Security: Ensure path is within allowed directories
    # This prevents path traversal attacks (../../etc/passwd)
    try:
        abs_path.relative_to(DATA_DIR)
        logger.debug(f"✅ Security check passed: {abs_path}")
    except ValueError:
        raise ValueError(
            f"Security violation: Path '{path}' is outside allowed data directory.\n"
            f"Resolved to: {abs_path}\n"
            f"Allowed directory: {DATA_DIR}\n"
            f"This prevents access to files outside the data directory."
        )
    
    return abs_path


def ensure_directory(path: Union[str, Path]) -> Path:
    """Ensure directory exists, creating if necessary.
    
    Args:
        path: Directory path to ensure exists
        
    Returns:
        Path object for the directory
    """
    path_obj = Path(path)
    path_obj.mkdir(parents=True, exist_ok=True)
    logger.debug(f"Ensured directory exists: {path_obj}")
    return path_obj


def get_upload_path(filename: str) -> Path:
    """Get path for uploaded file.
    
    Args:
        filename: Name of uploaded file
        
    Returns:
        Full path for uploaded file
    """
    return UPLOADS_DIR / filename


def get_result_path(filename: str) -> Path:
    """Get path for result file.
    
    Args:
        filename: Name of result file
        
    Returns:
        Full path for result file
    """
    return RESULTS_DIR / filename


# Initialize directories on module import
for directory in [DATA_DIR, UPLOADS_DIR, RESULTS_DIR, LOGS_DIR]:
    ensure_directory(directory)
    logger.debug(f"Initialized directory: {directory}")

