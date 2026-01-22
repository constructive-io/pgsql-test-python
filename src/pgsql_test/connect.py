"""
Connection management for pgsql-test.

Provides the main entry point for setting up test database connections.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pgsql_test.admin import DbAdmin
from pgsql_test.client import PgTestClient
from pgsql_test.manager import PgTestConnector, generate_test_db_name
from pgsql_test.types import ConnectionOptions, PgConfig, SeedContext

logger = logging.getLogger(__name__)


def get_pg_config_from_env() -> PgConfig:
    """
    Get PostgreSQL configuration from environment variables.

    Environment variables:
        PGHOST: PostgreSQL host (default: localhost)
        PGPORT: PostgreSQL port (default: 5432)
        PGDATABASE: PostgreSQL database (default: postgres)
        PGUSER: PostgreSQL user (default: postgres)
        PGPASSWORD: PostgreSQL password (default: empty)

    Returns:
        PgConfig dictionary
    """
    return {
        "host": os.environ.get("PGHOST", "localhost"),
        "port": int(os.environ.get("PGPORT", "5432")),
        "database": os.environ.get("PGDATABASE", "postgres"),
        "user": os.environ.get("PGUSER", "postgres"),
        "password": os.environ.get("PGPASSWORD", ""),
    }


@dataclass
class ConnectionResult:
    """
    Result from get_connections().

    Attributes:
        pg: PgTestClient connected as superuser (for admin operations)
        db: PgTestClient connected as app user (for testing with RLS)
        admin: DbAdmin instance for database management
        manager: PgTestConnector instance managing connections
        teardown: Callable to clean up all connections and databases
    """

    pg: PgTestClient
    db: PgTestClient
    admin: DbAdmin
    manager: PgTestConnector
    _teardown_fn: Callable[[], None]
    _keep_db: bool = False

    def teardown(self, keep_db: bool | None = None) -> None:
        """
        Clean up all connections and optionally drop databases.

        Args:
            keep_db: If True, keep the databases after teardown.
                     If None, uses the default set during creation.
        """
        should_keep = keep_db if keep_db is not None else self._keep_db
        self.manager.close_all(keep_db=should_keep)


def get_connections(
    pg_config: PgConfig | None = None,
    connection_options: ConnectionOptions | None = None,
    seed_adapters: list[Any] | None = None,
) -> ConnectionResult:
    """
    Set up a fresh PostgreSQL test database and return connection objects.

    This is the main entry point for pgsql-test. It:
    1. Creates a new isolated database with a UUID name
    2. Installs any requested extensions
    3. Runs seed adapters to populate the database
    4. Returns clients for both superuser and app-level access

    Args:
        pg_config: PostgreSQL configuration. If None, reads from environment.
        connection_options: Options for database creation and connections.
        seed_adapters: List of seed adapters to run after database creation.

    Returns:
        ConnectionResult with pg, db, admin, manager, and teardown function.

    Example:
        from pgsql_test import get_connections, seed

        # Basic usage
        conn = get_connections()
        result = conn.db.query('SELECT 1')
        conn.teardown()

        # With seeding
        conn = get_connections(
            seed_adapters=[seed.sqlfile(['schema.sql', 'fixtures.sql'])]
        )

        # With pytest fixture
        @pytest.fixture
        def db():
            conn = get_connections()
            yield conn.db
            conn.teardown()
    """
    # Get configuration
    config = pg_config or get_pg_config_from_env()
    options = connection_options or {}

    # Generate unique database name
    prefix = options.get("prefix", "pgsql_test_")
    test_db_name = generate_test_db_name(prefix)

    # Create admin connection to root database
    root_db = options.get("root_db", "postgres")
    admin_config: PgConfig = {
        "host": config.get("host", "localhost"),
        "port": config.get("port", 5432),
        "database": root_db,
        "user": config.get("user", "postgres"),
        "password": config.get("password", ""),
    }

    admin = DbAdmin(admin_config, verbose=False)

    # Create the test database
    template = options.get("template")
    if template:
        admin.create_from_template(template, test_db_name)
    else:
        admin.create(test_db_name)

    # Install extensions if requested
    extensions = options.get("extensions", [])
    if extensions:
        admin.install_extensions(extensions, test_db_name)

    # Create configuration for the test database
    test_config: PgConfig = {
        "host": config.get("host", "localhost"),
        "port": config.get("port", 5432),
        "database": test_db_name,
        "user": config.get("user", "postgres"),
        "password": config.get("password", ""),
    }

    # Get the connection manager
    manager = PgTestConnector.get_instance(config)

    # Create the superuser client (pg)
    pg = manager.get_client(test_config)

    # Run seed adapters
    if seed_adapters:
        seed_context: SeedContext = {
            "config": test_config,
            "admin": admin,
            "pg": pg,
        }
        for adapter in seed_adapters:
            try:
                adapter.seed(seed_context)
            except Exception as e:
                logger.error(f"Seed adapter failed: {e}")
                # Continue without teardown to allow debugging
                raise

    # For now, db is the same as pg (both superuser)
    # In the future, we can add app-level user support
    db = pg

    # Create teardown function
    def teardown_fn() -> None:
        manager.close_all(keep_db=False)

    return ConnectionResult(
        pg=pg,
        db=db,
        admin=admin,
        manager=manager,
        _teardown_fn=teardown_fn,
    )
