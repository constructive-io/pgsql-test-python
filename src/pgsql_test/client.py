"""
PgTestClient - A test-friendly PostgreSQL client with transaction management.

Provides automatic transaction and savepoint management for test isolation,
easy context switching for RLS testing, and a clean API for integration tests.
"""

from __future__ import annotations

import logging
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor

from pgsql_test.types import PgConfig, QueryResult

logger = logging.getLogger(__name__)


class PgTestClient:
    """
    A PostgreSQL client wrapper designed for testing.

    Provides:
    - Automatic transaction and savepoint management for test isolation
    - Easy switching of role-based contexts for RLS testing
    - A clean, high-level API for integration testing PostgreSQL systems

    Usage:
        client = PgTestClient(config)
        await client.connect()

        # In each test
        client.before_each()  # Begin transaction + savepoint
        # ... run test queries ...
        client.after_each()   # Rollback to savepoint

        client.close()
    """

    def __init__(self, config: PgConfig, enhanced_errors: bool = True) -> None:
        """
        Initialize the test client.

        Args:
            config: PostgreSQL connection configuration
            enhanced_errors: Whether to enhance error messages with PG details
        """
        self._config = config
        self._enhanced_errors = enhanced_errors
        self._conn: psycopg2.extensions.connection | None = None
        self._context: dict[str, str] = {}
        self._in_transaction = False
        self._savepoint_name = "pgsql_test_savepoint"

    @property
    def config(self) -> PgConfig:
        """Return the connection configuration."""
        return self._config

    @property
    def connection(self) -> psycopg2.extensions.connection:
        """Return the underlying psycopg2 connection."""
        if self._conn is None:
            raise RuntimeError("Client not connected. Call connect() first.")
        return self._conn

    def connect(self) -> None:
        """Establish connection to the database."""
        if self._conn is not None:
            return

        self._conn = psycopg2.connect(
            host=self._config.get("host", "localhost"),
            port=self._config.get("port", 5432),
            database=self._config.get("database", "postgres"),
            user=self._config.get("user", "postgres"),
            password=self._config.get("password", ""),
            cursor_factory=RealDictCursor,
        )
        # Set autocommit to False for transaction management
        self._conn.autocommit = False
        logger.debug(f"Connected to database: {self._config.get('database')}")

    def close(self) -> None:
        """Close the database connection."""
        if self._conn is not None:
            try:
                if self._in_transaction:
                    self._conn.rollback()
                self._conn.close()
                logger.debug(f"Closed connection to: {self._config.get('database')}")
            except Exception as e:
                logger.warning(f"Error closing connection: {e}")
            finally:
                self._conn = None
                self._in_transaction = False

    def query(self, sql: str, params: tuple[Any, ...] | None = None) -> QueryResult:
        """
        Execute a SQL query and return results.

        Args:
            sql: SQL query string
            params: Optional query parameters

        Returns:
            QueryResult with rows and metadata
        """
        conn = self.connection
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                # Check if this is a SELECT-like query that returns rows
                if cur.description is not None:
                    rows = [dict(row) for row in cur.fetchall()]
                    return QueryResult(
                        rows=rows,
                        row_count=cur.rowcount,
                        status_message=cur.statusmessage,
                    )
                else:
                    return QueryResult(
                        rows=[],
                        row_count=cur.rowcount,
                        status_message=cur.statusmessage,
                    )
        except psycopg2.Error as e:
            if self._enhanced_errors:
                raise self._enhance_error(e, sql, params) from e
            raise

    def one(self, sql: str, params: tuple[Any, ...] | None = None) -> dict[str, Any]:
        """
        Execute a query and return exactly one row.

        Raises:
            ValueError: If query returns zero or more than one row
        """
        result = self.query(sql, params)
        if len(result.rows) == 0:
            raise ValueError("Query returned no rows, expected exactly one")
        if len(result.rows) > 1:
            raise ValueError(f"Query returned {len(result.rows)} rows, expected exactly one")
        return result.rows[0]

    def one_or_none(self, sql: str, params: tuple[Any, ...] | None = None) -> dict[str, Any] | None:
        """
        Execute a query and return one row or None.

        Raises:
            ValueError: If query returns more than one row
        """
        result = self.query(sql, params)
        if len(result.rows) == 0:
            return None
        if len(result.rows) > 1:
            raise ValueError(f"Query returned {len(result.rows)} rows, expected at most one")
        return result.rows[0]

    def many(self, sql: str, params: tuple[Any, ...] | None = None) -> list[dict[str, Any]]:
        """
        Execute a query and return all rows.

        Raises:
            ValueError: If query returns no rows
        """
        result = self.query(sql, params)
        if len(result.rows) == 0:
            raise ValueError("Query returned no rows, expected at least one")
        return result.rows

    def many_or_none(self, sql: str, params: tuple[Any, ...] | None = None) -> list[dict[str, Any]]:
        """Execute a query and return all rows (may be empty)."""
        result = self.query(sql, params)
        return result.rows

    def execute(self, sql: str, params: tuple[Any, ...] | None = None) -> int:
        """
        Execute a SQL statement and return affected row count.

        Use this for INSERT, UPDATE, DELETE statements.
        """
        result = self.query(sql, params)
        return result.row_count

    def set_context(self, context: dict[str, str]) -> None:
        """
        Set PostgreSQL session context variables.

        Useful for simulating RLS contexts in tests.

        Args:
            context: Dictionary of context variables to set
                     e.g., {"role": "authenticated", "jwt.claims.user_id": "123"}
        """
        self._context.update(context)
        self._apply_context()

    def clear_context(self) -> None:
        """Clear all context variables."""
        self._context = {}

    def _apply_context(self) -> None:
        """Apply context variables to the current session."""
        conn = self.connection
        with conn.cursor() as cur:
            for key, value in self._context.items():
                # Use SET LOCAL so it only applies within the current transaction
                cur.execute(f"SET LOCAL {key} = %s", (value,))

    def begin(self) -> None:
        """Begin a new transaction."""
        if self._in_transaction:
            return
        # psycopg2 auto-begins transactions, but we track state
        self._in_transaction = True
        logger.debug("Transaction started")

    def commit(self) -> None:
        """Commit the current transaction."""
        conn = self.connection
        conn.commit()
        self._in_transaction = False
        logger.debug("Transaction committed")

    def rollback(self) -> None:
        """Rollback the current transaction."""
        conn = self.connection
        conn.rollback()
        self._in_transaction = False
        logger.debug("Transaction rolled back")

    def savepoint(self, name: str | None = None) -> None:
        """Create a savepoint within the current transaction."""
        name = name or self._savepoint_name
        conn = self.connection
        with conn.cursor() as cur:
            cur.execute(f"SAVEPOINT {name}")
        logger.debug(f"Savepoint created: {name}")

    def rollback_to_savepoint(self, name: str | None = None) -> None:
        """Rollback to a savepoint."""
        name = name or self._savepoint_name
        conn = self.connection
        with conn.cursor() as cur:
            cur.execute(f"ROLLBACK TO SAVEPOINT {name}")
        logger.debug(f"Rolled back to savepoint: {name}")

    def before_each(self) -> None:
        """
        Call at the start of each test.

        Begins a transaction and creates a savepoint for rollback.
        """
        self.begin()
        self.savepoint()
        if self._context:
            self._apply_context()

    def after_each(self) -> None:
        """
        Call at the end of each test.

        Rolls back to the savepoint and commits the outer transaction,
        effectively undoing all changes made during the test.
        """
        self.rollback_to_savepoint()
        self.commit()

    def _enhance_error(
        self, error: psycopg2.Error, sql: str, params: tuple[Any, ...] | None
    ) -> psycopg2.Error:
        """Enhance a psycopg2 error with additional context."""
        parts = [str(error)]

        # Add PostgreSQL error details if available
        if hasattr(error, "pgcode") and error.pgcode:
            parts.append(f"Error Code: {error.pgcode}")
        if hasattr(error, "pgerror") and error.pgerror:
            parts.append(f"Detail: {error.pgerror}")

        # Add query preview
        sql_preview = sql[:200] + "..." if len(sql) > 200 else sql
        parts.append(f"Query: {sql_preview}")

        if params:
            parts.append(f"Params: {params}")

        enhanced_msg = "\n".join(parts)
        error.args = (enhanced_msg,)
        return error

    def __enter__(self) -> PgTestClient:
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.close()
