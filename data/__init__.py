"""Sapheneia data service.

Python replacement for the Go data service. Reads/writes a TimescaleDB
prices cache; falls back to Yahoo Finance via the ``yfinance`` library on
cache miss; enforces backtest temporal isolation via ``end_date``.
"""

__all__: list[str] = []
