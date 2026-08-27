"""Sapheneia CLI — `sapheneia simulate ...` developer escape hatch.

The CLI POSTs a single rendered strategy YAML to the orchestrator service and
polls until it's done. For matrix runs use the `run-simulation` Claude Code
skill (which goes through the MCP server).
"""

from __future__ import annotations

import logging

import click

from .commands.simulate import simulate as simulate_cmd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


@click.group()
@click.version_option(package_name="sapheneia", prog_name="sapheneia")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.option("--quiet", "-q", is_flag=True, help="Suppress non-error output")
def cli(verbose: bool, quiet: bool) -> None:
    """Sapheneia — single-strategy backtest escape hatch.

    Examples:

    \b
        sapheneia simulate --strategy simulations/templates/spy_chronos_tiny.example.yaml
    """
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    elif quiet:
        logging.getLogger().setLevel(logging.ERROR)


cli.add_command(simulate_cmd)


def main() -> int:
    cli(standalone_mode=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
