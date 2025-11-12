def example_usage():
    """Example of how to use the trading strategy"""

    # Orchestrator maintains state
    initial_capital = 100000  # $100k
    available_cash = initial_capital
    current_position = 0.0

    # Example OHLC data (last 30 days)
    np.random.seed(42)
    open_history = np.random.uniform(95, 105, 30)
    high_history = np.random.uniform(100, 110, 30)
    low_history = np.random.uniform(90, 100, 30)
    close_history = np.random.uniform(95, 105, 30)

    print("=" * 60)
    print("Example 1: Threshold Strategy (Sign-based, threshold_value=0)")
    print("=" * 60)
    params_threshold = {
        "strategy_type": "threshold",
        "forecast_price": 105.0,
        "current_price": 100.0,
        "current_position": current_position,
        "available_cash": available_cash,
        "initial_capital": initial_capital,
        "threshold_type": "absolute",
        "threshold_value": 0.0,  # Sign-based (any difference triggers)
        "execution_size": 100,  # Buy 100 shares
    }

    result = TradingStrategy.execute_trading_signal(params_threshold)
    print(f"Action: {result['action']}")
    print(f"Size: {result['size']:.2f} shares")
    print(f"Value: ${result['value']:,.2f}")
    print(f"Reason: {result['reason']}")
    print(f"Available Cash: ${result['available_cash']:,.2f}")
    print(f"Position After: {result['position_after']:.2f} shares")

    # Update orchestrator state
    available_cash = result["available_cash"]
    current_position = result["position_after"]

    print("\n" + "=" * 60)
    print("Example 2: Return Strategy with Threshold")
    print("=" * 60)
    params_return = {
        "strategy_type": "return",
        "forecast_price": 108.0,
        "current_price": 100.0,
        "current_position": current_position,
        "available_cash": available_cash,
        "initial_capital": initial_capital,
        "position_sizing": "proportional",
        "threshold_type": "return",
        "threshold_value": 0.05,  # 5% return threshold
        "execution_size": 10,
        "max_position_size": 150,
        "min_position_size": 5,
    }

    result = TradingStrategy.execute_trading_signal(params_return)
    print(f"Action: {result['action']}")
    print(f"Size: {result['size']:.2f} shares")
    print(f"Reason: {result['reason']}")

    # Update orchestrator state
    available_cash = result["available_cash"]
    current_position = result["position_after"]

    print("\n" + "=" * 60)
    print("Example 3: Quantile Strategy")
    print("=" * 60)

    # Define quantile signals
    quantile_signals = {
        1: {"range": [0, 5], "signal": "sell", "multiplier": 1.0},
        2: {"range": [5, 10], "signal": "sell", "multiplier": 0.5},
        3: {"range": [10, 25], "signal": "sell", "multiplier": 0.25},
        4: {"range": [75, 90], "signal": "buy", "multiplier": 0.25},
        5: {"range": [90, 95], "signal": "buy", "multiplier": 0.75},
        6: {"range": [95, 100], "signal": "buy", "multiplier": 1.0},
    }

    params_quantile = {
        "strategy_type": "quantile",
        "forecast_price": 110.0,
        "current_price": 100.0,
        "current_position": current_position,
        "available_cash": available_cash,
        "initial_capital": initial_capital,
        "open_history": open_history,
        "high_history": high_history,
        "low_history": low_history,
        "close_history": close_history,
        "which_history": "close",
        "window_history": 20,
        "quantile_signals": quantile_signals,
        "position_sizing": "fixed",
        "execution_size": 100,
        "max_position_size": 200,
        "min_position_size": 10,
        "min_history_length": 5,
    }

    result = TradingStrategy.execute_trading_signal(params_quantile)
    print(f"Action: {result['action']}")
    print(f"Size: {result['size']:.2f} shares")
    print(f"Reason: {result['reason']}")

    # Update orchestrator state
    available_cash = result["available_cash"]
    current_position = result["position_after"]

    # Check final portfolio status
    print("\n" + "=" * 60)
    print("Portfolio Summary")
    print("=" * 60)
    current_price = 100.0
    portfolio_value = TradingStrategy.get_portfolio_value(
        current_position, current_price, available_cash
    )
    portfolio_return = TradingStrategy.get_portfolio_return(
        current_position, current_price, available_cash, initial_capital
    )

    print(f"Initial Capital: ${initial_capital:,.2f}")
    print(f"Available Cash: ${available_cash:,.2f}")
    print(f"Current Position: {current_position:.2f} shares")
    print(f"Portfolio Value: ${portfolio_value:,.2f}")
    print(f"Portfolio Return: {portfolio_return:.2%}")


if __name__ == "__main__":
    example_usage()
