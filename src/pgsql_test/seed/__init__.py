"""
Seed adapters for pgsql-test.

Provides composable seeding strategies for test databases:
- sqlfile: Execute raw SQL files
- fn: Run custom Python functions
- compose: Combine multiple adapters
- pgpm: Run pgpm migrations (requires pgpm CLI)
"""

from pgsql_test.seed.adapters import compose, fn
from pgsql_test.seed.pgpm import pgpm
from pgsql_test.seed.sql import sqlfile

__all__ = [
    "sqlfile",
    "fn",
    "compose",
    "pgpm",
]
