"""
SQL file seeding adapter.

Provides functionality to seed databases from SQL files.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pysql_test.types import SeedContext

logger = logging.getLogger(__name__)


class SqlFileSeedAdapter:
    """
    Seed adapter that executes SQL files.

    Usage:
        adapter = SqlFileSeedAdapter(['schema.sql', 'fixtures.sql'])
        await adapter.seed(ctx)
    """

    def __init__(self, files: list[str | Path]) -> None:
        """
        Initialize the SQL file seed adapter.

        Args:
            files: List of SQL file paths to execute
        """
        self._files = [Path(f) for f in files]

    def seed(self, ctx: SeedContext) -> None:
        """
        Execute the SQL files in order.

        Args:
            ctx: Seed context containing pg client and config
        """
        pg = ctx["pg"]

        for file_path in self._files:
            if not file_path.exists():
                raise FileNotFoundError(f"SQL file not found: {file_path}")

            logger.debug(f"Loading SQL file: {file_path}")
            sql_content = file_path.read_text(encoding="utf-8")

            # Execute the SQL
            pg.query(sql_content)
            logger.info(f"Executed SQL file: {file_path}")


def sqlfile(files: list[str | Path]) -> SqlFileSeedAdapter:
    """
    Create a SQL file seed adapter.

    Args:
        files: List of SQL file paths to execute

    Returns:
        A SqlFileSeedAdapter instance

    Example:
        seed_adapters = [seed.sqlfile(['schema.sql', 'fixtures.sql'])]
    """
    return SqlFileSeedAdapter(files)
