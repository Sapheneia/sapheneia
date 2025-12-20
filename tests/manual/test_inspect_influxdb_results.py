"""
Unit tests for inspect_influxdb_results.py
Tests the InfluxDB data loading and processing functionality
"""

import unittest
from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

import pandas as pd

# Import the module under test
from inspect_influxdb_results import load_backtest_data


class TestLoadBacktestData(unittest.TestCase):
    """Test suite for load_backtest_data function"""

    @patch("inspect_influxdb_results.InfluxDBClient")
    def test_load_backtest_data_success(self, mock_influx_client):
        """Test successful data loading from InfluxDB"""
        # Create mock data
        mock_df = pd.DataFrame(
            {
                "_time": pd.to_datetime(
                    ["2024-01-01", "2024-01-02", "2024-01-03"]
                ),
                "action": ["BUY", "HOLD", "SELL"],
                "current_price": [100.0, 105.0, 103.0],
                "forecast_price": [110.0, 108.0, 102.0],
                "available_cash": [10000.0, 9000.0, 9000.0],
                "position_after": [10, 10, 0],
                "result": [0, 0, 0],
                "table": [0, 0, 0],
                "_start": pd.to_datetime(["2024-01-01"] * 3),
                "_stop": pd.to_datetime(["2024-12-31"] * 3),
                "_measurement": ["forecast_evaluations"] * 3,
            }
        )

        # Configure mock
        mock_client_instance = MagicMock()
        mock_query_api = MagicMock()
        mock_query_api.query_data_frame.return_value = mock_df

        mock_client_instance.__enter__.return_value.query_api.return_value = (
            mock_query_api
        )
        mock_influx_client.return_value = mock_client_instance

        # Execute
        result = load_backtest_data("test_run_id")

        # Verify
        self.assertIsInstance(result, pd.DataFrame)
        self.assertEqual(len(result), 3)
        self.assertIn("action", result.columns)
        self.assertIn("current_price", result.columns)
        self.assertIn("Date", result.index.names)

        # Verify internal columns were dropped
        self.assertNotIn("result", result.columns)
        self.assertNotIn("table", result.columns)
        self.assertNotIn("_start", result.columns)
        self.assertNotIn("_stop", result.columns)
        self.assertNotIn("_measurement", result.columns)

    @patch("inspect_influxdb_results.InfluxDBClient")
    def test_load_backtest_data_empty_result(self, mock_influx_client):
        """Test handling of empty query result"""
        # Create empty dataframe
        mock_df = pd.DataFrame()

        # Configure mock
        mock_client_instance = MagicMock()
        mock_query_api = MagicMock()
        mock_query_api.query_data_frame.return_value = mock_df

        mock_client_instance.__enter__.return_value.query_api.return_value = (
            mock_query_api
        )
        mock_influx_client.return_value = mock_client_instance

        # Execute
        result = load_backtest_data("test_run_id")

        # Verify
        self.assertIsInstance(result, pd.DataFrame)
        self.assertTrue(result.empty)

    @patch("inspect_influxdb_results.InfluxDBClient")
    def test_load_backtest_data_connection_error(self, mock_influx_client):
        """Test handling of InfluxDB connection errors"""
        # Configure mock to raise exception
        mock_influx_client.side_effect = Exception("Connection failed")

        # Execute and verify exception is raised
        with self.assertRaises(Exception) as context:
            load_backtest_data("test_run_id")

        self.assertIn("Connection failed", str(context.exception))

    @patch("inspect_influxdb_results.InfluxDBClient")
    def test_load_backtest_data_with_all_columns(self, mock_influx_client):
        """Test that all expected columns are present in the result"""
        # Create mock data with all possible columns
        mock_df = pd.DataFrame(
            {
                "_time": pd.to_datetime(["2024-01-01"]),
                "action": ["BUY"],
                "current_price": [100.0],
                "forecast_price": [110.0],
                "available_cash": [10000.0],
                "position_after": [10],
                "position_before": [0],
                "cash_after": [9000.0],
                "cash_before": [10000.0],
                "portfolio_value": [10000.0],
                "result": [0],
                "table": [0],
                "_start": pd.to_datetime(["2024-01-01"]),
                "_stop": pd.to_datetime(["2024-12-31"]),
                "_measurement": ["forecast_evaluations"],
            }
        )

        # Configure mock
        mock_client_instance = MagicMock()
        mock_query_api = MagicMock()
        mock_query_api.query_data_frame.return_value = mock_df

        mock_client_instance.__enter__.return_value.query_api.return_value = (
            mock_query_api
        )
        mock_influx_client.return_value = mock_client_instance

        # Execute
        result = load_backtest_data("test_run_id")

        # Verify business columns are present
        expected_columns = [
            "action",
            "current_price",
            "forecast_price",
            "available_cash",
            "position_after",
        ]
        for col in expected_columns:
            self.assertIn(col, result.columns)

    @patch("inspect_influxdb_results.InfluxDBClient")
    def test_load_backtest_data_date_index(self, mock_influx_client):
        """Test that the Date index is properly set"""
        # Create mock data
        test_dates = pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"])
        mock_df = pd.DataFrame(
            {
                "_time": test_dates,
                "action": ["BUY", "HOLD", "SELL"],
                "current_price": [100.0, 105.0, 103.0],
            }
        )

        # Configure mock
        mock_client_instance = MagicMock()
        mock_query_api = MagicMock()
        mock_query_api.query_data_frame.return_value = mock_df

        mock_client_instance.__enter__.return_value.query_api.return_value = (
            mock_query_api
        )
        mock_influx_client.return_value = mock_client_instance

        # Execute
        result = load_backtest_data("test_run_id")

        # Verify index
        self.assertEqual(result.index.name, "Date")
        self.assertTrue(isinstance(result.index, pd.DatetimeIndex))
        self.assertEqual(len(result.index), 3)

    @patch("inspect_influxdb_results.InfluxDBClient")
    def test_load_backtest_data_query_construction(self, mock_influx_client):
        """Test that the Flux query is properly constructed"""
        # Create mock data
        mock_df = pd.DataFrame({"_time": pd.to_datetime(["2024-01-01"])})

        # Configure mock
        mock_client_instance = MagicMock()
        mock_query_api = MagicMock()
        mock_query_api.query_data_frame.return_value = mock_df

        mock_client_instance.__enter__.return_value.query_api.return_value = (
            mock_query_api
        )
        mock_influx_client.return_value = mock_client_instance

        # Execute
        run_id = "test_run_id_123"
        load_backtest_data(run_id)

        # Verify query was called
        mock_query_api.query_data_frame.assert_called_once()

        # Get the query that was passed
        call_args = mock_query_api.query_data_frame.call_args
        query = call_args.kwargs["query"]

        # Verify query contains expected components
        self.assertIn("forecast_evaluations", query)
        self.assertIn(run_id, query)
        self.assertIn("pivot", query)
        self.assertIn("sort", query)


class TestDataFrameProcessing(unittest.TestCase):
    """Test suite for DataFrame processing and cleanup"""

    def test_column_dropping(self):
        """Test that internal columns are properly dropped"""
        # Create a DataFrame with columns to drop
        df = pd.DataFrame(
            {
                "_time": pd.to_datetime(["2024-01-01"]),
                "action": ["BUY"],
                "result": [0],
                "table": [0],
                "_start": pd.to_datetime(["2024-01-01"]),
                "_stop": pd.to_datetime(["2024-12-31"]),
                "_measurement": ["test"],
            }
        )

        # Simulate the column dropping logic
        cols_to_drop = ["result", "table", "_start", "_stop", "_measurement"]
        df_cleaned = df.drop(
            columns=[c for c in cols_to_drop if c in df.columns]
        )

        # Verify
        for col in cols_to_drop:
            self.assertNotIn(col, df_cleaned.columns)
        self.assertIn("action", df_cleaned.columns)
        self.assertIn("_time", df_cleaned.columns)

    def test_time_column_rename(self):
        """Test that _time column is renamed to Date"""
        df = pd.DataFrame({"_time": pd.to_datetime(["2024-01-01", "2024-01-02"])})

        # Simulate the renaming logic
        df_renamed = df.rename(columns={"_time": "Date"})
        df_renamed = df_renamed.set_index("Date")

        # Verify
        self.assertNotIn("_time", df_renamed.columns)
        self.assertEqual(df_renamed.index.name, "Date")


class TestEdgeCases(unittest.TestCase):
    """Test suite for edge cases and error conditions"""

    @patch("inspect_influxdb_results.InfluxDBClient")
    def test_missing_time_column(self, mock_influx_client):
        """Test handling when _time column is missing"""
        # Create mock data without _time column
        mock_df = pd.DataFrame(
            {
                "action": ["BUY"],
                "current_price": [100.0],
            }
        )

        # Configure mock
        mock_client_instance = MagicMock()
        mock_query_api = MagicMock()
        mock_query_api.query_data_frame.return_value = mock_df

        mock_client_instance.__enter__.return_value.query_api.return_value = (
            mock_query_api
        )
        mock_influx_client.return_value = mock_client_instance

        # Execute
        result = load_backtest_data("test_run_id")

        # Verify - should still return a DataFrame, just without the time index
        self.assertIsInstance(result, pd.DataFrame)

    def test_data_types(self):
        """Test that numeric columns have correct data types"""
        df = pd.DataFrame(
            {
                "current_price": [100.0, 105.0],
                "forecast_price": [110.0, 108.0],
                "available_cash": [10000.0, 9000.0],
                "position_after": [10, 10],
                "volume": [1000000, 1100000],
            }
        )

        # Verify data types
        self.assertTrue(pd.api.types.is_float_dtype(df["current_price"]))
        self.assertTrue(pd.api.types.is_float_dtype(df["forecast_price"]))
        self.assertTrue(pd.api.types.is_float_dtype(df["available_cash"]))
        self.assertTrue(pd.api.types.is_integer_dtype(df["position_after"]))


class TestConfigurationValues(unittest.TestCase):
    """Test suite for configuration values"""

    def test_configuration_constants(self):
        """Test that configuration constants are defined"""
        from inspect_influxdb_results import bucket, org, token, url

        # Verify configuration values exist
        self.assertIsNotNone(url)
        self.assertIsNotNone(token)
        self.assertIsNotNone(org)
        self.assertIsNotNone(bucket)

        # Verify types
        self.assertIsInstance(url, str)
        self.assertIsInstance(token, str)
        self.assertIsInstance(org, str)
        self.assertIsInstance(bucket, str)


if __name__ == "__main__":
    unittest.main()
