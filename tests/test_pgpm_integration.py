"""
pgpm integration tests for pysql-test.

These tests demonstrate using seed.pgpm() to run pgpm migrations
as part of test database seeding.

Requires:
- pgpm CLI installed: npm install -g pgpm
- @pgpm/faker installed in the test fixture: pgpm install @pgpm/faker
"""

from pathlib import Path

import pytest

from pysql_test import get_connections, seed

# Path to the pre-scaffolded pgpm workspace fixture
FIXTURE_PATH = Path(__file__).parent / "fixtures" / "pgpm-workspace" / "packages" / "test-module"
PACKAGE_NAME = "test-module"


@pytest.fixture
def pgpm_db():
    """
    Create an isolated test database with pgpm migrations applied.

    This fixture uses seed.pgpm() to run pgpm deploy, which applies
    all migrations from the test-module fixture.
    """
    conn = get_connections(
        seed_adapters=[
            seed.pgpm(module_path=str(FIXTURE_PATH), package=PACKAGE_NAME)
        ]
    )
    db = conn.db
    db.before_each()
    yield db
    db.after_each()
    conn.teardown()


def test_pgpm_creates_schema(pgpm_db):
    """Test that pgpm deploy creates the test_app schema."""
    result = pgpm_db.one("""
        SELECT schema_name
        FROM information_schema.schemata
        WHERE schema_name = 'test_app'
    """)
    assert result["schema_name"] == "test_app"


def test_pgpm_faker_available(pgpm_db):
    """
    Test that @pgpm/faker is available after pgpm deploy.

    This test verifies that pgpm install @pgpm/faker was run
    and the faker schema/functions are available.
    """
    # Check if faker schema exists (installed via pgpm install @pgpm/faker)
    result = pgpm_db.one_or_none("""
        SELECT schema_name
        FROM information_schema.schemata
        WHERE schema_name = 'faker'
    """)

    if result is None:
        pytest.skip("@pgpm/faker not installed - run: cd tests/fixtures/pgpm-workspace/packages/test-module && pgpm install @pgpm/faker")

    assert result["schema_name"] == "faker"


def test_pgpm_faker_city_function(pgpm_db):
    """
    Test that faker.city() function works.

    This demonstrates the full pgpm integration flow:
    1. pysql-test creates isolated database
    2. seed.pgpm() runs pgpm deploy
    3. pgpm deploys test-module + @pgpm/faker dependency
    4. Test can use faker functions
    """
    # Check if faker schema exists first
    schema_exists = pgpm_db.one_or_none("""
        SELECT schema_name
        FROM information_schema.schemata
        WHERE schema_name = 'faker'
    """)

    if schema_exists is None:
        pytest.skip("@pgpm/faker not installed - run: cd tests/fixtures/pgpm-workspace/packages/test-module && pgpm install @pgpm/faker")

    # Test faker.city() function with Michigan state code
    result = pgpm_db.one("SELECT faker.city('MI') as city")
    assert result["city"] is not None
    assert isinstance(result["city"], str)
    assert len(result["city"]) > 0
