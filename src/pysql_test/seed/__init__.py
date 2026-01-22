"""
Seed adapters for pysql-test.

Provides composable seeding strategies for test databases:
- sqlfile: Execute raw SQL files
- fn: Run custom Python functions
- compose: Combine multiple adapters
- pgpm: Run pgpm migrations (requires pgpm CLI)
"""

from pysql_test.seed.adapters import compose, fn
from pysql_test.seed.pgpm import pgpm
from pysql_test.seed.sql import sqlfile

__all__ = [
    "sqlfile",
    "fn",
    "compose",
    "pgpm",
]
