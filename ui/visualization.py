"""
Interactive Visualization Module for TimesFM Forecasting using Plotly

This module provides comprehensive interactive visualization capabilities for TimesFM forecasting,
including professional-grade plots with prediction intervals, covariates displays,
and publication-ready styling using Plotly for enhanced interactivity.

Key Features:
- Interactive forecast visualizations with seamless connections
- Prediction intervals with customizable confidence levels
- Covariates subplots integration
- Sapheneia-style professional formatting
- Interactive zoom, pan, and hover capabilities
- Export capabilities for presentations and publications
- Responsive design for web applications
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from plotly.offline import plot
from datetime import datetime
from typing import List, Dict, Optional, Union
import logging
import json

logger = logging.getLogger(__name__)


class InteractiveVisualizer:
    """
    Interactive visualization class for TimesFM forecasting results using Plotly.
    
    This class provides methods to create interactive, publication-quality visualizations
    of forecasting results, including prediction intervals, covariates analysis,
    and comprehensive time series plots with enhanced user interaction.
    
    Example:
        >>> viz = InteractiveVisualizer()
        >>> fig = viz.plot_forecast_with_intervals(
        ...     historical_data=historical,
        ...     forecast=point_forecast,
        ...     intervals=prediction_intervals,
        ...     title="Bitcoin Price Forecast"
        ... )
        >>> fig.show()
    """
    
    def __init__(self, style: str = "professional", theme: str = "plotly_white"):
        """
        Initialize the InteractiveVisualizer with specified styling.
        
        Args:
            style: Visualization style ("professional", "minimal", "presentation")
            theme: Plotly theme ("plotly", "plotly_white", "plotly_dark", "ggplot2", "seaborn", "simple_white")
        """
        self.style = style
        self.theme = theme
        self._setup_style()
        logger.info(f"InteractiveVisualizer initialized with '{style}' style and '{theme}' theme")
    
    def _setup_style(self) -> None:
        """Set up the visualization style and parameters."""
        if self.style == "professional":
            # Sapheneia professional style
            self.colors = {
                'historical': '#1f77b4',
                'forecast': '#d62728', 
                'actual': '#2ca02c',
                'interval_80': 'rgba(255, 179, 102, 0.3)',
                'interval_50': 'rgba(255, 127, 14, 0.5)',
                'grid': '#e0e0e0',
                'background': '#fafafa',
                'text': '#2c3e50',
                'axis': '#34495e'
            }
            self.layout_config = {
                'width': 1200,
                'height': 800,
                'margin': {'l': 60, 'r': 60, 't': 80, 'b': 60}
            }
            
        elif self.style == "minimal":
            # Clean minimal style
            self.colors = {
                'historical': '#2E86AB',
                'forecast': '#A23B72',
                'actual': '#F18F01',
                'interval_80': 'rgba(199, 62, 29, 0.3)',
                'interval_50': 'rgba(241, 143, 1, 0.5)',
                'grid': '#f0f0f0',
                'background': 'white',
                'text': '#2c3e50',
                'axis': '#34495e'
            }
            self.layout_config = {
                'width': 1000,
                'height': 700,
                'margin': {'l': 50, 'r': 50, 't': 60, 'b': 50}
            }
            
        else:  # presentation
            # High contrast for presentations
            self.colors = {
                'historical': '#003f5c',
                'forecast': '#ff6361',
                'actual': '#58508d',
                'interval_80': 'rgba(255, 166, 0, 0.3)',
                'interval_50': 'rgba(255, 99, 97, 0.5)',
                'grid': '#e8e8e8',
                'background': 'white',
                'text': '#2c3e50',
                'axis': '#34495e'
            }
            self.layout_config = {
                'width': 1400,
                'height': 900,
                'margin': {'l': 70, 'r': 70, 't': 100, 'b': 70}
            }
    
    def _create_base_layout(self, title: str, x_title: str = "Time", y_title: str = "Value") -> Dict:
        """Create base layout configuration for plots."""
        return {
            'title': {
                'text': title,
                'x': 0.5,
                'xanchor': 'center',
                'font': {'size': 18, 'color': self.colors['text']}
            },
            'xaxis': {
                'title': {'text': x_title, 'font': {'size': 14, 'color': self.colors['axis']}},
                'tickfont': {'size': 12, 'color': self.colors['axis']},
                'gridcolor': self.colors['grid'],
                'showgrid': True,
                'zeroline': False
            },
            'yaxis': {
                'title': {'text': y_title, 'font': {'size': 14, 'color': self.colors['axis']}},
                'tickfont': {'size': 12, 'color': self.colors['axis']},
                'gridcolor': self.colors['grid'],
                'showgrid': True,
                'zeroline': False
            },
            'plot_bgcolor': self.colors['background'],
            'paper_bgcolor': 'white',
            'font': {'family': 'Arial, sans-serif', 'color': self.colors['text']},
            'showlegend': True,
            'legend': {
                'x': 0.02,
                'y': 0.98,
                'yanchor': 'top',
                'bgcolor': 'rgba(255, 255, 255, 0.8)',
                'bordercolor': 'rgba(0, 0, 0, 0.2)',
                'borderwidth': 1
            },
            'hovermode': 'x unified',
            **self.layout_config
        }
    
    def plot_forecast_with_intervals(
        self,
        historical_data: Union[List[float], np.ndarray],
        forecast: Union[List[float], np.ndarray], 
        intervals: Optional[Dict[str, np.ndarray]] = None,
        actual_future: Optional[Union[List[float], np.ndarray]] = None,
        dates_historical: Optional[List[Union[str, datetime]]] = None,
        dates_future: Optional[List[Union[str, datetime]]] = None,
        title: str = "TimesFM Forecast with Prediction Intervals",
        target_name: str = "Value",
        save_path: Optional[str] = None,
        show_figure: bool = True,
        context_len: Optional[int] = None,
        horizon_len: Optional[int] = None,
        y_axis_padding: float = 0.1
    ) -> go.Figure:
        """
        Create an interactive forecast visualization with prediction intervals.
        
        Args:
            historical_data: Historical time series data
            forecast: Point forecast values
            intervals: Dictionary containing prediction intervals
            actual_future: Optional actual future values for comparison
            dates_historical: Optional dates for historical data
            dates_future: Optional dates for forecast period
            title: Plot title
            target_name: Name of the target variable
            save_path: Optional path to save the plot (HTML format)
            show_figure: Whether to display the figure
            context_len: Length of context window for default view focus
            horizon_len: Length of horizon for default view focus
            y_axis_padding: Padding factor for focused y-axis range (0.1 = 10% padding)
            
        Returns:
            Plotly Figure object
        """
        logger.info(f"Creating interactive forecast visualization: {title}")
        
        # Convert to numpy arrays
        if actual_future is not None:
            actual_future = np.array(actual_future)
        
        # Setup time axis
        if dates_historical is None:
            historical_x = np.arange(len(historical_data))
        else:
            historical_x = pd.to_datetime(dates_historical)
        
        future_x = np.arange(
            len(historical_data), len(historical_data) + len(forecast)
            ) if dates_future is None else pd.to_datetime(dates_future)
                
        # Calculate default view range (context + horizon)
        if context_len is not None and horizon_len is not None:
            if dates_historical is not None:
                start_date = historical_x[0]
                end_date = future_x[min(horizon_len - 1, len(future_x) - 1)] if len(future_x) > 0 else historical_x[-1]
                default_x_range = [start_date, end_date]
            else:
                start_idx = 0
                end_idx = len(historical_x) + len(forecast)
                default_x_range = [start_idx, end_idx]
        else:
            # No specific focus, show all data
            if dates_historical is not None:
                start_date = historical_x[0]
                end_date = future_x[-1] if len(future_x) > 0 else historical_x[-1]
                default_x_range = [start_date, end_date]
            else:
                start_idx = 0
                end_idx = len(historical_x) + len(forecast)
                default_x_range = [start_idx, end_idx]
        
        # Calculate focused y-axis range for better visibility
        if context_len is not None and horizon_len is not None:
            # Focus y-axis on the context + horizon period data
            if context_len < len(historical_data):
                # Get the data range for context + horizon
                context_data = historical_data[-context_len:]
                focused_data = np.concatenate([context_data, forecast])
                
                # Include prediction intervals in y-axis calculation
                if intervals:
                    # Collect all interval data for y-axis range calculation
                    interval_data = []
                    
                    # Add 50th percentile if available
                    if 'lower_50' in intervals and 'upper_50' in intervals:
                        interval_data.extend(intervals['lower_50'])
                        interval_data.extend(intervals['upper_50'])
                    
                    # Add 80th percentile if available
                    if 'lower_80' in intervals and 'upper_80' in intervals:
                        interval_data.extend(intervals['lower_80'])
                        interval_data.extend(intervals['upper_80'])
                    
                    # Add other confidence levels
                    for key in intervals.keys():
                        if key.startswith('lower_') and key not in ['lower_50', 'lower_80']:
                            interval_data.extend(intervals[key])
                        elif key.startswith('upper_') and key not in ['upper_50', 'upper_80']:
                            interval_data.extend(intervals[key])
                    
                    # Add quantile bands
                    for key in intervals.keys():
                        if key.startswith('quantile_band_') and key.endswith('_lower'):
                            interval_data.extend(intervals[key])
                        elif key.startswith('quantile_band_') and key.endswith('_upper'):
                            interval_data.extend(intervals[key])
                    
                    # Include interval data in range calculation
                    if interval_data:
                        interval_data = np.array(interval_data)
                        all_focused_data = np.concatenate([focused_data, interval_data])
                    else:
                        all_focused_data = focused_data
                else:
                    all_focused_data = focused_data
                
                # Calculate y-axis range including intervals
                data_min = np.min(all_focused_data)
                data_max = np.max(all_focused_data)
                data_range = data_max - data_min
                padding = data_range * y_axis_padding
                
                default_y_range = [data_min - padding, data_max + padding]
            else:
                # If context_len >= historical_data length, use all data
                all_data = np.concatenate([historical_x, forecast])
                
                # Include prediction intervals in y-axis calculation
                if intervals:
                    interval_data = []
                    
                    # Add 50th percentile if available
                    if 'lower_50' in intervals and 'upper_50' in intervals:
                        interval_data.extend(intervals['lower_50'])
                        interval_data.extend(intervals['upper_50'])
                    
                    # Add 80th percentile if available
                    if 'lower_80' in intervals and 'upper_80' in intervals:
                        interval_data.extend(intervals['lower_80'])
                        interval_data.extend(intervals['upper_80'])
                    
                    # Add other confidence levels
                    for key in intervals.keys():
                        if key.startswith('lower_') and key not in ['lower_50', 'lower_80']:
                            interval_data.extend(intervals[key])
                        elif key.startswith('upper_') and key not in ['upper_50', 'upper_80']:
                            interval_data.extend(intervals[key])
                    
                    # Add quantile bands
                    for key in intervals.keys():
                        if key.startswith('quantile_band_') and key.endswith('_lower'):
                            interval_data.extend(intervals[key])
                        elif key.startswith('quantile_band_') and key.endswith('_upper'):
                            interval_data.extend(intervals[key])
                    
                    # Include interval data in range calculation
                    if interval_data:
                        interval_data = np.array(interval_data)
                        all_data = np.concatenate([all_data, interval_data])
                
                data_min = np.min(all_data)
                data_max = np.max(all_data)
                data_range = data_max - data_min
                padding = data_range * y_axis_padding
                
                default_y_range = [data_min - padding, data_max + padding]
        else:
            # No focused y-axis, let Plotly auto-scale
            default_y_range = None
        
        # Create figure
        fig = go.Figure()
        
        # Debug logging for historical data
        print(f"DEBUG: Historical data length: {len(historical_data)}")
        print(f"DEBUG: Historical data type: {type(historical_data)}")
        print(f"DEBUG: Historical data first 5: {historical_data[:5] if len(historical_data) > 0 else 'Empty'}")
        print(f"DEBUG: Historical data last 5: {historical_data[-5:] if len(historical_data) > 0 else 'Empty'}")
        print(f"DEBUG: Historical x length: {len(historical_x)}")
        print(f"DEBUG: Historical x first 5: {historical_x[:5] if len(historical_x) > 0 else 'Empty'}")
        
        # Validate data before plotting
        if len(historical_data) == 0:
            print("ERROR: Historical data is empty!")
            return None
        
        if len(historical_x) == 0:
            print("ERROR: Historical x-axis data is empty!")
            return None
        
        if len(historical_data) != len(historical_x):
            print(f"ERROR: Mismatch between historical data ({len(historical_data)}) and x-axis ({len(historical_x)}) lengths!")
            return None
        
        # Plot historical data
        print(f"DEBUG: About to plot historical data with {len(historical_data)} points")
        print(f"DEBUG: Historical data sample: {historical_data[:3]}...{historical_data[-3:]}")
        print(f"DEBUG: Historical x sample: {historical_x[:3]}...{historical_x[-3:]}")
        
        historical_trace = go.Scatter(
            x=historical_x,
            y=historical_data,
            mode='lines',
            name='Historical Data',
            line=dict(color=self.colors['historical'], width=3),
            hovertemplate='<b>Historical</b><br>Time: %{x}<br>Value: %{y:.2f}<extra></extra>'
        )
        
        print(f"DEBUG: Historical trace created: {historical_trace}")
        fig.add_trace(historical_trace)
        print(f"DEBUG: Historical trace added to figure. Figure has {len(fig.data)} traces")

        # Create seamless connection for forecast
        if dates_historical is None:
            connection_x = [len(historical_x) - 1] + list(future_x)
        else:
            connection_x = [historical_x[-1]] + list(future_x)
        
        # Plot quantile intervals if available
        if intervals:
            # Handle different types of intervals
            if 'lower_80' in intervals and 'upper_80' in intervals:
                # Traditional confidence intervals
                interval_lower = [historical_data[-1]] + list(intervals['lower_80'])
                interval_upper = [historical_data[-1]] + list(intervals['upper_80'])
                
                fig.add_trace(go.Scatter(
                    x=connection_x,
                    y=interval_upper,
                    mode='lines',
                    line=dict(width=0),
                    showlegend=False,
                    hoverinfo='skip'
                ))
                
                fig.add_trace(go.Scatter(
                    x=connection_x,
                    y=interval_lower,
                    mode='lines',
                    line=dict(width=0),
                    fill='tonexty',
                    fillcolor=self.colors['interval_80'],
                    name='80% Prediction Interval',
                    hovertemplate='<b>80% Interval</b><br>Time: %{x}<br>Upper: %{y:.2f}<extra></extra>'
                ))
                               
                # Add 50% interval if available
                if 'lower_50' in intervals and 'upper_50' in intervals:
                    interval_lower_50 = [historical_data[-1]] + list(intervals['lower_50'])
                    interval_upper_50 = [historical_data[-1]] + list(intervals['upper_50'])
                    
                    fig.add_trace(go.Scatter(
                        x=connection_x,
                        y=interval_upper_50,
                        mode='lines',
                        line=dict(width=0),
                        showlegend=False,
                        hoverinfo='skip'
                    ))
                    
                    fig.add_trace(go.Scatter(
                        x=connection_x,
                        y=interval_lower_50,
                        mode='lines',
                        line=dict(width=0),
                        fill='tonexty',
                        fillcolor=self.colors['interval_50'],
                        name='50% Prediction Interval',
                        hovertemplate='<b>50% Interval</b><br>Time: %{x}<br>Upper: %{y:.2f}<extra></extra>'
                    ))
            
            else:
                # Check for generic confidence levels
                conf_levels = []
                for key in intervals.keys():
                    if key.startswith('lower_'):
                        conf_level = key.split('_')[1]
                        if f'upper_{conf_level}' in intervals:
                            conf_levels.append(int(conf_level))
                
                conf_levels.sort(reverse=True)  # Largest first for layering
                
                for conf_level in conf_levels:
                    lower_key = f'lower_{conf_level}'
                    upper_key = f'upper_{conf_level}'
                    
                    if lower_key in intervals and upper_key in intervals:
                        # Create seamless intervals
                        interval_lower = [historical_data[-1]] + list(intervals[lower_key])
                        interval_upper = [historical_data[-1]] + list(intervals[upper_key])
                        
                        alpha = 0.3 if conf_level == max(conf_levels) else 0.5
                        color = self.colors['interval_80'] if conf_level >= 80 else self.colors['interval_50']
                        
                        fig.add_trace(go.Scatter(
                            x=connection_x,
                            y=interval_upper,
                            mode='lines',
                            line=dict(width=0),
                            showlegend=False,
                            hoverinfo='skip'
                        ))
                        
                        fig.add_trace(go.Scatter(
                            x=connection_x,
                            y=interval_lower,
                            mode='lines',
                            line=dict(width=0),
                            fill='tonexty',
                            fillcolor=color,
                            name=f'{conf_level}% Prediction Interval',
                            hovertemplate=f'<b>{conf_level}% Interval</b><br>Time: %{{x}}<br>Upper: %{{y:.2f}}<extra></extra>'
                        ))
            
            # Handle quantile bands (new format)
            quantile_bands = {}
            for key in intervals.keys():
                if key.startswith('quantile_band_') and key.endswith('_lower'):
                    band_name = key.replace('quantile_band_', '').replace('_lower', '')
                    upper_key = f'quantile_band_{band_name}_upper'
                    if upper_key in intervals:
                        quantile_bands[band_name] = {
                            'lower': intervals[key],
                            'upper': intervals[upper_key]
                        }
            
            if quantile_bands:
                # Define colors for different bands
                band_colors = ['rgba(255, 153, 153, 0.3)', 'rgba(153, 204, 255, 0.3)', 
                               'rgba(153, 255, 153, 0.3)', 'rgba(255, 204, 153, 0.3)', 
                               'rgba(204, 153, 255, 0.3)', 'rgba(255, 255, 153, 0.3)']
                
                for i, (band_name, band_data) in enumerate(sorted(quantile_bands.items())):
                    color = band_colors[i % len(band_colors)]
                    
                    interval_lower = [historical_data[-1]] + list(band_data['lower'])
                    interval_upper = [historical_data[-1]] + list(band_data['upper'])
                    
                    label_key = f'quantile_band_{band_name}_label'
                    label_text = intervals.get(label_key, f'Quantile Band {int(band_name)+1}')
                    
                    fig.add_trace(go.Scatter(
                        x=connection_x,
                        y=interval_upper,
                        mode='lines',
                        line=dict(width=0),
                        showlegend=False,
                        hoverinfo='skip'
                    ))
                    
                    fig.add_trace(go.Scatter(
                        x=connection_x,
                        y=interval_lower,
                        mode='lines',
                        line=dict(width=0),
                        fill='tonexty',
                        fillcolor=color,
                        name=label_text,
                        hovertemplate=f'<b>{label_text}</b><br>Upper: %{{y:.2f}}<extra></extra>'
                    ))
        
        fig.add_trace(go.Scatter(
            x=future_x,
            y=forecast,
            mode='lines',
            name='Point Forecast',
            line=dict(color=self.colors['forecast'], width=3, dash='dash'),
            hovertemplate='<b>Forecast</b><br>Time: %{x}<br>Value: %{y:.2f}<extra></extra>',
            legendgroup='forecast'
        ))

        # 2) a 2-point seamless bridge with no hover/legend
        fig.add_trace(go.Scatter(
            x=[historical_x[-1], future_x[0]],
            y=[historical_data[-1], forecast[0]],
            mode='lines',
            line=dict(color=self.colors['forecast'], width=3, dash='dash'),
            hoverinfo='skip',
            showlegend=False,
            legendgroup='forecast'
        ))
        
        # Plot actual future data if available
        if actual_future is not None:
            print(f"DEBUG: Plotting actual future values")
            print(f"DEBUG: actual_future length: {len(actual_future)}")
            print(f"DEBUG: actual_future sample: {actual_future[:3] if len(actual_future) > 0 else 'Empty'}")
            print(f"DEBUG: dates_future length: {len(dates_future) if dates_future else 'None'}")
            print(f"DEBUG: dates_future sample: {dates_future[:3] if dates_future and len(dates_future) > 0 else 'Empty'}")
            print(f"DEBUG: historical_x last value: {historical_x[-1]}")
            print(f"DEBUG: future_x first value: {future_x[0] if len(future_x) > 0 else 'Empty'}")
            
            actual_connection = [historical_x[-1]] + list(actual_future)
            fig.add_trace(go.Scatter(
                x=connection_x,
                y=actual_connection,
                mode='lines+markers',
                name='Actual Future',
                line=dict(color=self.colors['actual'], width=3),
                marker=dict(size=8, color=self.colors['actual'], 
                           line=dict(width=2, color='white')),
                hovertemplate='<b>Actual Future</b><br>Time: %{x}<br>Value: %{y:.2f}<extra></extra>',
                legendgroup='actual'
            ))
            print([historical_x[-1], connection_x[0]])
            print([historical_data[-1], actual_connection[0]])

            # 2) a 2-point seamless bridge with no hover/legend
            fig.add_trace(go.Scatter(
                x=[historical_x[-1], connection_x[1]],
                y=[historical_data[-1], actual_connection[1]],
                mode='lines',
                line=dict(color=self.colors['actual'], width=3),
                marker=dict(size=8, color=self.colors['actual'], 
                           line=dict(width=2, color='white')),
                hoverinfo='skip',
                showlegend=False,
                legendgroup='actual'
            ))
        
        # Add forecast start line
        fig.add_vline(
            x=pd.to_datetime(historical_x[-1]).to_pydatetime(),  # or .isoformat()
            line_dash="dot", line_color="gray", line_width=1
        )
        fig.add_annotation(
            x=pd.to_datetime(historical_x[-1]).to_pydatetime(),
            y=1,                 # top of plotting area
            xref="x",
            yref="paper",
            text="Forecast Start",
            showarrow=False,
            yanchor="bottom"
        )
        
        # Apply layout
        layout = self._create_base_layout(title, "Time", target_name)
        
        # Add default view range if specified
        if context_len is not None and horizon_len is not None:
            layout['xaxis']['range'] = default_x_range
            
        # Add focused y-axis range if specified
        if default_y_range is not None:
            layout['yaxis']['range'] = default_y_range
        
        # Add timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        layout['annotations'] = [{
            'x': 1,
            'y': -0.1,
            'xref': 'paper',
            'yref': 'paper',
            'text': f'Generated: {timestamp}',
            'showarrow': False,
            'font': {'size': 10, 'color': 'gray'}
        }]
        
        fig.update_layout(**layout)
        
        # Save if requested
        if save_path:
            if save_path.endswith('.html'):
                fig.write_html(save_path)
            else:
                fig.write_image(save_path)
            logger.info(f"Interactive plot saved to: {save_path}")
        
        # Debug final figure
        print(f"DEBUG: Final figure has {len(fig.data)} traces")
        for i, trace in enumerate(fig.data):
            print(f"DEBUG: Trace {i}: name='{trace.name}', type='{trace.type}', visible={trace.visible}")
            if hasattr(trace, 'y') and trace.y is not None:
                print(f"DEBUG: Trace {i} y-data length: {len(trace.y) if hasattr(trace.y, '__len__') else 'scalar'}")
        
        # Show figure if requested
        if show_figure:
            fig.show()
        
        logger.info("✅ Interactive forecast visualization completed")
        return fig
    
    def plot_forecast_with_covariates(
        self,
        historical_data: Union[List[float], np.ndarray],
        forecast: Union[List[float], np.ndarray],
        covariates_data: Dict[str, Dict[str, Union[List[float], float, str]]],
        intervals: Optional[Dict[str, np.ndarray]] = None,
        actual_future: Optional[Union[List[float], np.ndarray]] = None,
        dates_historical: Optional[List[Union[str, datetime]]] = None,
        dates_future: Optional[List[Union[str, datetime]]] = None,
        title: str = "TimesFM Forecast with Covariates Analysis",
        target_name: str = "Target Value",
        save_path: Optional[str] = None,
        show_figure: bool = True,
        context_len: Optional[int] = None,
        horizon_len: Optional[int] = None,
        show_full_history: bool = True,
        y_axis_padding: float = 0.1
    ) -> go.Figure:
        """
        Create a comprehensive interactive visualization with main forecast and covariates subplots.
        
        Args:
            historical_data: Historical time series data
            forecast: Point forecast values
            covariates_data: Dictionary containing covariates information
            intervals: Optional prediction intervals
            actual_future: Optional actual future values
            dates_historical: Optional historical dates
            dates_future: Optional future dates
            title: Main plot title
            target_name: Name of target variable
            save_path: Optional save path
            show_figure: Whether to display the figure
            context_len: Length of context window for default view focus
            horizon_len: Length of horizon for default view focus
            show_full_history: Whether to show full historical data (True) or just context (False)
            
        Returns:
            Plotly Figure object
        """
        logger.info(f"Creating comprehensive interactive forecast with covariates: {title}")
        
        # Count covariates for subplot layout
        num_covariates = len([k for k, v in covariates_data.items() 
                             if isinstance(v, dict) and 'historical' in v])
        
        # Create subplot layout
        if num_covariates == 0:
            return self.plot_forecast_with_intervals(
                historical_data, forecast, intervals, actual_future,
                dates_historical, dates_future, title, target_name, save_path, show_figure,
                context_len, horizon_len, show_full_history, y_axis_padding
            )
        
        # Determine grid layout
        if num_covariates <= 2:
            rows, cols = 2, 2
            subplot_titles = [title] + [f'{name.replace("_", " ").title()}' 
                                      for name in list(covariates_data.keys())[:3]]
        elif num_covariates <= 4:
            rows, cols = 3, 2  
            subplot_titles = [title] + [f'{name.replace("_", " ").title()}' 
                                      for name in list(covariates_data.keys())[:5]]
        else:
            rows, cols = 4, 2
            subplot_titles = [title] + [f'{name.replace("_", " ").title()}' 
                                      for name in list(covariates_data.keys())[:7]]
        
        # Create subplots
        fig = make_subplots(
            rows=rows, cols=cols,
            subplot_titles=subplot_titles,
            vertical_spacing=0.08,
            horizontal_spacing=0.1
        )
        
        # Convert data
        historical_data = np.array(historical_data)
        forecast = np.array(forecast)
        
        # Setup time axes
        if dates_historical is None:
            historical_x = np.arange(len(historical_data))
            future_x = np.arange(len(historical_data), len(historical_data) + len(forecast))
        else:
            historical_x = pd.to_datetime(dates_historical)
            future_x = pd.to_datetime(dates_future) if dates_future is not None else None
        
        # Plot main forecast (similar to single plot method)
        # Historical data
        fig.add_trace(go.Scatter(
            x=historical_x,
            y=historical_data,
            mode='lines',
            name='Historical Data',
            line=dict(color=self.colors['historical'], width=3),
            hovertemplate='<b>Historical</b><br>Time: %{x}<br>Value: %{y:.2f}<extra></extra>'
        ), row=1, col=1)
        
        # Forecast with seamless connection
        if dates_historical is None:
            connection_x = [len(historical_data) - 1] + list(future_x)
        else:
            connection_x = [historical_x[-1]] + list(future_x)
        connection_forecast = [historical_data[-1]] + list(forecast)
        
        # Plot intervals if available
        if intervals:
            for key in intervals.keys():
                if key.startswith('lower_'):
                    conf_level = key.split('_')[1]
                    upper_key = f'upper_{conf_level}'
                    if upper_key in intervals:
                        interval_lower = [historical_data[-1]] + list(intervals[key])
                        interval_upper = [historical_data[-1]] + list(intervals[upper_key])
                        
                        alpha = 0.3 if int(conf_level) >= 80 else 0.5
                        color = self.colors['interval_80'] if int(conf_level) >= 80 else self.colors['interval_50']
                        
                        fig.add_trace(go.Scatter(
                            x=connection_x,
                            y=interval_upper,
                            mode='lines',
                            line=dict(width=0),
                            showlegend=False,
                            hoverinfo='skip'
                        ), row=1, col=1)
                        
                        fig.add_trace(go.Scatter(
                            x=connection_x,
                            y=interval_lower,
                            mode='lines',
                            line=dict(width=0),
                            fill='tonexty',
                            fillcolor=color,
                            name=f'{conf_level}% Prediction Interval',
                            hovertemplate=f'<b>{conf_level}% Interval</b><br>Time: %{{x}}<br>Upper: %{{y:.2f}}<extra></extra>'
                        ), row=1, col=1)
        
        # Forecast line
        fig.add_trace(go.Scatter(
            x=connection_x,
            y=connection_forecast,
            mode='lines',
            name='Point Forecast',
            line=dict(color=self.colors['forecast'], width=3, dash='dash'),
            hovertemplate='<b>Forecast</b><br>Time: %{x}<br>Value: %{y:.2f}<extra></extra>'
        ), row=1, col=1)
        
        # Plot actual future if available
        if actual_future is not None:
            actual_future = np.array(actual_future)
            actual_connection = [historical_data[-1]] + list(actual_future)
            fig.add_trace(go.Scatter(
                x=connection_x,
                y=actual_connection,
                mode='lines+markers',
                name='Actual Future',
                line=dict(color=self.colors['actual'], width=3),
                marker=dict(size=8, color=self.colors['actual'], 
                           line=dict(width=2, color='white')),
                hovertemplate='<b>Actual Future</b><br>Time: %{x}<br>Value: %{y:.2f}<extra></extra>'
            ), row=1, col=1)
        
        # Forecast start line (commented out due to datetime compatibility issues)
        # forecast_start = historical_x[-1] if dates_historical is not None else len(historical_data) - 1
        # fig.add_vline(
        #     x=forecast_start,
        #     line_dash="dot",
        #     line_color="gray",
        #     line_width=2,
        #     annotation_text="Forecast Start",
        #     annotation_position="top"
        # )
        
        # Create covariate subplots
        covariate_colors = ['#9467bd', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf', '#d62728']
        
        plot_idx = 0
        for cov_name, cov_data in covariates_data.items():
            if not isinstance(cov_data, dict) or 'historical' not in cov_data:
                continue
                
            if plot_idx >= (rows - 1) * cols:  # Don't exceed subplot capacity
                break
                
            # Calculate subplot position
            row = 2 + plot_idx // cols
            col = 1 + plot_idx % cols
            color = covariate_colors[plot_idx % len(covariate_colors)]
            
            # Plot historical covariate data
            fig.add_trace(go.Scatter(
                x=historical_x,
                y=cov_data['historical'],
                mode='lines',
                name=f'{cov_name.replace("_", " ").title()} Historical',
                line=dict(color=color, width=2.5),
                hovertemplate=f'<b>{cov_name.replace("_", " ").title()}</b><br>Time: %{{x}}<br>Value: %{{y:.2f}}<extra></extra>',
                showlegend=False
            ), row=row, col=col)
            
            # Plot future covariate data if available
            if 'future' in cov_data and future_x is not None:
                combined_data = list(cov_data['historical']) + list(cov_data['future'])
                if dates_historical is None:
                    combined_x = np.arange(len(combined_data))
                else:
                    combined_x = list(historical_x) + list(future_x)
                
                future_start_idx = len(cov_data['historical']) - 1
                fig.add_trace(go.Scatter(
                    x=combined_x[future_start_idx:],
                    y=combined_data[future_start_idx:],
                    mode='lines+markers',
                    name=f'{cov_name.replace("_", " ").title()} Future',
                    line=dict(color=color, width=2.5, dash='dash'),
                    marker=dict(size=6, color=color),
                    hovertemplate=f'<b>{cov_name.replace("_", " ").title()} Future</b><br>Time: %{{x}}<br>Value: %{{y:.2f}}<extra></extra>',
                    showlegend=False
                ), row=row, col=col)
            
            # Forecast start line for covariate (commented out due to datetime compatibility issues)
            # fig.add_vline(
            #     x=forecast_start,
            #     line_dash="dot",
            #     line_color="gray",
            #     line_width=1,
            #     row=row, col=col
            # )
            
            plot_idx += 1
        
        # Update layout
        fig.update_layout(
            title=f'TimesFM Comprehensive Forecasting Analysis',
            title_x=0.5,
            title_font_size=20,
            height=800,
            showlegend=True,
            hovermode='x unified'
        )
        
        # Update axes
        for i in range(1, rows + 1):
            for j in range(1, cols + 1):
                fig.update_xaxes(
                    title_text="Time" if i == 1 else "",
                    gridcolor=self.colors['grid'],
                    showgrid=True,
                    row=i, col=j
                )
                fig.update_yaxes(
                    title_text=target_name if i == 1 else "Value",
                    gridcolor=self.colors['grid'],
                    showgrid=True,
                    row=i, col=j
                )
        
        # Add timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        fig.add_annotation(
            x=1, y=-0.1,
            xref='paper', yref='paper',
            text=f'Generated: {timestamp}',
            showarrow=False,
            font=dict(size=10, color='gray')
        )
        
        # Save if requested
        if save_path:
            if save_path.endswith('.html'):
                fig.write_html(save_path)
            else:
                fig.write_image(save_path)
            logger.info(f"Comprehensive interactive plot saved to: {save_path}")
        
        # Show figure if requested
        if show_figure:
            fig.show()
        
        logger.info("✅ Comprehensive interactive forecast visualization completed")
        return fig
    
    def plot_forecast_comparison(
        self,
        forecasts_dict: Dict[str, np.ndarray],
        historical_data: Union[List[float], np.ndarray],
        actual_future: Optional[Union[List[float], np.ndarray]] = None,
        title: str = "Forecast Methods Comparison",
        save_path: Optional[str] = None,
        show_figure: bool = True
    ) -> go.Figure:
        """
        Compare multiple forecasting methods in an interactive plot.
        
        Args:
            forecasts_dict: Dictionary of {method_name: forecast_array}
            historical_data: Historical data for context
            actual_future: Optional actual future values
            title: Plot title
            save_path: Optional save path
            show_figure: Whether to display the figure
            
        Returns:
            Plotly Figure object
        """
        logger.info(f"Creating interactive forecast comparison plot: {title}")
        
        fig = go.Figure()
        
        historical_data = np.array(historical_data)
        historical_x = np.arange(len(historical_data))
        
        # Plot historical data
        fig.add_trace(go.Scatter(
            x=historical_x,
            y=historical_data,
            mode='lines',
            name='Historical Data',
            line=dict(color=self.colors['historical'], width=3),
            hovertemplate='<b>Historical</b><br>Time: %{x}<br>Value: %{y:.2f}<extra></extra>'
        ))
        
        # Plot different forecasts
        forecast_colors = ['#d62728', '#ff7f0e', '#2ca02c', '#9467bd', '#8c564b']
        
        for i, (method, forecast) in enumerate(forecasts_dict.items()):
            forecast = np.array(forecast)
            future_x = np.arange(len(historical_data), len(historical_data) + len(forecast))
            
            # Seamless connection
            connection_x = [len(historical_data) - 1] + list(future_x)
            connection_forecast = [historical_data[-1]] + list(forecast)
            
            color = forecast_colors[i % len(forecast_colors)]
            linestyle = 'dash' if i == 0 else 'dot'
            
            fig.add_trace(go.Scatter(
                x=connection_x,
                y=connection_forecast,
                mode='lines',
                name=f'{method} Forecast',
                line=dict(color=color, width=3, dash=linestyle),
                hovertemplate=f'<b>{method} Forecast</b><br>Time: %{{x}}<br>Value: %{{y:.2f}}<extra></extra>'
            ))
        
        # Plot actual future if available
        if actual_future is not None:
            actual_future = np.array(actual_future)
            future_x = np.arange(len(historical_data), len(historical_data) + len(actual_future))
            connection_x = [len(historical_data) - 1] + list(future_x)
            actual_connection = [historical_data[-1]] + list(actual_future)
            
            fig.add_trace(go.Scatter(
                x=connection_x,
                y=actual_connection,
                mode='lines+markers',
                name='Actual Future',
                line=dict(color=self.colors['actual'], width=3),
                marker=dict(size=8, color=self.colors['actual'], 
                           line=dict(width=2, color='white')),
                hovertemplate='<b>Actual Future</b><br>Time: %{x}<br>Value: %{y:.2f}<extra></extra>'
            ))
        
        # Forecast start line
        fig.add_vline(
            x=len(historical_data) - 1,
            line_dash="dot",
            line_color="gray",
            line_width=2,
            annotation_text="Forecast Start",
            annotation_position="top"
        )
        
        # Apply layout
        layout = self._create_base_layout(title, "Time", "Value")
        fig.update_layout(**layout)
        
        # Add timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        fig.add_annotation(
            x=1, y=-0.1,
            xref='paper', yref='paper',
            text=f'Generated: {timestamp}',
            showarrow=False,
            font=dict(size=10, color='gray')
        )
        
        # Save if requested
        if save_path:
            if save_path.endswith('.html'):
                fig.write_html(save_path)
            else:
                fig.write_image(save_path)
            logger.info(f"Comparison plot saved to: {save_path}")
        
        # Show figure if requested
        if show_figure:
            fig.show()
        
        logger.info("✅ Interactive forecast comparison visualization completed")
        return fig
    
    def create_dashboard(
        self,
        historical_data: Union[List[float], np.ndarray],
        forecast: Union[List[float], np.ndarray],
        intervals: Optional[Dict[str, np.ndarray]] = None,
        covariates_data: Optional[Dict[str, Dict[str, Union[List[float], float, str]]]] = None,
        actual_future: Optional[Union[List[float], np.ndarray]] = None,
        dates_historical: Optional[List[Union[str, datetime]]] = None,
        dates_future: Optional[List[Union[str, datetime]]] = None,
        title: str = "TimesFM Forecasting Dashboard",
        target_name: str = "Value",
        save_path: Optional[str] = None,
        show_figure: bool = True,
        context_len: Optional[int] = None,
        horizon_len: Optional[int] = None,
        show_full_history: bool = True,
        y_axis_padding: float = 0.1
    ) -> go.Figure:
        """
        Create a comprehensive dashboard with multiple visualization panels.
        
        Args:
            historical_data: Historical time series data
            forecast: Point forecast values
            intervals: Optional prediction intervals
            covariates_data: Optional covariates data
            actual_future: Optional actual future values
            dates_historical: Optional historical dates
            dates_future: Optional future dates
            title: Dashboard title
            target_name: Name of target variable
            save_path: Optional save path
            show_figure: Whether to display the figure
            
        Returns:
            Plotly Figure object
        """
        logger.info(f"Creating interactive forecasting dashboard: {title}")
        
        # If covariates are provided, use the comprehensive view
        if covariates_data and len(covariates_data) > 0:
            return self.plot_forecast_with_covariates(
                historical_data, forecast, covariates_data, intervals,
                actual_future, dates_historical, dates_future,
                title, target_name, save_path, show_figure,
                context_len, horizon_len, show_full_history, y_axis_padding
            )
        else:
            # Otherwise, use the standard forecast view
            return self.plot_forecast_with_intervals(
                historical_data, forecast, intervals, actual_future,
                dates_historical, dates_future, title, target_name, save_path, show_figure,
                context_len, horizon_len, show_full_history, y_axis_padding
            )
    
    def export_to_json(self, fig: go.Figure, file_path: str) -> None:
        """
        Export a Plotly figure to JSON format for web integration.
        
        Args:
            fig: Plotly Figure object
            file_path: Path to save the JSON file
        """
        fig.write_json(file_path)
        logger.info(f"Figure exported to JSON: {file_path}")
    
    def get_figure_html(self, fig: go.Figure, include_plotlyjs: bool = True) -> str:
        """
        Get the HTML representation of a figure.
        
        Args:
            fig: Plotly Figure object
            include_plotlyjs: Whether to include Plotly.js in the HTML
            
        Returns:
            HTML string representation of the figure
        """
        return fig.to_html(include_plotlyjs=include_plotlyjs)
