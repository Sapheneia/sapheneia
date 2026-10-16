"""
Integration tests for path handling across different environments.

Tests ensure that path handling works consistently in both Docker and venv
environments, addressing the critical issues from Phase 2.
"""

from pathlib import Path

import pytest

# Import IS_DOCKER to use in skipif markers
from forecast.core.paths import IS_DOCKER


class TestVenvEnvironment:
    """Test path resolution in venv environment."""

    @pytest.mark.skipif(IS_DOCKER, reason="Test only applies when NOT in Docker")
    def test_venv_path_resolution(self):
        """Test that paths resolve correctly in venv environment."""
        from forecast.core.paths import normalize_data_path

        result = normalize_data_path("test.csv")

        # Should not start with /app in venv
        assert not str(result).startswith("/app")
        assert "data" in str(result)
        assert "uploads" in str(result)

    @pytest.mark.skipif(IS_DOCKER, reason="Test only applies when NOT in Docker")
    def test_venv_converts_docker_paths(self):
        """Test that Docker-style paths are converted in venv."""
        from forecast.core.paths import normalize_data_path

        # Simulate getting a Docker-style path
        docker_path = "/app/data/uploads/test.csv"
        result = normalize_data_path(docker_path)

        # Should not start with /app
        result_str = str(result)
        assert not result_str.startswith("/app"), f"Path still starts with /app: {result_str}"


class TestDockerEnvironment:
    """Test path resolution in Docker environment."""

    @pytest.mark.skipif(not IS_DOCKER, reason="Test only applies when IN Docker")
    def test_docker_path_resolution(self):
        """Test that paths resolve correctly in Docker environment."""
        from forecast.core.paths import normalize_data_path

        result = normalize_data_path("test.csv")

        # Should start with /app in Docker
        assert str(result).startswith("/app/data/uploads")

    @pytest.mark.skipif(not IS_DOCKER, reason="Test only applies when IN Docker")
    def test_docker_handles_venv_paths(self):
        """Test that venv-style paths work in Docker."""
        from forecast.core.paths import normalize_data_path

        # Relative path should resolve to Docker path
        result = normalize_data_path("data/uploads/test.csv")
        assert str(result).startswith("/app")


class TestCrossEnvironmentCompatibility:
    """Test that path handling works across environment boundaries."""

    def test_local_prefix_stripped_both_environments(self):
        """Test that local:// prefix is stripped in both environments."""
        from forecast.core.paths import normalize_data_path

        result = normalize_data_path("local://test.csv")
        assert "local://" not in str(result)

    def test_security_validation_both_environments(self):
        """Test that security validation works in both environments."""
        from forecast.core.paths import normalize_data_path

        with pytest.raises(ValueError, match="outside allowed"):
            normalize_data_path("../../../etc/passwd")

    def test_bare_filename_both_environments(self):
        """Test that bare filenames work in both environments."""
        from forecast.core.paths import normalize_data_path

        result = normalize_data_path("file.csv")

        # Should resolve to uploads directory
        assert "uploads" in str(result)
        assert result.name == "file.csv"


class TestRealEnvironment:
    """Test path handling in the actual runtime environment."""

    def test_current_environment_paths(self):
        """Test path handling in the actual environment we're running in."""
        from forecast.core.paths import IS_DOCKER, normalize_data_path

        # Test basic filename resolution
        result = normalize_data_path("test.csv")

        # Should resolve to a valid path
        assert isinstance(result, Path)
        assert "uploads" in str(result)

        # Environment-specific checks
        if IS_DOCKER:
            assert str(result).startswith("/app")
        else:
            # In venv, path should be relative to project
            assert not str(result).startswith("/app")

    def test_current_environment_security(self):
        """Test security validation in current environment."""
        from forecast.core.paths import normalize_data_path

        # Path traversal should always fail
        with pytest.raises(ValueError, match="outside allowed"):
            normalize_data_path("../../../etc/passwd")


class TestPathConsistency:
    """Test that path handling is consistent across different scenarios."""

    def test_same_input_different_formats(self):
        """Test that different path formats for same file give consistent results."""
        from forecast.core.paths import normalize_data_path

        formats = [
            "test.csv",
            "data/uploads/test.csv",
            "local://test.csv",
            "local://data/uploads/test.csv",
        ]

        # All should resolve to the same filename (even if exact paths differ)
        results = [normalize_data_path(fmt) for fmt in formats]

        # All should have the same filename
        filenames = [r.name for r in results]
        assert len(set(filenames)) == 1

        # All should be in uploads directory
        for result in results:
            assert "uploads" in str(result)
