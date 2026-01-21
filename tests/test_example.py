"""
Simple example test demonstrating pysql-test usage.

This is a minimal example showing how to use the testing framework
for PostgreSQL integration tests with automatic database isolation.
"""

import pytest

from pysql_test import get_connections, seed


@pytest.fixture
def db():
    """
    Create an isolated test database with sample schema.
    
    Each test gets a fresh database that is automatically
    cleaned up after the test completes.
    """
    conn = get_connections(
        seed_adapters=[
            seed.fn(lambda ctx: ctx["pg"].query("""
                CREATE TABLE users (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    email TEXT UNIQUE
                )
            """))
        ]
    )
    db = conn.db
    db.before_each()
    yield db
    db.after_each()
    conn.teardown()


def test_insert_and_query_user(db):
    """Test inserting and querying a user."""
    # Insert a user
    db.execute(
        "INSERT INTO users (name, email) VALUES (%s, %s)",
        ("Alice", "alice@example.com"),
    )

    # Query the user
    user = db.one("SELECT * FROM users WHERE name = %s", ("Alice",))

    assert user["name"] == "Alice"
    assert user["email"] == "alice@example.com"


def test_transaction_isolation(db):
    """Test that changes are rolled back between tests."""
    # This insert will be rolled back after the test
    db.execute(
        "INSERT INTO users (name, email) VALUES (%s, %s)",
        ("Bob", "bob@example.com"),
    )

    # Verify the user exists within this test
    count = db.one("SELECT COUNT(*) as count FROM users")
    assert count["count"] == 1


def test_empty_table_after_rollback(db):
    """Verify previous test's data was rolled back."""
    # Table should be empty because previous test's insert was rolled back
    count = db.one("SELECT COUNT(*) as count FROM users")
    assert count["count"] == 0
