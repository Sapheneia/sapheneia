"""
Tests for shared/errors.py

Tests the shared error hierarchy, error codes, and FastAPI error handler registration.
"""

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from shared.errors import (
    SapheneiaError,
    ValidationError,
    ModelUnavailableError,
    ServiceUnavailableError,
    ServiceTimeoutError,
    InsufficientDataError,
    ComputationError,
    ErrorCode,
    register_error_handlers,
)


# =============================================================================
# ErrorCode Enum
# =============================================================================

class TestErrorCode:
    """Tests for ErrorCode enum values."""

    def test_all_error_codes_exist(self):
        """All expected error codes should be defined."""
        expected = [
            "VALIDATION_ERROR",
            "INVALID_MODEL",
            "INSUFFICIENT_DATA",
            "MODEL_UNAVAILABLE",
            "SERVICE_UNAVAILABLE",
            "COMPUTATION_ERROR",
            "TIMEOUT",
        ]
        for code in expected:
            assert hasattr(ErrorCode, code)

    def test_error_codes_are_strings(self):
        """Error codes should be string values."""
        assert ErrorCode.VALIDATION_ERROR == "VALIDATION_ERROR"
        assert ErrorCode.TIMEOUT == "TIMEOUT"


# =============================================================================
# SapheneiaError Base Class
# =============================================================================

class TestSapheneiaError:
    """Tests for SapheneiaError base class."""

    def test_default_values(self):
        """Base error should have correct defaults."""
        err = SapheneiaError("something broke")
        assert err.message == "something broke"
        assert err.error_code == "SAPHENEIA_ERROR"
        assert err.details == {}
        assert err.suggested_status_code == 500

    def test_custom_values(self):
        """Base error should accept custom values."""
        err = SapheneiaError(
            message="custom msg",
            error_code="CUSTOM",
            details={"key": "val"},
            suggested_status_code=418,
        )
        assert err.message == "custom msg"
        assert err.error_code == "CUSTOM"
        assert err.details == {"key": "val"}
        assert err.suggested_status_code == 418

    def test_to_dict(self):
        """to_dict should return structured error dict."""
        err = SapheneiaError("test", error_code="TEST", details={"a": 1})
        d = err.to_dict()
        assert d == {
            "error": "TEST",
            "message": "test",
            "details": {"a": 1},
        }

    def test_is_exception(self):
        """SapheneiaError should be an Exception subclass."""
        err = SapheneiaError("msg")
        assert isinstance(err, Exception)
        assert str(err) == "msg"


# =============================================================================
# Error Subclasses
# =============================================================================

class TestValidationError:
    """Tests for ValidationError."""

    def test_defaults(self):
        err = ValidationError()
        assert err.message == "Validation error"
        assert err.error_code == ErrorCode.VALIDATION_ERROR
        assert err.suggested_status_code == 400

    def test_custom_message(self):
        err = ValidationError("bad input", details={"field": "x"})
        assert err.message == "bad input"
        assert err.details == {"field": "x"}


class TestModelUnavailableError:
    """Tests for ModelUnavailableError."""

    def test_defaults(self):
        err = ModelUnavailableError()
        assert err.error_code == ErrorCode.MODEL_UNAVAILABLE
        assert err.suggested_status_code == 503


class TestServiceUnavailableError:
    """Tests for ServiceUnavailableError."""

    def test_defaults(self):
        err = ServiceUnavailableError()
        assert err.error_code == ErrorCode.SERVICE_UNAVAILABLE
        assert err.suggested_status_code == 503


class TestServiceTimeoutError:
    """Tests for ServiceTimeoutError."""

    def test_defaults(self):
        err = ServiceTimeoutError()
        assert err.error_code == ErrorCode.TIMEOUT
        assert err.suggested_status_code == 504


class TestInsufficientDataError:
    """Tests for InsufficientDataError."""

    def test_defaults(self):
        err = InsufficientDataError()
        assert err.error_code == ErrorCode.INSUFFICIENT_DATA
        assert err.suggested_status_code == 400


class TestComputationError:
    """Tests for ComputationError."""

    def test_defaults(self):
        err = ComputationError()
        assert err.error_code == ErrorCode.COMPUTATION_ERROR
        assert err.suggested_status_code == 500


# =============================================================================
# register_error_handlers
# =============================================================================

@pytest.fixture
def error_app():
    """Create a FastAPI app with error handlers registered."""
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/raise-validation")
    async def raise_validation():
        raise ValidationError("bad field", details={"field": "name"})

    @app.get("/raise-timeout")
    async def raise_timeout():
        raise ServiceTimeoutError("timed out", details={"timeout": 30})

    @app.get("/raise-generic")
    async def raise_generic():
        raise RuntimeError("unexpected")

    return app


@pytest.fixture
def error_client(error_app):
    return TestClient(error_app, raise_server_exceptions=False)


class TestRegisterErrorHandlers:
    """Tests for register_error_handlers."""

    def test_sapheneia_error_returns_structured_json(self, error_client):
        """SapheneiaError should return structured JSON with correct status."""
        resp = error_client.get("/raise-validation")
        assert resp.status_code == 400
        body = resp.json()
        assert body["error"] == "VALIDATION_ERROR"
        assert body["message"] == "bad field"
        assert "request_id" in body["details"]

    def test_timeout_error_returns_504(self, error_client):
        """ServiceTimeoutError should return 504."""
        resp = error_client.get("/raise-timeout")
        assert resp.status_code == 504
        body = resp.json()
        assert body["error"] == "TIMEOUT"

    def test_generic_exception_returns_500(self, error_client):
        """Unhandled exceptions should return 500 with generic message, no leakage."""
        resp = error_client.get("/raise-generic")
        assert resp.status_code == 500
        body = resp.json()
        assert body["error"] == "INTERNAL_ERROR"
        assert "request_id" in body["details"]
        assert body["details"]["error_type"] == "RuntimeError"
        # Verify the user-facing message is generic, not the original error
        assert body["message"] == "An unexpected error occurred. Please contact support."

    def test_error_response_has_request_id(self, error_client):
        """All error responses should include request_id in details."""
        resp = error_client.get("/raise-validation")
        body = resp.json()
        assert "request_id" in body["details"]
