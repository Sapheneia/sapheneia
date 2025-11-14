"""
Sapheneia TimesFM Web Application (API-Integrated Version)

A Flask-based web application for TimesFM forecasting that communicates
with the FastAPI backend via REST API.

Features:
- File upload for CSV data
- Interactive parameter configuration
- Real-time forecasting via REST API
- Professional visualizations
- Downloadable results
- Support for covariates and quantile forecasting
"""

import os
import sys
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

# Optional: python-magic for MIME type detection (requires libmagic system library)
try:
    import magic
    MAGIC_AVAILABLE = True
except ImportError:
    MAGIC_AVAILABLE = False
    logging.warning("python-magic not available. MIME type validation will be skipped.")

import pandas as pd
import numpy as np
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, flash
from werkzeug.utils import secure_filename
import tempfile
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# Import visualization module - use absolute import for Flask compatibility
# When Flask runs as script, relative imports don't work, so we use sys.path
sys.path.append(os.path.join(os.path.dirname(__file__)))  # Add ui/ to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))  # Add project root
from visualization import InteractiveVisualizer
from forecast.core.forecasting import process_quantile_bands
from api_client import SapheneiaAPIClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-change-this-in-production')

# Import path utilities AFTER logging is configured (lazy import)
from pathlib import Path as PathClass
try:
    sys.path.append(str(PathClass(__file__).parent.parent))
    from forecast.core.paths import IS_DOCKER, get_upload_path, get_result_path
    
    # Use centralized path utilities
    UPLOAD_FOLDER = str(get_upload_path('').resolve())
    RESULTS_FOLDER = str(get_result_path('').resolve())
    
    logger.info(f"UI path configuration: IS_DOCKER={IS_DOCKER}")
    logger.info(f"UPLOAD_FOLDER={UPLOAD_FOLDER}")
    logger.info(f"RESULTS_FOLDER={RESULTS_FOLDER}")
except Exception as e:
    # Fallback to original path handling if import fails
    logger.warning(f"Could not import path utilities, using fallback: {e}")
    IS_DOCKER = os.path.exists('/app')
    
    if IS_DOCKER:
        UPLOAD_FOLDER = '/app/data/uploads'
        RESULTS_FOLDER = '/app/data/results'
    else:
        PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        UPLOAD_FOLDER = os.path.join(PROJECT_ROOT, 'data', 'uploads')
        RESULTS_FOLDER = os.path.join(PROJECT_ROOT, 'data', 'results')
    
    logger.info(f"Using fallback paths: UPLOAD_FOLDER={UPLOAD_FOLDER}")

ALLOWED_EXTENSIONS = {'csv'}
MAX_FILE_SIZE = 16 * 1024 * 1024  # 16MB
ALLOWED_MIME_TYPES = {
    'text/csv',
    'text/plain',
    'application/csv',
    'application/vnd.ms-excel'  # Sometimes CSV files have this MIME type
}
MAX_COLUMNS = 1000  # Prevent extremely wide files
MAX_ROWS_PREVIEW = 100000  # Limit rows for preview/validation

# Ensure directories exist
for folder in [UPLOAD_FOLDER, RESULTS_FOLDER]:
    os.makedirs(folder, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['RESULTS_FOLDER'] = RESULTS_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

# Initialize API client
api_client = SapheneiaAPIClient()

# Global visualizer (UI handles visualization locally)
current_visualizer = InteractiveVisualizer(style="professional")


def allowed_file(filename):
    """Check if file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def validate_file_content(file_path: str) -> tuple[bool, Optional[str]]:
    """
    Validate file content for security and format.

    Args:
        file_path: Path to the uploaded file

    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        # 1. Check MIME type (if available)
        if MAGIC_AVAILABLE:
            try:
                mime = magic.Magic(mime=True)
                file_mime = mime.from_file(file_path)

                if file_mime not in ALLOWED_MIME_TYPES:
                    return False, f"Invalid file type detected: {file_mime}. Only CSV files are allowed."
            except Exception as e:
                logger.warning(f"MIME type detection failed (continuing): {e}")
        else:
            logger.debug("MIME type validation skipped (libmagic not available)")

        # 2. Check file size
        file_size = os.path.getsize(file_path)
        if file_size > MAX_FILE_SIZE:
            return False, f"File too large: {file_size / 1024 / 1024:.2f}MB (max: {MAX_FILE_SIZE / 1024 / 1024}MB)"

        if file_size == 0:
            return False, "File is empty"

        # 3. Try to read as CSV and validate structure
        try:
            df = pd.read_csv(file_path, nrows=MAX_ROWS_PREVIEW)
        except Exception as e:
            return False, f"File is not a valid CSV: {str(e)}"

        # 4. Validate CSV structure
        if df.empty:
            return False, "CSV file contains no data"

        if len(df.columns) > MAX_COLUMNS:
            return False, f"Too many columns: {len(df.columns)} (max: {MAX_COLUMNS})"

        # 5. Check for suspicious content (basic check)
        # Look for common script injection patterns in column names
        suspicious_patterns = ['<script', 'javascript:', 'onerror=', 'onclick=']
        for col in df.columns:
            col_lower = str(col).lower()
            if any(pattern in col_lower for pattern in suspicious_patterns):
                return False, f"Suspicious content detected in column name: {col}"

        return True, None

    except Exception as e:
        logger.error(f"File validation error: {str(e)}")
        return False, f"File validation failed: {str(e)}"


@app.route('/')
def index():
    """Main page."""
    return render_template('index.html')


@app.route('/api/model/init', methods=['POST'])
def api_init_model():
    """Initialize TimesFM model via API."""
    try:
        data = request.get_json()

        backend = data.get('backend', 'cpu')
        context_len = int(data.get('context_len', 64))
        horizon_len = int(data.get('horizon_len', 24))
        checkpoint = data.get('checkpoint')
        local_path = data.get('local_path')

        # Use default checkpoint if none specified
        if not checkpoint and not local_path:
            checkpoint = "google/timesfm-2.0-500m-pytorch"

        logger.info(f"Initializing model via API: backend={backend}, context={context_len}, horizon={horizon_len}")

        # Call API to initialize model
        success, result = api_client.initialize_model(
            backend=backend,
            context_len=context_len,
            horizon_len=horizon_len,
            checkpoint=checkpoint,
            local_model_path=local_path
        )

        if success:
            logger.info("Model initialized successfully via API")
            return jsonify({
                'success': True,
                'message': result.get('message', 'Model initialized'),
                'model_info': result.get('model_info')
            })
        else:
            logger.error(f"Model initialization failed: {result}")
            return jsonify({
                'success': False,
                'message': f'Initialization failed: {result}'
            }), 500

    except Exception as e:
        logger.error(f"API model init error: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/data/upload', methods=['POST'])
def api_upload_data():
    """Upload and process CSV data (same as before - file handling remains local)."""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': 'No file uploaded'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'message': 'No file selected'}), 400

        if not allowed_file(file.filename):
            return jsonify({'success': False, 'message': 'Invalid file type. Only CSV files allowed.'}), 400

        # Save uploaded file with secure filename
        filename = secure_filename(file.filename)

        # Additional filename validation
        if not filename or filename == '' or '..' in filename:
            return jsonify({'success': False, 'message': 'Invalid filename'}), 400

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

        # Ensure the filepath is within UPLOAD_FOLDER (prevent path traversal)
        abs_upload_folder = os.path.abspath(app.config['UPLOAD_FOLDER'])
        abs_filepath = os.path.abspath(filepath)
        if not abs_filepath.startswith(abs_upload_folder):
            logger.error(f"Path traversal attempt detected: {filepath}")
            return jsonify({'success': False, 'message': 'Invalid file path'}), 400

        try:
            file.save(filepath)
            logger.info(f"File saved successfully: {filepath}")

            # Validate file content
            is_valid, error_msg = validate_file_content(filepath)
            if not is_valid:
                # Delete the invalid file
                try:
                    os.remove(filepath)
                except Exception:
                    pass
                logger.warning(f"File validation failed: {error_msg}")
                return jsonify({'success': False, 'message': error_msg}), 400

            # Load and analyze data
            df = pd.read_csv(filepath)
            logger.info(f"CSV loaded successfully with shape: {df.shape}")

            # Convert data to JSON-serializable format
            df_head = df.head()
            head_records = []
            for _, row in df_head.iterrows():
                record = {}
                for col in df.columns:
                    value = row[col]
                    if pd.isna(value):
                        record[col] = None
                    elif isinstance(value, (pd.Timestamp, datetime)):
                        record[col] = str(value)
                    elif isinstance(value, (np.integer, np.floating)):
                        record[col] = float(value)
                    else:
                        record[col] = str(value)
                head_records.append(record)

            df_info = {
                'filename': filename,
                'shape': list(df.shape),
                'columns': df.columns.tolist(),
                'dtypes': {col: str(dtype) for col, dtype in df.dtypes.items()},
                'head': head_records,
                'null_counts': {col: int(count) for col, count in df.isnull().sum().items()}
            }

            # Check for date column
            has_date = 'date' in df.columns
            if has_date:
                try:
                    df['date'] = pd.to_datetime(df['date'], errors='coerce')
                    available_dates = df['date'].dropna().dt.date.unique()
                    available_dates = sorted([str(date) for date in available_dates])

                    df_info['date_range'] = {
                        'start': str(df['date'].min().date()) if not df['date'].isnull().all() else None,
                        'end': str(df['date'].max().date()) if not df['date'].isnull().all() else None,
                        'periods': len(df),
                        'available_dates': available_dates
                    }
                except Exception as date_error:
                    logger.warning(f"Date parsing failed: {date_error}")
                    has_date = False

            logger.info(f"Data analysis completed. Has date column: {has_date}")

            response_data = {
                'success': True,
                'message': 'File uploaded successfully',
                'data_info': df_info,
                'has_date_column': has_date
            }

            return jsonify(response_data)

        except Exception as processing_error:
            logger.error(f"File processing error: {processing_error}")
            if os.path.exists(filepath):
                os.remove(filepath)
            raise processing_error

    except Exception as e:
        logger.error(f"File upload error: {str(e)}")
        return jsonify({'success': False, 'message': f'Upload failed: {str(e)}'}), 500


@app.route('/api/sample_data', methods=['POST'])
def api_sample_data():
    """Generate sample time series data for testing (same as before)."""
    try:
        data = request.get_json()
        data_type = data.get('type', 'financial')
        periods = int(data.get('periods', 100))

        # Generate sample data
        dates = pd.date_range(start='2020-01-01', periods=periods, freq='D')

        if data_type == 'financial':
            np.random.seed(42)
            base_price = 100
            returns = np.random.normal(0.001, 0.02, periods)
            prices = [base_price]
            for ret in returns[1:]:
                prices.append(prices[-1] * (1 + ret))

            sample_data = pd.DataFrame({
                'date': dates,
                'price': prices,
                'volume': np.random.randint(1000, 10000, periods),
                'volatility': np.random.uniform(0.1, 0.3, periods)
            })

        elif data_type == 'sales':
            np.random.seed(42)
            trend = np.linspace(100, 150, periods)
            seasonal = 20 * np.sin(2 * np.pi * np.arange(periods) / 365.25)
            noise = np.random.normal(0, 5, periods)
            sales = trend + seasonal + noise

            sample_data = pd.DataFrame({
                'date': dates,
                'sales': sales,
                'customers': np.random.randint(50, 200, periods),
                'marketing_spend': np.random.uniform(1000, 5000, periods)
            })

        else:
            np.random.seed(42)
            trend = np.linspace(0, 100, periods)
            seasonal = 10 * np.sin(2 * np.pi * np.arange(periods) / 30)
            noise = np.random.normal(0, 2, periods)
            values = trend + seasonal + noise

            sample_data = pd.DataFrame({
                'date': dates,
                'value': values,
                'category': np.random.choice(['A', 'B', 'C'], periods),
                'score': np.random.uniform(0, 100, periods)
            })

        # Save sample data
        filename = f"sample_{data_type}_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        sample_data.to_csv(filepath, index=False)

        # Return data info
        df_info = {
            'filename': filename,
            'shape': list(sample_data.shape),
            'columns': sample_data.columns.tolist(),
            'dtypes': {col: str(dtype) for col, dtype in sample_data.dtypes.items()},
            'head': sample_data.head().to_dict('records'),
            'null_counts': {col: int(count) for col, count in sample_data.isnull().sum().items()},
            'date_range': {
                'start': str(sample_data['date'].min().date()),
                'end': str(sample_data['date'].max().date()),
                'periods': len(sample_data)
            }
        }

        return jsonify({
            'success': True,
            'message': f'Sample {data_type} data generated successfully',
            'data_info': df_info,
            'has_date_column': True
        })

    except Exception as e:
        logger.error(f"Sample data generation error: {str(e)}")
        return jsonify({'success': False, 'message': f'Sample data generation failed: {str(e)}'}), 500


@app.route('/api/forecast', methods=['POST'])
def api_forecast():
    """Perform forecasting via API."""
    try:
        data = request.get_json()
        filename = data.get('filename')
        data_definition = data.get('data_definition', {})
        use_covariates = data.get('use_covariates', False)
        use_quantiles = data.get('use_quantiles', False)
        context_len = int(data.get('context_len', 64))
        horizon_len = int(data.get('horizon_len', 24))

        if not filename:
            return jsonify({'success': False, 'message': 'No data file specified'}), 400

        # Construct local file path for API
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if not os.path.exists(filepath):
            return jsonify({'success': False, 'message': 'Data file not found'}), 400

        # Prepare parameters for API
        parameters = {
            'context_len': context_len,
            'horizon_len': horizon_len,
            'use_covariates': use_covariates,
            'use_quantiles': use_quantiles,
            'quantile_indices': data.get('quantile_indices', [1, 3, 5, 7, 9])
        }

        # Add date filtering if provided
        context_start_date = data.get('context_start_date')
        context_end_date = data.get('context_end_date')
        if context_start_date and context_end_date:
            parameters['context_start_date'] = context_start_date
            parameters['context_end_date'] = context_end_date

        logger.info(f"Sending forecast request to API for file: {filename}")

        # Just send the filename - API will resolve it using centralized path utilities
        # This fixes the path handling inconsistency from CODEREVIEW.md (lines 456-463)
        logger.info(f"Sending filename to API: {filename}")

        # Call API for inference - pass just filename, not full path
        success, result = api_client.run_inference(
            data_source=filename,  # Just filename, normalize_data_path() handles the rest
            data_definition=data_definition,
            parameters=parameters
        )

        if success:
            logger.info("Forecast completed successfully via API")

            # Extract results
            prediction = result.get('prediction', {})
            visualization_data = result.get('visualization_data', {})

            # Flatten predictions for frontend (remove batch dimension)
            if 'point_forecast' in prediction:
                pf = prediction['point_forecast']
                if isinstance(pf, list) and len(pf) > 0 and isinstance(pf[0], list):
                    prediction['point_forecast'] = pf[0]
                    logger.info(f"Flattened point_forecast: {len(pf)} -> {len(pf[0])}")

            if 'quantile_forecast' in prediction:
                qf = prediction['quantile_forecast']
                if isinstance(qf, list) and len(qf) > 0 and isinstance(qf[0], list):
                    prediction['quantile_forecast'] = qf[0]  # Remove batch dimension
                    logger.info(f"Flattened quantile_forecast: ({len(qf)}, {len(qf[0])}, ...) -> ({len(qf[0])}, ...)")

            # Determine target column for summary
            target_column = None
            for col, dtype in data_definition.items():
                if dtype == 'target':
                    target_column = col
                    break

            return jsonify({
                'success': True,
                'message': 'Forecasting completed successfully',
                'results': prediction,
                'visualization_data': visualization_data,
                'forecast_summary': {
                    'methods_used': list(prediction.keys()),
                    'context_length': context_len,
                    'horizon_length': horizon_len,
                    'target_column': target_column,
                    'covariates_used': use_covariates
                }
            })
        else:
            logger.error(f"Forecast failed: {result}")
            return jsonify({
                'success': False,
                'message': f'Forecasting failed: {result}'
            }), 500

    except Exception as e:
        logger.error(f"Forecasting error: {str(e)}")
        return jsonify({'success': False, 'message': f'Forecasting failed: {str(e)}'}), 500


@app.route('/api/visualize', methods=['POST'])
def api_visualize():
    """Generate visualization (UI handles this locally)."""
    try:
        data = request.get_json()
        viz_data = data.get('visualization_data', {})
        results = data.get('results', {})
        selected_indices = data.get('quantile_indices', [])

        # Extract data
        historical_data = viz_data.get('historical_data', [])
        dates_historical = [pd.to_datetime(d) for d in viz_data.get('dates_historical', [])]
        dates_future = [pd.to_datetime(d) for d in viz_data.get('dates_future', [])]
        actual_future = viz_data.get('actual_future', [])
        target_name = viz_data.get('target_name', 'Value')

        logger.info(f"Generating visualization for {len(historical_data)} historical points")

        # Choose forecast data
        if 'point_forecast' in results:
            forecast = results['point_forecast']

            # Flatten if necessary (handle shape (1, horizon) -> (horizon,))
            if isinstance(forecast, list) and len(forecast) > 0 and isinstance(forecast[0], list):
                forecast = forecast[0]  # Take first batch
                logger.info(f"Flattened forecast from nested list to shape: {len(forecast)}")

            if results.get('method') == 'covariates_enhanced':
                title = f"{target_name} Forecast with Covariates Enhancement"
            else:
                title = f"{target_name} Forecast (TimesFM)"
        else:
            return jsonify({'success': False, 'message': 'No forecast data available'}), 400

        # Process quantile bands
        intervals = {}
        used_quantile_intervals = False
        quantile_shape = None

        if 'quantile_forecast' in results:
            try:
                quantiles = np.array(results['quantile_forecast'])
                quantile_shape = list(quantiles.shape)
                logger.info(f"Processing quantile forecast with shape: {quantile_shape}")

                # Use centralized quantile processing
                intervals = process_quantile_bands(
                    quantile_forecast=quantiles,
                    selected_indices=selected_indices if selected_indices and len(selected_indices) > 0 else []
                )

                used_quantile_intervals = len(intervals) > 0
                logger.info(f"Processed {len(intervals)//3} quantile bands")

            except Exception as e:
                logger.warning(f"Quantile band processing failed: {e}")
                intervals = {}

        # Generate plot using local visualizer
        try:
            fig = current_visualizer.plot_forecast_with_intervals(
                historical_data=historical_data,
                forecast=forecast,
                intervals=intervals if intervals else None,
                actual_future=actual_future if actual_future else None,
                dates_historical=dates_historical,
                dates_future=dates_future,
                title=title,
                target_name=target_name,
                show_figure=False
            )
            logger.info("Visualization generated successfully")
        except Exception as plot_error:
            logger.error(f"Plot generation failed: {str(plot_error)}")
            raise plot_error

        figure_payload = json.loads(fig.to_json())
        plot_config = {
            'responsive': True,
            'displaylogo': False,
            'modeBarButtonsToRemove': ['lasso2d', 'select2d']
        }

        return jsonify({
            'success': True,
            'message': 'Visualization generated successfully',
            'figure': figure_payload,
            'config': plot_config,
            'used_quantile_intervals': used_quantile_intervals,
            'quantile_shape': quantile_shape
        })

    except Exception as e:
        logger.error(f"Visualization error: {str(e)}")
        return jsonify({'success': False, 'message': f'Visualization failed: {str(e)}'}), 500


@app.route('/health')
def health_check():
    """Health check endpoint."""
    # Check API connectivity
    api_success, api_health = api_client.health_check()

    return jsonify({
        'status': 'healthy' if api_success else 'degraded',
        'timestamp': datetime.now().isoformat(),
        'ui': 'running',
        'api_connected': api_success,
        'api_health': api_health if api_success else 'unavailable'
    })


@app.errorhandler(413)
def too_large(e):
    """Handle file too large error."""
    return jsonify({'success': False, 'message': 'File too large. Maximum size is 16MB.'}), 413


@app.errorhandler(500)
def internal_error(e):
    """Handle internal server error."""
    return jsonify({'success': False, 'message': 'Internal server error.'}), 500


if __name__ == '__main__':
    # Configuration for different environments
    port = int(os.environ.get('UI_PORT', 8080))
    debug = os.environ.get('FLASK_ENV') == 'development'

    logger.info("=" * 80)
    logger.info("Sapheneia UI starting...")
    logger.info(f"UI Port: {port}")
    logger.info(f"API Base URL: {api_client.base_url}")
    logger.info(f"Debug Mode: {debug}")
    logger.info("=" * 80)

    # Run the app
    app.run(host='0.0.0.0', port=port, debug=debug)
