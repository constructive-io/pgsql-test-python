"""
Pytest configuration and fixtures for pgsql-test.

This module provides reusable fixtures for testing the pgsql-test framework itself.
"""

import os
from pathlib import Path

import pytest

from pgsql_test import get_connections
from pgsql_test.types import PgConfig


def get_test_pg_config() -> PgConfig:
    """Get PostgreSQL configuration for tests."""
    return {
        "host": os.environ.get("PGHOST", "localhost"),
        "port": int(os.environ.get("PGPORT", "5432")),
        "database": os.environ.get("PGDATABASE", "postgres"),
        "user": os.environ.get("PGUSER", "postgres"),
        "password": os.environ.get("PGPASSWORD", ""),
    }


@pytest.fixture
def pg_config() -> PgConfig:
    """Fixture providing PostgreSQL configuration."""
    return get_test_pg_config()


@pytest.fixture
def db_connection():
    """
    Fixture providing a database connection with automatic teardown.

    Usage:
        def test_something(db_connection):
            conn = db_connection
            result = conn.db.query('SELECT 1')
    """
    conn = get_connections()
    yield conn
    conn.teardown()


@pytest.fixture
def db(db_connection):
    """
    Fixture providing just the db client with per-test isolation.

    Usage:
        def test_something(db):
            db.before_each()
            result = db.query('SELECT 1')
            db.after_each()
    """
    return db_connection.db


@pytest.fixture
def pg(db_connection):
    """
    Fixture providing the superuser pg client.

    Usage:
        def test_something(pg):
            result = pg.query('SELECT 1')
    """
    return db_connection.pg


@pytest.fixture
def sql_dir() -> Path:
    """Fixture providing path to test SQL files."""
    return Path(__file__).parent / "sql"
