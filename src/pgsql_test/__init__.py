"""
pgsql-test: PostgreSQL testing framework for Python.

Instant, isolated PostgreSQL databases for each test with automatic
transaction rollback, context switching, and clean seeding.
"""

from pgsql_test import seed
from pgsql_test.admin import DbAdmin
from pgsql_test.client import PgTestClient
from pgsql_test.connect import get_connections
from pgsql_test.manager import PgTestConnector

__all__ = [
    "get_connections",
    "PgTestClient",
    "PgTestConnector",
    "DbAdmin",
    "seed",
]

__version__ = "0.2.0"
