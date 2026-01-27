"""
Tests for data fetching utilities.

Tests the fetch_data_source function and related utilities from forecast.core.data.
"""

import pytest
from pathlib import Path
import pandas as pd
from unittest.mock import patch, MagicMock
from forecast.core.data import fetch_data_source, DataFetchError, _fetch_local_file
from forecast.core.paths import normalize_data_path, DATA_DIR


class TestDataFetching:
    """Test data fetching from various sources."""

    def test_fetch_nonexistent_file(self):
        """Test that nonexistent files raise FileNotFoundError."""
        # Use a path within the data directory that doesn't exist
        with pytest.raises(FileNotFoundError):
            fetch_data_source("definitely_nonexistent_file_12345.csv")

    def test_fetch_valid_csv_file(self, sample_data_file_in_uploads):
        """Test fetching a valid CSV file."""
        # Use the sample data file from fixtures (created in data/uploads)
        result = fetch_data_source(str(sample_data_file_in_uploads))

        assert isinstance(result, pd.DataFrame)
        assert not result.empty
        assert 'date' in result.columns
        assert 'value' in result.columns

    def test_fetch_file_with_bare_filename(self, sample_data_file_in_uploads):
        """Test fetching with just a filename."""
        # Test that bare filenames are resolved to the uploads directory
        filename = sample_data_file_in_uploads.name
        result = fetch_data_source(filename)

        assert isinstance(result, pd.DataFrame)
        assert not result.empty


class TestLocalFileFetching:
    """Test _fetch_local_file function directly."""

    def test_fetch_nonexistent_local_file(self):
        """Test that nonexistent local files raise FileNotFoundError."""
        fake_path = normalize_data_path("definitely_does_not_exist.csv")

        with pytest.raises(FileNotFoundError):
            _fetch_local_file(fake_path)

    def test_fetch_file_with_invalid_extension(self, sample_txt_file_in_uploads):
        """Test that files with unsupported extensions raise DataFetchError."""
        # The sample_txt_file_in_uploads is created in data/uploads
        normalized_path = normalize_data_path(sample_txt_file_in_uploads.name)

        # This would fail validation - unsupported extension
        with pytest.raises(DataFetchError, match="Unsupported file format"):
            _fetch_local_file(normalized_path)


class TestDataValidation:
    """Test data validation functions."""

    def test_csv_structure_validation(self, sample_data_file_in_uploads):
        """Test that fetched CSV has expected structure."""
        df = fetch_data_source(str(sample_data_file_in_uploads))

        # Should have required columns
        assert 'date' in df.columns
        assert len(df) > 0

        # Should be a proper DataFrame
        assert isinstance(df, pd.DataFrame)
        assert not df.empty


class TestSecurityBoundaries:
    """Test that security boundaries are enforced."""

    def test_path_outside_data_dir_rejected(self, tmp_path):
        """Test that paths outside data directory are rejected."""
        # Create a file outside the data directory
        outside_file = tmp_path / "outside.csv"
        outside_file.write_text("date,value\n2023-01-01,100")

        with pytest.raises(ValueError, match="outside allowed"):
            fetch_data_source(str(outside_file))

    def test_path_traversal_rejected(self):
        """Test that path traversal attempts are rejected."""
        with pytest.raises(ValueError, match="outside allowed"):
            fetch_data_source("../../../etc/passwd")


@pytest.mark.slow
class TestHTTPDataFetching:
    """Test fetching data from HTTP sources."""

    def test_fetch_from_invalid_url(self):
        """Test that invalid URLs raise appropriate errors."""
        with pytest.raises((DataFetchError, ValueError)):
            fetch_data_source("http://nonexistent-url-12345.com/data.csv")


# Fixtures specific to test_data.py
@pytest.fixture
def sample_data_file_in_uploads():
    """Create a sample CSV file in the actual data/uploads directory."""
    import pandas as pd

    # Create sample data
    data = {
        "date": [f"2023-01-{i:02d}" for i in range(1, 31)],
        "value": [100.0 + i * 0.5 for i in range(30)]
    }
    df = pd.DataFrame(data)

    # Create the file in the actual data/uploads directory
    uploads_dir = DATA_DIR / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)

    file_path = uploads_dir / "test_sample_data.csv"
    df.to_csv(file_path, index=False)

    yield file_path

    # Cleanup
    if file_path.exists():
        file_path.unlink()


@pytest.fixture
def sample_txt_file_in_uploads():
    """Create a sample TXT file in the actual data/uploads directory."""
    # Create the file in the actual data/uploads directory
    uploads_dir = DATA_DIR / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)

    file_path = uploads_dir / "test_invalid.txt"
    file_path.write_text("some content")

    yield file_path

    # Cleanup
    if file_path.exists():
        file_path.unlink()
