"""
Basic tests for pgsql-test framework.

These tests verify the core functionality of the testing framework itself.
"""


import pytest

from pgsql_test import get_connections, seed
from pgsql_test.admin import DbAdmin
from pgsql_test.manager import generate_test_db_name


class TestGetConnections:
    """Tests for the get_connections() function."""

    def test_creates_isolated_database(self, pg_config):
        """Test that get_connections creates a new isolated database."""
        conn = get_connections(pg_config)
        try:
            # Verify we got a connection
            assert conn.pg is not None
            assert conn.db is not None
            assert conn.admin is not None
            assert conn.manager is not None

            # Verify the database name is unique (contains UUID)
            db_name = conn.pg.config.get("database", "")
            assert db_name.startswith("pgsql_test_")
            assert len(db_name) > len("pgsql_test_")
        finally:
            conn.teardown()

    def test_database_is_functional(self, pg_config):
        """Test that the created database can execute queries."""
        conn = get_connections(pg_config)
        try:
            result = conn.db.query("SELECT 1 as value")
            assert len(result.rows) == 1
            assert result.rows[0]["value"] == 1
        finally:
            conn.teardown()

    def test_teardown_drops_database(self, pg_config):
        """Test that teardown drops the test database."""
        conn = get_connections(pg_config)
        db_name = conn.pg.config.get("database")

        # Verify database exists
        admin = DbAdmin(pg_config)
        assert admin.database_exists(db_name)
        admin.close()

        # Teardown
        conn.teardown()

        # Verify database is dropped
        admin = DbAdmin(pg_config)
        assert not admin.database_exists(db_name)
        admin.close()


class TestPgTestClient:
    """Tests for the PgTestClient class."""

    def test_query_returns_results(self, db_connection):
        """Test that query() returns proper results."""
        result = db_connection.db.query("SELECT 1 as num, 'hello' as greeting")
        assert len(result.rows) == 1
        assert result.rows[0]["num"] == 1
        assert result.rows[0]["greeting"] == "hello"

    def test_query_with_params(self, db_connection):
        """Test that query() handles parameters correctly."""
        result = db_connection.db.query(
            "SELECT %s as value, %s as name",
            (42, "test"),
        )
        assert result.rows[0]["value"] == 42
        assert result.rows[0]["name"] == "test"

    def test_one_returns_single_row(self, db_connection):
        """Test that one() returns exactly one row."""
        row = db_connection.db.one("SELECT 1 as value")
        assert row["value"] == 1

    def test_one_raises_on_no_rows(self, db_connection):
        """Test that one() raises when no rows returned."""
        db_connection.db.query("CREATE TEMP TABLE empty_table (id INT)")
        with pytest.raises(ValueError, match="no rows"):
            db_connection.db.one("SELECT * FROM empty_table")

    def test_one_or_none_returns_none(self, db_connection):
        """Test that one_or_none() returns None when no rows."""
        db_connection.db.query("CREATE TEMP TABLE empty_table (id INT)")
        result = db_connection.db.one_or_none("SELECT * FROM empty_table")
        assert result is None

    def test_many_returns_multiple_rows(self, db_connection):
        """Test that many() returns multiple rows."""
        rows = db_connection.db.many(
            "SELECT generate_series(1, 3) as num"
        )
        assert len(rows) == 3
        assert [r["num"] for r in rows] == [1, 2, 3]

    def test_execute_returns_row_count(self, db_connection):
        """Test that execute() returns affected row count."""
        db_connection.db.query("CREATE TEMP TABLE test_exec (id INT)")
        count = db_connection.db.execute(
            "INSERT INTO test_exec VALUES (1), (2), (3)"
        )
        assert count == 3

    def test_transaction_rollback(self, db_connection):
        """Test that before_each/after_each provides transaction isolation."""
        db = db_connection.db

        # Create a table
        db.query("CREATE TABLE rollback_test (id INT)")
        db.connection.commit()

        # Start test isolation
        db.before_each()

        # Insert data
        db.execute("INSERT INTO rollback_test VALUES (1), (2)")
        result = db.query("SELECT COUNT(*) as count FROM rollback_test")
        assert result.rows[0]["count"] == 2

        # Rollback
        db.after_each()

        # Verify data is gone
        result = db.query("SELECT COUNT(*) as count FROM rollback_test")
        assert result.rows[0]["count"] == 0

    def test_set_context(self, db_connection):
        """Test that set_context() sets session variables."""
        db = db_connection.db
        db.begin()

        db.set_context({"app.user_id": "123"})

        result = db.one("SELECT current_setting('app.user_id') as user_id")
        assert result["user_id"] == "123"

        db.rollback()


class TestSqlFileSeeding:
    """Tests for SQL file seeding."""

    def test_sqlfile_loads_schema(self, pg_config, sql_dir):
        """Test that sqlfile adapter loads SQL files."""
        schema_file = sql_dir / "schema.sql"

        conn = get_connections(
            pg_config,
            seed_adapters=[seed.sqlfile([schema_file])],
        )
        try:
            # Verify tables were created
            result = conn.db.query(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name IN ('users', 'posts')
                ORDER BY table_name
                """
            )
            tables = [r["table_name"] for r in result.rows]
            assert "posts" in tables
            assert "users" in tables

            # Verify data was inserted
            users = conn.db.many("SELECT * FROM users ORDER BY id")
            assert len(users) == 2
            assert users[0]["name"] == "Alice"
            assert users[1]["name"] == "Bob"

            posts = conn.db.many("SELECT * FROM posts ORDER BY id")
            assert len(posts) == 3
        finally:
            conn.teardown()

    def test_sqlfile_raises_on_missing_file(self, pg_config):
        """Test that sqlfile raises when file doesn't exist."""
        conn = get_connections(pg_config)
        try:
            with pytest.raises(FileNotFoundError):
                seed.sqlfile(["/nonexistent/file.sql"]).seed({
                    "config": conn.pg.config,
                    "admin": conn.admin,
                    "pg": conn.pg,
                })
        finally:
            conn.teardown()


class TestFnSeeding:
    """Tests for function-based seeding."""

    def test_fn_adapter_executes_function(self, pg_config):
        """Test that fn adapter executes the provided function."""
        def my_seed(ctx):
            ctx["pg"].query("CREATE TABLE fn_test (value TEXT)")
            ctx["pg"].execute("INSERT INTO fn_test VALUES ('seeded')")

        conn = get_connections(
            pg_config,
            seed_adapters=[seed.fn(my_seed)],
        )
        try:
            result = conn.db.one("SELECT value FROM fn_test")
            assert result["value"] == "seeded"
        finally:
            conn.teardown()


class TestComposeSeeding:
    """Tests for composed seeding."""

    def test_compose_runs_adapters_in_order(self, pg_config):
        """Test that compose runs adapters in order."""
        execution_order = []

        def first_seed(ctx):
            execution_order.append("first")
            ctx["pg"].query("CREATE TABLE compose_test (step INT)")

        def second_seed(ctx):
            execution_order.append("second")
            ctx["pg"].execute("INSERT INTO compose_test VALUES (1)")

        def third_seed(ctx):
            execution_order.append("third")
            ctx["pg"].execute("INSERT INTO compose_test VALUES (2)")

        conn = get_connections(
            pg_config,
            seed_adapters=[
                seed.compose([
                    seed.fn(first_seed),
                    seed.fn(second_seed),
                    seed.fn(third_seed),
                ])
            ],
        )
        try:
            assert execution_order == ["first", "second", "third"]

            result = conn.db.many("SELECT step FROM compose_test ORDER BY step")
            assert [r["step"] for r in result] == [1, 2]
        finally:
            conn.teardown()


class TestDbAdmin:
    """Tests for DbAdmin class."""

    def test_create_and_drop_database(self, pg_config):
        """Test creating and dropping a database."""
        admin = DbAdmin(pg_config)
        test_db = f"pgsql_admin_test_{generate_test_db_name('')}"

        try:
            # Create
            admin.create(test_db)
            assert admin.database_exists(test_db)

            # Drop
            admin.drop(test_db)
            assert not admin.database_exists(test_db)
        finally:
            # Cleanup in case of failure
            if admin.database_exists(test_db):
                admin.drop(test_db)
            admin.close()

    def test_install_extensions(self, pg_config):
        """Test installing extensions."""
        admin = DbAdmin(pg_config)
        test_db = generate_test_db_name()

        try:
            admin.create(test_db)
            admin.install_extensions(["uuid-ossp"], test_db)

            # Verify extension is installed by connecting to the DB
            from pgsql_test.client import PgTestClient
            client_config = {**pg_config, "database": test_db}
            client = PgTestClient(client_config)
            client.connect()

            result = client.one(
                "SELECT 1 FROM pg_extension WHERE extname = 'uuid-ossp'"
            )
            assert result is not None

            client.close()
        finally:
            admin.drop(test_db)
            admin.close()


class TestGenerateTestDbName:
    """Tests for the generate_test_db_name function."""

    def test_generates_unique_names(self):
        """Test that generated names are unique."""
        names = [generate_test_db_name() for _ in range(100)]
        assert len(set(names)) == 100  # All unique

    def test_uses_prefix(self):
        """Test that generated names use the provided prefix."""
        name = generate_test_db_name("my_prefix_")
        assert name.startswith("my_prefix_")

    def test_default_prefix(self):
        """Test the default prefix."""
        name = generate_test_db_name()
        assert name.startswith("pgsql_test_")
