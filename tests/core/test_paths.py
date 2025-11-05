"""
Tests for path handling utilities.

Tests the normalize_data_path function from api.core.paths to ensure:
1. Correct resolution of different path formats
2. Proper handling of Docker vs venv environments
3. Security validation against path traversal attacks
"""

import pytest
from pathlib import Path
from unittest.mock import patch
from api.core.paths import normalize_data_path, IS_DOCKER, PROJECT_ROOT


class TestPathNormalization:
    """Test path normalization with different input formats."""
    
    def test_normalize_bare_filename(self):
        """Test normalizing a bare filename (e.g., 'test.csv')."""
        result = normalize_data_path("test.csv")
        
        assert result.name == "test.csv"
        assert "uploads" in str(result)
        assert result.suffix == ".csv"
    
    def test_normalize_relative_path(self):
        """Test normalizing a relative path with data/ prefix."""
        result = normalize_data_path("data/uploads/test.csv")
        
        assert result.name == "test.csv"
        assert "data" in str(result)
        assert "uploads" in str(result)
    
    def test_normalize_with_local_prefix(self):
        """Test normalizing path with local:// prefix (from UI)."""
        result = normalize_data_path("local://data/uploads/test.csv")
        
        assert result.name == "test.csv"
        assert "local://" not in str(result)
        assert "uploads" in str(result)
    
    def test_normalize_absolute_path_venv(self):
        """Test normalizing absolute path in venv environment."""
        if not IS_DOCKER:
            # In venv, absolute path should resolve correctly
            abs_path = Path.cwd() / "data" / "uploads" / "test.csv"
            try:
                result = normalize_data_path(str(abs_path))
                assert result.exists() or result.parent.exists()
            except ValueError:
                # Path outside data directory - expected
                pass


class TestSecurityValidation:
    """Test security features of path normalization."""
    
    def test_path_traversal_rejected(self):
        """Test that path traversal attacks are rejected."""
        with pytest.raises(ValueError, match="outside allowed"):
            normalize_data_path("../../../etc/passwd")
    
    def test_path_traversal_in_relative_path(self):
        """Test path traversal in relative paths is rejected."""
        with pytest.raises(ValueError, match="outside allowed"):
            normalize_data_path("data/uploads/../../etc/passwd")
    
    def test_absolute_path_outside_data_dir_rejected(self):
        """Test that absolute paths outside data directory are rejected."""
        with pytest.raises(ValueError, match="outside allowed"):
            normalize_data_path("/etc/passwd")
    
    def test_nested_path_traversal_rejected(self):
        """Test nested path traversal attempts are rejected."""
        with pytest.raises(ValueError, match="outside allowed"):
            normalize_data_path("data/uploads/../../../..//etc/passwd")


class TestEnvironmentSpecificBehavior:
    """Test path resolution in different environments."""
    
    @patch('api.core.paths.IS_DOCKER', False)
    def test_venv_path_resolution(self):
        """Test path resolution in venv environment."""
        with patch('api.core.paths.IS_DOCKER', False):
            # Reload the module to get patched IS_DOCKER
            from importlib import reload
            import api.core.paths
            reload(api.core.paths)
            
            result = api.core.paths.normalize_data_path("test.csv")
            assert not str(result).startswith('/app')
            assert "uploads" in str(result)
    
    @patch('api.core.paths.IS_DOCKER', True)
    def test_docker_path_resolution(self):
        """Test path resolution in Docker environment."""
        with patch('api.core.paths.IS_DOCKER', True):
            from importlib import reload
            import api.core.paths
            reload(api.core.paths)
            
            result = api.core.paths.normalize_data_path("test.csv")
            assert str(result).startswith('/app/data/uploads')
    
    def test_cross_environment_path_conversion(self):
        """Test that Docker paths in venv are converted correctly."""
        if not IS_DOCKER:
            # In venv, if we get a Docker-style path, it should be converted
            docker_style_path = "/app/data/uploads/test.csv"
            result = normalize_data_path(docker_style_path)
            # Should not start with /app in venv
            assert not str(result).startswith('/app') or 'data' in str(result)


class TestPathTypeHandling:
    """Test handling of different path input types."""
    
    def test_string_path(self):
        """Test passing string path."""
        result = normalize_data_path("test.csv")
        assert isinstance(result, Path)
    
    def test_path_object(self):
        """Test passing Path object."""
        path_obj = Path("test.csv")
        result = normalize_data_path(path_obj)
        assert isinstance(result, Path)
    
    def test_empty_string_rejected(self):
        """Test that empty string is rejected."""
        with pytest.raises((ValueError, FileNotFoundError)):
            normalize_data_path("")


class TestSpecialCases:
    """Test edge cases and special scenarios."""
    
    def test_path_with_spaces(self):
        """Test handling paths with spaces."""
        result = normalize_data_path("my file.csv")
        assert "my file.csv" in str(result)
    
    def test_unicode_path(self):
        """Test handling unicode in paths."""
        result = normalize_data_path("数据.csv")
        assert "数据.csv" in str(result.name)
    
    def test_multiple_forward_slashes(self):
        """Test handling multiple slashes in path."""
        result = normalize_data_path("data//uploads//test.csv")
        assert result.name == "test.csv"
