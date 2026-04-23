"""sapheneia-mcp server entry point.

Registers 12 tools and starts either an HTTP/SSE server or a stdio transport.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import Any, Optional

# Path bootstrap when run as a script
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sapheneia_mcp.config import settings  # noqa: E402
from sapheneia_mcp.tools import cache as cache_tools  # noqa: E402
from sapheneia_mcp.tools import combinations as combo_tools  # noqa: E402
from sapheneia_mcp.tools import passthroughs as pt_tools  # noqa: E402
from sapheneia_mcp.tools import runs as run_tools  # noqa: E402

logger = logging.getLogger("sapheneia.mcp")


def build_server():
    """Construct an MCP server with our 12 tools registered.

    Imports the MCP SDK lazily so unit tests can exercise the underlying
    tool functions without requiring the SDK installed.
    """
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:  # pragma: no cover - import guard
        raise RuntimeError(
            "The 'mcp' package is required to start the MCP server. "
            "Install with `uv pip install -e .[mcp]`."
        ) from exc

    server = FastMCP("sapheneia-mcp")

    # ----- Composite tools (delegate to orchestrator) ------------------------

    @server.tool()
    def validate_combinations(yaml_text: str) -> dict:
        """Validate a combinations YAML against the schema."""
        return combo_tools.validate_combinations(yaml_text)

    @server.tool()
    def expand_matrix(yaml_text: str) -> list[dict]:
        """Expand the matrix into forecast cohorts."""
        return combo_tools.expand_matrix(yaml_text)

    @server.tool()
    def render_strategies(combinations_yaml_text: str, cohort: dict) -> list[str]:
        """Render strategy YAMLs for one cohort."""
        return combo_tools.render_strategies(combinations_yaml_text, cohort)

    @server.tool()
    async def run_simulation(strategy_yaml: str) -> dict:
        """Submit one rendered strategy YAML to the orchestrator."""
        return await run_tools.run_simulation(strategy_yaml)

    @server.tool()
    async def run_simulation_batch(strategy_yamls: list[str]) -> list[dict]:
        """Submit a list of rendered strategy YAMLs."""
        return await run_tools.run_simulation_batch(strategy_yamls)

    @server.tool()
    async def get_run_status(run_ids: list[str]) -> list[dict]:
        """Get status for one or more run_ids."""
        return await run_tools.get_run_status(run_ids)

    @server.tool()
    async def query_results(
        experiment_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict]:
        """List runs filtered by experiment_id / status / limit."""
        return await run_tools.query_results(experiment_id=experiment_id, status=status, limit=limit)

    @server.tool()
    async def delete_run(run_id: str) -> dict:
        """Cancel and delete a run plus its cascading rows."""
        return await cache_tools.delete_run(run_id)

    @server.tool()
    async def delete_cache(
        experiment_id: Optional[str] = None,
        older_than_seconds: Optional[int] = None,
    ) -> dict:
        """Bulk cache cleanup by experiment_id or TTL."""
        return await cache_tools.delete_cache(
            experiment_id=experiment_id, older_than_seconds=older_than_seconds
        )

    # ----- Passthrough tools (leaf services) --------------------------------

    @server.tool()
    async def fetch_prices(
        ticker: str,
        start: str,
        end: str,
        end_date: Optional[str] = None,
        interval: str = "1d",
    ) -> dict:
        """Direct price query against the data service."""
        return await pt_tools.fetch_prices(
            ticker=ticker, start=start, end=end, end_date=end_date, interval=interval
        )

    @server.tool()
    async def forecast(
        model_id: str,
        context: list[float],
        prediction_length: int,
        num_samples: int = 20,
    ) -> dict:
        """Direct forecast call."""
        return await pt_tools.forecast(
            model_id=model_id, context=context, prediction_length=prediction_length, num_samples=num_samples
        )

    @server.tool()
    async def execute_trade(
        strategy_type: str,
        forecast_price: float,
        current_price: float,
        current_position: float,
        available_cash: float,
        initial_capital: float,
        params: Optional[dict[str, Any]] = None,
    ) -> dict:
        """Direct trading.execute call."""
        return await pt_tools.execute_trade(
            strategy_type=strategy_type,
            forecast_price=forecast_price,
            current_price=current_price,
            current_position=current_position,
            available_cash=available_cash,
            initial_capital=initial_capital,
            params=params,
        )

    @server.tool()
    async def compute_metrics(returns: list[float], metric: str = "performance") -> dict:
        """Direct metrics call."""
        return await pt_tools.compute_metrics(returns=returns, metric=metric)

    return server


def main() -> None:
    parser = argparse.ArgumentParser(description="sapheneia-mcp server")
    parser.add_argument("--transport", choices=["stdio", "sse"], default="stdio")
    parser.add_argument("--host", default=settings.HOST)
    parser.add_argument("--port", type=int, default=settings.PORT)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    server = build_server()
    if args.transport == "stdio":
        logger.info("Starting sapheneia-mcp on stdio")
        server.run()
    else:
        logger.info("Starting sapheneia-mcp on http://%s:%s/sse", args.host, args.port)
        server.settings.host = args.host
        server.settings.port = args.port
        server.run(transport="sse")


if __name__ == "__main__":
    main()
