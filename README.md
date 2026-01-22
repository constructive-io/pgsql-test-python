# pgsql-test

<p align="center" width="100%">
  <img height="250" src="https://raw.githubusercontent.com/constructive-io/constructive/refs/heads/main/assets/outline-logo.svg" />
</p>

<p align="center" width="100%">
  <a href="https://github.com/constructive-io/pgsql-test-python/actions/workflows/test.yml">
    <img height="20" src="https://github.com/constructive-io/pgsql-test-python/actions/workflows/test.yml/badge.svg" />
  </a>
  <a href="https://github.com/constructive-io/pgsql-test-python/blob/main/LICENSE">
    <img height="20" src="https://img.shields.io/badge/license-MIT-blue.svg"/>
  </a>
  <a href="https://www.npmjs.com/package/pgsql-test">
    <img height="20" src="https://img.shields.io/npm/v/pgsql-test.svg"/>
  </a>
</p>

The Python counterpart to [`pgsql-test`](https://www.npmjs.com/package/pgsql-test) on npm. Instant, isolated PostgreSQL databases for each test — with automatic transaction rollbacks, context switching, and clean seeding.

## Features

* **Instant test DBs** — each one seeded, isolated, and UUID-named
* **Per-test rollback** — every test runs in its own transaction with savepoint-based rollback via `before_each()`/`after_each()`
* **RLS-friendly** — test with role-based auth via `set_context()`
* **pgpm integration** — run database migrations using [pgpm](https://github.com/pgpm-io/pgpm) (PostgreSQL Package Manager)
* **Flexible seeding** — run `.sql` files, programmatic seeds, pgpm modules, or combine multiple strategies
* **Auto teardown** — no residue, no reboots, just clean exits

## Installation

```bash
# Using Poetry (recommended)
poetry add pgsql-test

# Using pip
pip install pgsql-test
```

## Quick Start

```python
import pytest
from pgsql_test import get_connections, seed

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
```

## pgpm Integration

The primary use case for pgsql-test is testing PostgreSQL modules managed by [pgpm](https://github.com/pgpm-io/pgpm). The `seed.pgpm()` adapter runs `pgpm deploy` to apply your migrations to an isolated test database.

### Prerequisites

Install pgpm globally:

```bash
npm install -g pgpm
```

### Basic pgpm Usage

```python
import pytest
from pgsql_test import get_connections, seed

@pytest.fixture
def db():
    conn = get_connections(
        seed_adapters=[
            seed.pgpm(
                module_path="./packages/my-module",
                package="my-module"
            )
        ]
    )
    db = conn.db
    db.before_each()
    yield db
    db.after_each()
    conn.teardown()

def test_my_function(db):
    # Your pgpm module's functions are now available
    result = db.one("SELECT my_schema.my_function() as result")
    assert result['result'] == expected_value
```

### pgpm with Dependencies

If your module depends on other pgpm packages (like `@pgpm/faker`), install them first:

```bash
cd packages/my-module
pgpm install @pgpm/faker
```

Then test:

```python
def test_faker_integration(db):
    # @pgpm/faker functions are available after pgpm deploy
    result = db.one("SELECT faker.city('MI') as city")
    assert result['city'] is not None
```

### pgpm Workspace Structure

A typical pgpm workspace for testing looks like:

```
my-workspace/
  pgpm.json                    # Workspace config
  packages/
    my-module/
      package.json             # Module metadata
      my-module.control        # PostgreSQL extension control
      pgpm.plan                # Migration plan
      deploy/
        schemas/
          my_schema.sql        # CREATE SCHEMA my_schema;
        functions/
          my_function.sql      # CREATE FUNCTION ...
      revert/
        schemas/
          my_schema.sql        # DROP SCHEMA my_schema;
      verify/
        schemas/
          my_schema.sql        # SELECT 1 FROM ...
```

### seed.pgpm() Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `module_path` | `str` | Path to the pgpm module directory |
| `package` | `str` | Package name to deploy (required to avoid interactive prompts) |
| `deploy_args` | `list[str]` | Additional arguments to pass to `pgpm deploy` |
| `cache` | `bool` | Enable caching (not yet implemented) |

## SQL File Seeding

For simpler use cases without pgpm, seed directly from SQL files:

```python
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

## Per-Test Rollback

The `before_each()` and `after_each()` methods provide automatic transaction rollback for each test. This ensures complete isolation between tests - any changes made during a test are automatically rolled back, so each test starts with a clean slate.

### How It Works

1. `before_each()` begins a transaction and creates a savepoint
2. Your test runs and makes changes to the database
3. `after_each()` rolls back to the savepoint, undoing all changes
4. The next test starts fresh with only the seeded data

### Basic Pattern

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

### Why This Matters

Without per-test rollback, tests can interfere with each other:
- Test A inserts a user
- Test B expects 0 users but finds 1
- Tests become order-dependent and flaky

With `before_each()`/`after_each()`, each test is completely isolated, making your test suite reliable and deterministic.

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

### pgpm Modules

```python
seed.pgpm(module_path="./packages/my-module", package="my-module")
```

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
    seed.pgpm(module_path="./packages/my-module", package="my-module"),
    seed.sqlfile(['fixtures.sql']),
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

## GitHub Actions Example

Here's a complete CI workflow for testing pgpm modules:

```yaml
name: Test

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:17
        env:
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: password
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432

    env:
      PGHOST: localhost
      PGPORT: 5432
      PGUSER: postgres
      PGPASSWORD: password

    steps:
      - uses: actions/checkout@v4
      
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      
      - name: Install pgpm
        run: npm install -g pgpm
      
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      
      - name: Install Poetry
        uses: snok/install-poetry@v1
      
      - name: Install dependencies
        run: poetry install
      
      - name: Bootstrap pgpm roles
        run: |
          pgpm admin-users bootstrap --yes
          pgpm admin-users add --test --yes
      
      - name: Run tests
        run: poetry run pytest -v
```

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

## Related Projects

- [pgsql-test](https://github.com/launchql/pgsql-test) - The original TypeScript/Node.js version
- [pgpm](https://github.com/pgpm-io/pgpm) - PostgreSQL Package Manager

## License

MIT
