# pysql-test

PostgreSQL testing framework for Python - instant, isolated databases with automatic transaction rollback.

## Features

- **Instant isolated databases**: Each test gets a fresh database with a unique UUID name
- **Transaction rollback**: Changes are automatically rolled back after each test
- **Composable seeding**: Seed your database with SQL files, custom functions, or combine multiple strategies
- **RLS testing support**: Easy context switching for testing Row Level Security policies
- **Clean API**: Simple, intuitive interface inspired by the Node.js pgsql-test library

## Installation

```bash
# Using Poetry (recommended)
poetry add pysql-test

# Using pip
pip install pysql-test
```

## Quick Start

```python
import pytest
from pysql_test import get_connections, seed

# Basic usage
def test_basic_query():
    conn = get_connections()
    result = conn.db.query('SELECT 1 as value')
    assert result.rows[0]['value'] == 1
    conn.teardown()

# With pytest fixture
@pytest.fixture
def db():
    conn = get_connections()
    yield conn.db
    conn.teardown()

def test_with_fixture(db):
    result = db.query('SELECT 1 as value')
    assert result.rows[0]['value'] == 1

# With SQL file seeding
@pytest.fixture
def seeded_db():
    conn = get_connections(
        seed_adapters=[seed.sqlfile(['schema.sql', 'fixtures.sql'])]
    )
    yield conn.db
    conn.teardown()

def test_with_seeding(seeded_db):
    users = seeded_db.many('SELECT * FROM users')
    assert len(users) > 0
```

## Transaction Isolation

Use `before_each()` and `after_each()` for per-test isolation:

```python
@pytest.fixture
def db():
    conn = get_connections(
        seed_adapters=[seed.sqlfile(['schema.sql'])]
    )
    db = conn.db
    db.before_each()  # Begin transaction + savepoint
    yield db
    db.after_each()   # Rollback to savepoint
    conn.teardown()

def test_insert_user(db):
    # This insert will be rolled back after the test
    db.execute("INSERT INTO users (name) VALUES ('Test User')")
    result = db.one("SELECT * FROM users WHERE name = 'Test User'")
    assert result['name'] == 'Test User'

def test_user_count(db):
    # Previous test's insert is not visible here
    result = db.one("SELECT COUNT(*) as count FROM users")
    assert result['count'] == 0  # Only seeded data
```

## RLS Testing

Test Row Level Security policies by switching contexts:

```python
def test_rls_policy(db):
    db.before_each()
    
    # Set the user context
    db.set_context({'app.user_id': '123'})
    
    # Now queries will be filtered by RLS policies
    result = db.many('SELECT * FROM user_data')
    
    db.after_each()
```

## Seeding Strategies

### SQL Files

```python
seed.sqlfile(['schema.sql', 'fixtures.sql'])
```

### Custom Functions

```python
seed.fn(lambda ctx: ctx['pg'].execute(
    "INSERT INTO users (name) VALUES (%s)", ('Alice',)
))
```

### Composed Seeding

```python
seed.compose([
    seed.sqlfile(['schema.sql']),
    seed.fn(lambda ctx: ctx['pg'].execute("INSERT INTO ...")),
])
```

## Configuration

Configure via environment variables:

```bash
export PGHOST=localhost
export PGPORT=5432
export PGUSER=postgres
export PGPASSWORD=your_password
```

Or pass configuration directly:

```python
conn = get_connections(
    pg_config={
        'host': 'localhost',
        'port': 5432,
        'user': 'postgres',
        'password': 'your_password',
    }
)
```

## API Reference

### `get_connections(pg_config?, connection_options?, seed_adapters?)`

Creates a new isolated test database and returns connection objects.

Returns a `ConnectionResult` with:
- `pg`: PgTestClient connected as superuser
- `db`: PgTestClient for testing (same as pg for now)
- `admin`: DbAdmin for database management
- `manager`: PgTestConnector managing connections
- `teardown()`: Function to clean up

### `PgTestClient`

- `query(sql, params?)`: Execute SQL and return QueryResult
- `one(sql, params?)`: Return exactly one row
- `one_or_none(sql, params?)`: Return one row or None
- `many(sql, params?)`: Return multiple rows
- `many_or_none(sql, params?)`: Return rows (may be empty)
- `execute(sql, params?)`: Execute and return affected row count
- `before_each()`: Start test isolation (transaction + savepoint)
- `after_each()`: End test isolation (rollback)
- `set_context(dict)`: Set session variables for RLS testing

## Development

```bash
# Install dependencies
poetry install

# Run tests
poetry run pytest

# Run linting
poetry run ruff check .

# Run type checking
poetry run mypy src
```

## License

MIT
