"""
Pets example demonstrating per-test rollback with before_each/after_each.

This example shows how pgsql-test provides complete test isolation through
automatic transaction rollback. Each test starts with a clean slate,
regardless of what previous tests inserted.

Key concept: before_each() creates a savepoint, after_each() rolls back to it.
"""

import pytest

from pysql_test import get_connections, seed


@pytest.fixture
def pets_db():
    """
    Create an isolated test database with a simple pets schema.

    The before_each()/after_each() pattern ensures each test:
    1. Starts with only the seeded data (empty pets table)
    2. Can insert/modify data freely during the test
    3. Has all changes rolled back automatically after the test
    """
    conn = get_connections(
        seed_adapters=[
            seed.fn(lambda ctx: ctx["pg"].query("""
                CREATE TABLE pets (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    species TEXT NOT NULL,
                    age INTEGER
                )
            """))
        ]
    )
    db = conn.db
    db.before_each()  # Begin transaction + create savepoint
    yield db
    db.after_each()   # Rollback to savepoint (undo all changes)
    conn.teardown()


# =============================================================================
# Test 1: Insert a pet and verify it exists
# =============================================================================
def test_insert_pet(pets_db):
    """Insert a pet and verify it exists in the database."""
    pets_db.execute(
        "INSERT INTO pets (name, species, age) VALUES (%s, %s, %s)",
        ("Buddy", "dog", 3),
    )

    pet = pets_db.one("SELECT * FROM pets WHERE name = %s", ("Buddy",))

    assert pet["name"] == "Buddy"
    assert pet["species"] == "dog"
    assert pet["age"] == 3


# =============================================================================
# Test 2: Verify the table is empty (previous insert was rolled back!)
# =============================================================================
def test_table_empty_after_rollback(pets_db):
    """
    Verify that the previous test's insert was rolled back.

    Even though test_insert_pet inserted 'Buddy', that change was
    automatically rolled back by after_each(). This test starts fresh.
    """
    count = pets_db.one("SELECT COUNT(*) as count FROM pets")

    # Table should be empty - Buddy was rolled back!
    assert count["count"] == 0


# =============================================================================
# Test 3: Insert multiple pets
# =============================================================================
def test_insert_multiple_pets(pets_db):
    """Insert multiple pets and verify the count."""
    pets_db.execute(
        "INSERT INTO pets (name, species, age) VALUES (%s, %s, %s)",
        ("Whiskers", "cat", 5),
    )
    pets_db.execute(
        "INSERT INTO pets (name, species, age) VALUES (%s, %s, %s)",
        ("Goldie", "fish", 1),
    )
    pets_db.execute(
        "INSERT INTO pets (name, species, age) VALUES (%s, %s, %s)",
        ("Rex", "dog", 7),
    )

    count = pets_db.one("SELECT COUNT(*) as count FROM pets")
    assert count["count"] == 3

    # Verify we can query specific pets
    cats = pets_db.many("SELECT * FROM pets WHERE species = %s", ("cat",))
    assert len(cats) == 1
    assert cats[0]["name"] == "Whiskers"


# =============================================================================
# Test 4: Verify table is empty again (all 3 pets were rolled back!)
# =============================================================================
def test_table_empty_again(pets_db):
    """
    Verify that ALL previous inserts were rolled back.

    The 3 pets from test_insert_multiple_pets are gone.
    Each test truly starts with a clean slate.
    """
    count = pets_db.one("SELECT COUNT(*) as count FROM pets")

    # Table should be empty - all pets were rolled back!
    assert count["count"] == 0


# =============================================================================
# Test 5: Demonstrate update rollback
# =============================================================================
def test_update_rollback(pets_db):
    """
    Demonstrate that updates are also rolled back.

    Insert a pet, update it, verify the update - all rolled back after.
    """
    # Insert
    pets_db.execute(
        "INSERT INTO pets (name, species, age) VALUES (%s, %s, %s)",
        ("Max", "dog", 2),
    )

    # Update
    pets_db.execute(
        "UPDATE pets SET age = %s WHERE name = %s",
        (3, "Max"),
    )

    # Verify update worked within this test
    pet = pets_db.one("SELECT * FROM pets WHERE name = %s", ("Max",))
    assert pet["age"] == 3  # Updated age


# =============================================================================
# Test 6: Final verification - still empty!
# =============================================================================
def test_final_empty_check(pets_db):
    """
    Final check: table is still empty after all previous tests.

    This proves that before_each()/after_each() provides complete
    isolation for every single test, no matter what operations were performed.
    """
    count = pets_db.one("SELECT COUNT(*) as count FROM pets")
    assert count["count"] == 0

    # We can safely insert knowing it won't affect other tests
    pets_db.execute(
        "INSERT INTO pets (name, species, age) VALUES (%s, %s, %s)",
        ("Luna", "cat", 4),
    )

    # Verify our insert worked
    pet = pets_db.one("SELECT * FROM pets WHERE name = %s", ("Luna",))
    assert pet["name"] == "Luna"

    # Luna will be rolled back after this test completes
