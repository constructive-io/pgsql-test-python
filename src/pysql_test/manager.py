"""
PgTestConnector - Connection pool manager for test environments.

Manages database connections, creates isolated test databases,
and handles cleanup/teardown.
"""

from __future__ import annotations

import atexit
import logging
import signal
import uuid
from typing import Any

from pysql_test.admin import DbAdmin
from pysql_test.client import PgTestClient
from pysql_test.types import PgConfig

logger = logging.getLogger(__name__)


class PgTestConnector:
    """
    Connection pool manager for PostgreSQL test environments.

    Manages:
    - Creation of isolated test databases with UUID names
    - Connection pooling for test clients
    - Automatic cleanup on shutdown

    This is a singleton class - use get_instance() to get the shared instance.
    """

    _instance: PgTestConnector | None = None

    def __init__(self, config: PgConfig, verbose: bool = False) -> None:
        """
        Initialize the connector.

        Args:
            config: Base PostgreSQL configuration
            verbose: Whether to log verbose output
        """
        self._config = config
        self._verbose = verbose
        self._clients: set[PgTestClient] = set()
        self._seen_databases: dict[str, PgConfig] = {}
        self._shutting_down = False

        # Register cleanup handlers
        atexit.register(self._cleanup_on_exit)
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

    @classmethod
    def get_instance(cls, config: PgConfig, verbose: bool = False) -> PgTestConnector:
        """
        Get the singleton instance of PgTestConnector.

        Args:
            config: Base PostgreSQL configuration
            verbose: Whether to log verbose output

        Returns:
            The shared PgTestConnector instance
        """
        if cls._instance is None:
            cls._instance = cls(config, verbose)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance (useful for testing)."""
        if cls._instance is not None:
            cls._instance.close_all()
            cls._instance = None

    @property
    def config(self) -> PgConfig:
        """Return the base configuration."""
        return self._config

    def _signal_handler(self, signum: int, frame: Any) -> None:
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, closing all connections...")
        self.close_all()

    def _cleanup_on_exit(self) -> None:
        """Cleanup handler for atexit."""
        if not self._shutting_down:
            self.close_all()

    def begin_teardown(self) -> None:
        """Mark that teardown has begun (prevents new clients)."""
        self._shutting_down = True

    def get_client(self, config: PgConfig) -> PgTestClient:
        """
        Get a new test client for the given configuration.

        Args:
            config: PostgreSQL configuration for the client

        Returns:
            A new PgTestClient instance

        Raises:
            RuntimeError: If connector is shutting down
        """
        if self._shutting_down:
            raise RuntimeError("PgTestConnector is shutting down; no new clients allowed")

        client = PgTestClient(config)
        client.connect()
        self._clients.add(client)

        # Track the database for cleanup
        db_key = f"{config.get('host')}:{config.get('port')}/{config.get('database')}"
        self._seen_databases[db_key] = config

        logger.debug(f"Created new client for database: {config.get('database')}")
        return client

    def close_all(self, keep_db: bool = False) -> None:
        """
        Close all connections and optionally drop databases.

        Args:
            keep_db: If True, keep the databases after closing connections
        """
        self.begin_teardown()

        # Close all clients
        logger.info("Closing all PgTestClients...")
        for client in list(self._clients):
            try:
                client.close()
                logger.debug(f"Closed client for {client.config.get('database')}")
            except Exception as e:
                logger.warning(f"Error closing client: {e}")
        self._clients.clear()

        # Drop databases unless keep_db is True
        if not keep_db:
            logger.info("Dropping test databases...")
            for config in list(self._seen_databases.values()):
                try:
                    # Use admin connection to drop the database
                    admin_config: PgConfig = {
                        "host": config.get("host", "localhost"),
                        "port": config.get("port", 5432),
                        "database": "postgres",  # Connect to postgres to drop other DBs
                        "user": self._config.get("user", "postgres"),
                        "password": self._config.get("password", ""),
                    }
                    admin = DbAdmin(admin_config, verbose=self._verbose)
                    admin.drop(config.get("database"))
                    admin.close()
                    logger.info(f"Dropped database: {config.get('database')}")
                except Exception as e:
                    logger.warning(f"Error dropping database {config.get('database')}: {e}")
        else:
            db_names = [c.get("database") for c in self._seen_databases.values()]
            logger.info(f"Keeping databases: {db_names}")

        self._seen_databases.clear()
        self._shutting_down = False
        logger.info("Teardown complete")

    def close(self) -> None:
        """Alias for close_all()."""
        self.close_all()

    def drop(self, config: PgConfig) -> None:
        """
        Drop a specific database.

        Args:
            config: Configuration of the database to drop
        """
        admin_config: PgConfig = {
            "host": config.get("host", "localhost"),
            "port": config.get("port", 5432),
            "database": "postgres",
            "user": self._config.get("user", "postgres"),
            "password": self._config.get("password", ""),
        }
        admin = DbAdmin(admin_config, verbose=self._verbose)
        admin.drop(config.get("database"))
        admin.close()

        # Remove from tracking
        db_key = f"{config.get('host')}:{config.get('port')}/{config.get('database')}"
        self._seen_databases.pop(db_key, None)

    def kill(self, client: PgTestClient) -> None:
        """
        Close a client and drop its database.

        Args:
            client: The client to kill
        """
        client.close()
        self._clients.discard(client)
        self.drop(client.config)


def generate_test_db_name(prefix: str = "pysql_test_") -> str:
    """
    Generate a unique test database name.

    Args:
        prefix: Prefix for the database name

    Returns:
        A unique database name like "pysql_test_abc123..."
    """
    return f"{prefix}{uuid.uuid4().hex[:12]}"
