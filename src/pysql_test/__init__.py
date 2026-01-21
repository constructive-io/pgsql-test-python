"""
pysql-test: PostgreSQL testing framework for Python.

Instant, isolated PostgreSQL databases for each test with automatic
transaction rollback, context switching, and clean seeding.
"""

from pysql_test import seed
from pysql_test.admin import DbAdmin
from pysql_test.client import PgTestClient
from pysql_test.connect import get_connections
from pysql_test.manager import PgTestConnector

__all__ = [
    "get_connections",
    "PgTestClient",
    "PgTestConnector",
    "DbAdmin",
    "seed",
]

__version__ = "0.1.0"
