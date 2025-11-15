"""
Sapheneia API Client

REST API client for communicating with the Sapheneia FastAPI backend.
Handles all model operations through HTTP requests.
"""

import os
import logging
import requests
from typing import Dict, Any, Optional, Tuple
from requests.exceptions import RequestException, Timeout, ConnectionError

logger = logging.getLogger(__name__)


class SapheneiaAPIClient:
    """
    Client for interacting with the Sapheneia FastAPI backend.

    Provides methods for model initialization, status checking, inference,
    and shutdown operations.
    """

    def __init__(
        self,
        base_url: str = None,
        api_key: str = None,
        timeout: int = 300  # 5 minutes for model operations
    ):
        """
        Initialize the API client.

        Args:
            base_url: Base URL of the API (default from environment or localhost:8000)
            api_key: API key for authentication (default from environment)
            timeout: Request timeout in seconds
        """
        self.base_url = base_url or os.environ.get(
            'UI_API_BASE_URL',
            'http://localhost:8000'
        )
        self.api_key = api_key or os.environ.get(
            'API_SECRET_KEY',
            'your_secret_key_change_me_in_production'
        )
        self.timeout = timeout

        # Ensure base_url doesn't end with /
        self.base_url = self.base_url.rstrip('/')

        logger.info(f"API Client initialized with base URL: {self.base_url}")

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with authentication."""
        return {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }

    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        timeout: Optional[int] = None
    ) -> Tuple[bool, Any]:
        """
        Make an HTTP request to the API.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            data: Request body data
            timeout: Request timeout (uses default if None)

        Returns:
            Tuple of (success, response_data_or_error_message)
        """
        url = f"{self.base_url}{endpoint}"
        timeout = timeout or self.timeout

        try:
            logger.info(f"{method} {url}")

            if method.upper() == 'GET':
                response = requests.get(
                    url,
                    headers=self._get_headers(),
                    timeout=timeout
                )
            elif method.upper() == 'POST':
                response = requests.post(
                    url,
                    headers=self._get_headers(),
                    json=data,
                    timeout=timeout
                )
            else:
                return False, f"Unsupported HTTP method: {method}"

            # Check for HTTP errors
            response.raise_for_status()

            # Parse JSON response
            result = response.json()
            logger.info(f"API call successful: {endpoint}")
            return True, result

        except Timeout:
            error_msg = f"Request timeout after {timeout}s"
            logger.error(error_msg)
            return False, error_msg

        except ConnectionError:
            error_msg = "Cannot connect to API server. Is it running?"
            logger.error(error_msg)
            return False, error_msg

        except requests.HTTPError as e:
            # Try to get error detail from response
            try:
                error_detail = e.response.json().get('detail', str(e))
            except:
                error_detail = str(e)

            error_msg = f"API error ({e.response.status_code}): {error_detail}"
            logger.error(error_msg)
            return False, error_msg

        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    def health_check(self) -> Tuple[bool, Dict]:
        """
        Check API health status.

        Returns:
            Tuple of (success, health_data)
        """
        return self._make_request('GET', '/health', timeout=5)

    def get_model_status(self) -> Tuple[bool, Dict]:
        """
        Get current model status.

        Returns:
            Tuple of (success, status_data)
        """
        return self._make_request('GET', '/forecast/v1/timesfm20/status', timeout=5)

    def initialize_model(
        self,
        backend: str = 'cpu',
        context_len: int = 64,
        horizon_len: int = 24,
        checkpoint: str = None,
        local_model_path: str = None
    ) -> Tuple[bool, Dict]:
        """
        Initialize the TimesFM model.

        Args:
            backend: Computing backend ('cpu', 'gpu', 'tpu')
            context_len: Context window length
            horizon_len: Forecast horizon length
            checkpoint: HuggingFace checkpoint repo ID
            local_model_path: Local model file path

        Returns:
            Tuple of (success, initialization_result)
        """
        data = {
            'backend': backend,
            'context_len': context_len,
            'horizon_len': horizon_len
        }

        if checkpoint:
            data['checkpoint'] = checkpoint
        if local_model_path:
            data['local_model_path'] = local_model_path

        logger.info(f"Initializing model: {data}")
        return self._make_request(
            'POST',
            '/forecast/v1/timesfm20/initialization',
            data=data,
            timeout=300  # 5 minutes for model loading
        )

    def run_inference(
        self,
        data_source: str,
        data_definition: Dict[str, str],
        parameters: Dict[str, Any]
    ) -> Tuple[bool, Dict]:
        """
        Run inference on the provided data.

        Args:
            data_source: Path or URL to data source
            data_definition: Column type definitions
            parameters: Inference parameters

        Returns:
            Tuple of (success, inference_result)
        """
        data = {
            'data_source_url_or_path': data_source,
            'data_definition': data_definition,
            'parameters': parameters
        }

        logger.info(f"Running inference on: {data_source}")
        return self._make_request(
            'POST',
            '/forecast/v1/timesfm20/inference',
            data=data,
            timeout=300  # 5 minutes for inference
        )

    def shutdown_model(self) -> Tuple[bool, Dict]:
        """
        Shutdown the model and free resources.

        Returns:
            Tuple of (success, shutdown_result)
        """
        logger.info("Shutting down model")
        return self._make_request(
            'POST',
            '/forecast/v1/timesfm20/shutdown',
            timeout=30
        )
