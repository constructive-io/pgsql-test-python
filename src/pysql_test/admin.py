"""
DbAdmin - Database administration utilities for test environments.

Provides functionality for creating, dropping, and managing test databases.
"""

from __future__ import annotations

import logging
from typing import Any

import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

from pysql_test.types import PgConfig

logger = logging.getLogger(__name__)


class DbAdmin:
    """
    Database administration utilities for test environments.

    Provides methods for:
    - Creating and dropping databases
    - Installing extensions
    - Creating databases from templates
    - Managing roles and permissions
    """

    def __init__(self, config: PgConfig, verbose: bool = False) -> None:
        """
        Initialize the database admin.

        Args:
            config: PostgreSQL connection configuration
            verbose: Whether to log verbose output
        """
        self._config = config
        self._verbose = verbose
        self._conn: psycopg2.extensions.connection | None = None

    @property
    def config(self) -> PgConfig:
        """Return the connection configuration."""
        return self._config

    def _get_admin_connection(self) -> psycopg2.extensions.connection:
        """Get a connection for admin operations (autocommit mode)."""
        if self._conn is None or self._conn.closed:
            self._conn = psycopg2.connect(
                host=self._config.get("host", "localhost"),
                port=self._config.get("port", 5432),
                database=self._config.get("database", "postgres"),
                user=self._config.get("user", "postgres"),
                password=self._config.get("password", ""),
            )
            self._conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        return self._conn

    def close(self) -> None:
        """Close the admin connection."""
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception as e:
                logger.warning(f"Error closing admin connection: {e}")
            finally:
                self._conn = None

    def database_exists(self, database: str) -> bool:
        """Check if a database exists."""
        conn = self._get_admin_connection()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s",
                (database,),
            )
            return cur.fetchone() is not None

    def create(self, database: str) -> None:
        """
        Create a new database.

        Args:
            database: Name of the database to create
        """
        if self.database_exists(database):
            if self._verbose:
                logger.info(f"Database already exists: {database}")
            return

        conn = self._get_admin_connection()
        with conn.cursor() as cur:
            # Use sql.Identifier for safe database name handling
            cur.execute(
                sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database))
            )
        logger.info(f"Created database: {database}")

    def drop(self, database: str | None = None) -> None:
        """
        Drop a database.

        Args:
            database: Name of the database to drop (defaults to config database)
        """
        database = database or self._config.get("database")
        if not database:
            raise ValueError("No database specified to drop")

        if not self.database_exists(database):
            if self._verbose:
                logger.info(f"Database does not exist: {database}")
            return

        conn = self._get_admin_connection()
        with conn.cursor() as cur:
            # Terminate existing connections
            cur.execute(
                """
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = %s AND pid <> pg_backend_pid()
                """,
                (database,),
            )
            # Drop the database
            cur.execute(
                sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(database))
            )
        logger.info(f"Dropped database: {database}")

    def create_from_template(self, template: str, database: str) -> None:
        """
        Create a database from a template.

        Args:
            template: Name of the template database
            database: Name of the new database
        """
        if self.database_exists(database):
            if self._verbose:
                logger.info(f"Database already exists: {database}")
            return

        conn = self._get_admin_connection()
        with conn.cursor() as cur:
            cur.execute(
                sql.SQL("CREATE DATABASE {} TEMPLATE {}").format(
                    sql.Identifier(database),
                    sql.Identifier(template),
                )
            )
        logger.info(f"Created database {database} from template {template}")

    def install_extensions(
        self, extensions: list[str], database: str | None = None
    ) -> None:
        """
        Install PostgreSQL extensions in a database.

        Args:
            extensions: List of extension names to install
            database: Target database (defaults to config database)
        """
        database = database or self._config.get("database")
        if not database:
            raise ValueError("No database specified")

        # Connect to the target database
        conn = psycopg2.connect(
            host=self._config.get("host", "localhost"),
            port=self._config.get("port", 5432),
            database=database,
            user=self._config.get("user", "postgres"),
            password=self._config.get("password", ""),
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)

        try:
            with conn.cursor() as cur:
                for ext in extensions:
                    cur.execute(
                        sql.SQL("CREATE EXTENSION IF NOT EXISTS {}").format(
                            sql.Identifier(ext)
                        )
                    )
                    logger.debug(f"Installed extension: {ext}")
        finally:
            conn.close()

        logger.info(f"Installed extensions in {database}: {extensions}")

    def create_role(
        self,
        role_name: str,
        password: str | None = None,
        login: bool = True,
        superuser: bool = False,
    ) -> None:
        """
        Create a PostgreSQL role.

        Args:
            role_name: Name of the role to create
            password: Optional password for the role
            login: Whether the role can login
            superuser: Whether the role is a superuser
        """
        conn = self._get_admin_connection()
        with conn.cursor() as cur:
            # Check if role exists
            cur.execute(
                "SELECT 1 FROM pg_roles WHERE rolname = %s",
                (role_name,),
            )
            if cur.fetchone() is not None:
                if self._verbose:
                    logger.info(f"Role already exists: {role_name}")
                return

            # Build CREATE ROLE statement
            options = []
            if login:
                options.append("LOGIN")
            if superuser:
                options.append("SUPERUSER")
            if password:
                options.append(f"PASSWORD '{password}'")

            options_str = " ".join(options)
            cur.execute(
                sql.SQL("CREATE ROLE {} {}").format(
                    sql.Identifier(role_name),
                    sql.SQL(options_str),
                )
            )
        logger.info(f"Created role: {role_name}")

    def grant_connect(self, role_name: str, database: str) -> None:
        """
        Grant CONNECT privilege on a database to a role.

        Args:
            role_name: Name of the role
            database: Name of the database
        """
        conn = self._get_admin_connection()
        with conn.cursor() as cur:
            cur.execute(
                sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                    sql.Identifier(database),
                    sql.Identifier(role_name),
                )
            )
        logger.debug(f"Granted CONNECT on {database} to {role_name}")

    def grant_all(self, role_name: str, database: str) -> None:
        """
        Grant ALL privileges on a database to a role.

        Args:
            role_name: Name of the role
            database: Name of the database
        """
        conn = self._get_admin_connection()
        with conn.cursor() as cur:
            cur.execute(
                sql.SQL("GRANT ALL PRIVILEGES ON DATABASE {} TO {}").format(
                    sql.Identifier(database),
                    sql.Identifier(role_name),
                )
            )
        logger.debug(f"Granted ALL on {database} to {role_name}")

    def __enter__(self) -> DbAdmin:
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.close()
