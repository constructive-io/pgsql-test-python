"""Type definitions for pgsql-test."""

from dataclasses import dataclass
from typing import Any, Protocol, TypedDict


class PgConfig(TypedDict, total=False):
    """PostgreSQL connection configuration."""

    host: str
    port: int
    database: str
    user: str
    password: str


class ConnectionOptions(TypedDict, total=False):
    """Options for database connections."""

    prefix: str  # Prefix for test database names
    root_db: str  # Root database for admin operations (default: postgres)
    extensions: list[str]  # Extensions to install
    template: str | None  # Template database to use


@dataclass
class ConnectionResult:
    """Result from get_connections()."""

    pg: Any  # PgTestClient connected as superuser
    db: Any  # PgTestClient connected as app user
    admin: Any  # DbAdmin instance
    manager: Any  # PgTestConnector instance
    teardown: Any  # Callable to teardown connections


class SeedContext(TypedDict):
    """Context passed to seed adapters."""

    config: PgConfig
    admin: Any  # DbAdmin
    pg: Any  # PgTestClient


class SeedAdapter(Protocol):
    """Protocol for seed adapters."""

    async def seed(self, ctx: SeedContext) -> None:
        """Execute the seeding operation."""
        ...


@dataclass
class QueryResult:
    """Result from a database query."""

    rows: list[dict[str, Any]]
    row_count: int
    status_message: str | None = None

    def __iter__(self) -> Any:
        return iter(self.rows)

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int) -> dict[str, Any]:
        return self.rows[index]
