"""
Generic seed adapters for pgsql-test.

Provides composable seeding utilities:
- fn: Run custom Python functions
- compose: Combine multiple adapters
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pgsql_test.types import SeedContext

logger = logging.getLogger(__name__)


class FnSeedAdapter:
    """
    Seed adapter that runs a custom function.

    Usage:
        adapter = FnSeedAdapter(lambda ctx: ctx['pg'].query('INSERT INTO ...'))
        adapter.seed(ctx)
    """

    def __init__(self, func: Callable[[SeedContext], None]) -> None:
        """
        Initialize the function seed adapter.

        Args:
            func: Function to execute during seeding
        """
        self._func = func

    def seed(self, ctx: SeedContext) -> None:
        """
        Execute the seed function.

        Args:
            ctx: Seed context containing pg client and config
        """
        logger.debug("Executing custom seed function")
        self._func(ctx)
        logger.debug("Custom seed function completed")


class ComposeSeedAdapter:
    """
    Seed adapter that composes multiple adapters.

    Executes adapters in order.

    Usage:
        adapter = ComposeSeedAdapter([
            seed.sqlfile(['schema.sql']),
            seed.fn(lambda ctx: ctx['pg'].query('INSERT INTO ...'))
        ])
        adapter.seed(ctx)
    """

    def __init__(self, adapters: list[FnSeedAdapter | ComposeSeedAdapter | object]) -> None:
        """
        Initialize the compose adapter.

        Args:
            adapters: List of seed adapters to compose
        """
        self._adapters = adapters

    def seed(self, ctx: SeedContext) -> None:
        """
        Execute all adapters in order.

        Args:
            ctx: Seed context containing pg client and config
        """
        for i, adapter in enumerate(self._adapters):
            logger.debug(f"Executing seed adapter {i + 1}/{len(self._adapters)}")
            adapter.seed(ctx)  # type: ignore
        logger.debug(f"Completed {len(self._adapters)} seed adapters")


def fn(func: Callable[[SeedContext], None]) -> FnSeedAdapter:
    """
    Create a function seed adapter.

    Args:
        func: Function to execute during seeding.
              Receives SeedContext with 'pg', 'admin', and 'config'.

    Returns:
        A FnSeedAdapter instance

    Example:
        seed_adapters = [
            seed.fn(lambda ctx: ctx['pg'].query('INSERT INTO users (name) VALUES (%s)', ('Alice',)))
        ]
    """
    return FnSeedAdapter(func)


def compose(adapters: list[object]) -> ComposeSeedAdapter:
    """
    Compose multiple seed adapters into one.

    Args:
        adapters: List of seed adapters to compose

    Returns:
        A ComposeSeedAdapter instance

    Example:
        seed_adapters = [
            seed.compose([
                seed.sqlfile(['schema.sql']),
                seed.fn(lambda ctx: ctx['pg'].query('INSERT INTO ...'))
            ])
        ]
    """
    return ComposeSeedAdapter(adapters)
