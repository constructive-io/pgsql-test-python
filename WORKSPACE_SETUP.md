# pgpm Workspace Setup Guide

This guide walks you through setting up a pgpm workspace with Python tests using `pgsql-test`. Choose the configuration that best fits your needs.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Environment Setup](#environment-setup)
  - [Option A: Using pgpm Docker](#option-a-using-pgpm-docker)
  - [Option B: Using Existing PostgreSQL](#option-b-using-existing-postgresql)
- [Creating Your Workspace](#creating-your-workspace)
  - [Step 1: Initialize the Workspace](#step-1-initialize-the-workspace)
  - [Step 2: Create Your First Module](#step-2-create-your-first-module)
  - [Step 3: Add Database Objects](#step-3-add-database-objects)
  - [Step 4: Set Up Python Tests](#step-4-set-up-python-tests)
- [Project Structure Options](#project-structure-options)
  - [Option A: Tests at Workspace Root (Recommended)](#option-a-tests-at-workspace-root-recommended)
  - [Option B: Tests Inside Each Module](#option-b-tests-inside-each-module)
  - [Option C: Separate Test Project](#option-c-separate-test-project)
- [Running Tests](#running-tests)
- [CI/CD Setup](#cicd-setup)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

Before you begin, install the following:

### 1. Node.js and npm

pgpm is distributed via npm. Install Node.js 18+ from [nodejs.org](https://nodejs.org/) or using a version manager:

```bash
# Using nvm (recommended)
nvm install 20
nvm use 20

# Verify installation
node --version  # Should be v18+ 
npm --version
```

### 2. pgpm CLI

Install pgpm globally:

```bash
npm install -g pgpm

# Verify installation
pgpm --version
```

### 3. Python and Poetry

Install Python 3.10+ and Poetry for managing Python dependencies:

```bash
# Install Poetry (if not already installed)
curl -sSL https://install.python-poetry.org | python3 -

# Verify installation
python3 --version  # Should be 3.10+
poetry --version
```

### 4. PostgreSQL

You need a running PostgreSQL instance. See [Environment Setup](#environment-setup) for options.

---

## Environment Setup

Choose one of the following options to set up your PostgreSQL environment.

### Option A: Using pgpm Docker

The easiest way to get started. pgpm can manage a Docker container for you.

```bash
# Start PostgreSQL in Docker
pgpm docker start

# Set environment variables (add to your shell profile for persistence)
eval "$(pgpm env)"

# Verify connection
psql -c "SELECT version();"
```

**Stopping the container:**

```bash
pgpm docker stop
```

**Pros:**
- Zero configuration
- Isolated environment
- Easy cleanup

**Cons:**
- Requires Docker installed
- Slightly slower startup

### Option B: Using Existing PostgreSQL

If you already have PostgreSQL running locally or remotely, configure your environment variables:

```bash
# Add to ~/.bashrc, ~/.zshrc, or your shell profile
export PGHOST=localhost
export PGPORT=5432
export PGUSER=postgres
export PGPASSWORD=your_password

# Verify connection
psql -c "SELECT version();"
```

**For macOS with Homebrew:**

```bash
brew install postgresql@17
brew services start postgresql@17
export PGHOST=localhost
export PGPORT=5432
export PGUSER=$(whoami)
```

**For Ubuntu/Debian:**

```bash
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
sudo -u postgres createuser --superuser $USER
export PGHOST=localhost
export PGPORT=5432
export PGUSER=$USER
```

---

## Creating Your Workspace

### Step 1: Initialize the Workspace

Create a new pgpm workspace:

```bash
# Create and enter your project directory
mkdir my-project
cd my-project

# Initialize a pgpm workspace
pgpm init workspace
```

This creates a `my-workspace` directory (or the name you chose) with a `pgpm.json` configuration file.

```bash
cd my-workspace
```

### Step 2: Create Your First Module

Inside your workspace, create a module:

```bash
# From the workspace root
pgpm init
```

Follow the prompts to name your module (e.g., `my-module`). This creates:

```
packages/
  my-module/
    package.json           # Module metadata
    my-module.control      # PostgreSQL extension control file
    pgpm.plan              # Migration plan (like a Makefile for SQL)
    deploy/                # SQL files to apply
    revert/                # SQL files to undo changes
    verify/                # SQL files to verify changes
```

### Step 3: Add Database Objects

Let's add a simple schema and function to your module.

**Create the schema:**

```bash
# Create directories
mkdir -p packages/my-module/deploy/schemas
mkdir -p packages/my-module/revert/schemas
mkdir -p packages/my-module/verify/schemas
```

**packages/my-module/deploy/schemas/my_schema.sql:**

```sql
CREATE SCHEMA my_schema;
```

**packages/my-module/revert/schemas/my_schema.sql:**

```sql
DROP SCHEMA my_schema;
```

**packages/my-module/verify/schemas/my_schema.sql:**

```sql
SELECT 1 FROM information_schema.schemata WHERE schema_name = 'my_schema';
```

**Add a function:**

```bash
mkdir -p packages/my-module/deploy/functions
mkdir -p packages/my-module/revert/functions
mkdir -p packages/my-module/verify/functions
```

**packages/my-module/deploy/functions/hello_world.sql:**

```sql
CREATE FUNCTION my_schema.hello_world(name text DEFAULT 'World')
RETURNS text
LANGUAGE sql
AS $$
  SELECT 'Hello, ' || name || '!';
$$;
```

**packages/my-module/revert/functions/hello_world.sql:**

```sql
DROP FUNCTION my_schema.hello_world(text);
```

**packages/my-module/verify/functions/hello_world.sql:**

```sql
SELECT my_schema.hello_world('Test');
```

**Update the plan file:**

Edit `packages/my-module/pgpm.plan` to include your migrations:

```
%syntax-version=1.0.0
%project=my-module

schemas/my_schema
functions/hello_world [schemas/my_schema]
```

**Test the deployment:**

```bash
# Deploy to a test database
pgpm deploy --createdb --database test_db

# Verify it works
psql -d test_db -c "SELECT my_schema.hello_world('pgpm');"
# Output: Hello, pgpm!

# Clean up
psql -c "DROP DATABASE test_db;"
```

### Step 4: Set Up Python Tests

Now let's add Python tests using `pgsql-test`.

**Initialize Poetry project:**

```bash
# From workspace root
poetry init --name my-workspace-tests --python "^3.10" -n

# Add pgsql-test as a dependency
poetry add --group dev pgsql-test pytest
```

**Create test directory structure:**

```bash
mkdir -p tests
```

**tests/conftest.py:**

```python
import pytest
from pgsql_test import get_connections, seed


@pytest.fixture
def db():
    """
    Create an isolated test database with your pgpm module deployed.
    
    Each test gets a fresh database that is automatically cleaned up.
    """
    conn = get_connections(
        seed_adapters=[
            seed.pgpm(
                module_path="./packages/my-module",
                package="my-module"
            )
        ]
    )
    db = conn.db
    db.before_each()  # Start transaction for test isolation
    yield db
    db.after_each()   # Rollback changes
    conn.teardown()   # Drop test database
```

**tests/test_hello_world.py:**

```python
def test_hello_world_default(db):
    """Test hello_world with default parameter."""
    result = db.one("SELECT my_schema.hello_world() as greeting")
    assert result["greeting"] == "Hello, World!"


def test_hello_world_custom_name(db):
    """Test hello_world with custom name."""
    result = db.one("SELECT my_schema.hello_world('Python') as greeting")
    assert result["greeting"] == "Hello, Python!"


def test_hello_world_empty_string(db):
    """Test hello_world with empty string."""
    result = db.one("SELECT my_schema.hello_world('') as greeting")
    assert result["greeting"] == "Hello, !"
```

**Run the tests:**

```bash
poetry run pytest -v
```

---

## Project Structure Options

Choose the structure that best fits your workflow.

### Option A: Tests at Workspace Root (Recommended)

Best for: Most projects, especially when testing multiple modules together.

```
my-workspace/
├── pgpm.json
├── pyproject.toml          # Python project config
├── poetry.lock
├── packages/
│   ├── module-a/
│   │   ├── package.json
│   │   ├── pgpm.plan
│   │   ├── deploy/
│   │   ├── revert/
│   │   └── verify/
│   └── module-b/
│       └── ...
└── tests/
    ├── conftest.py         # Shared fixtures
    ├── test_module_a.py
    └── test_module_b.py
```

**Pros:**
- Single `pyproject.toml` for all tests
- Easy to test module interactions
- Simple CI/CD setup
- Matches TypeScript pgsql-test patterns

**Cons:**
- All tests in one place (may get large)

### Option B: Tests Inside Each Module

Best for: Large projects where modules are developed independently.

```
my-workspace/
├── pgpm.json
└── packages/
    ├── module-a/
    │   ├── package.json
    │   ├── pgpm.plan
    │   ├── deploy/
    │   ├── revert/
    │   ├── verify/
    │   ├── pyproject.toml  # Module-specific Python config
    │   └── tests/
    │       └── test_functions.py
    └── module-b/
        └── ...
```

**Pros:**
- Tests co-located with module code
- Each module is self-contained
- Easy to run tests for a single module

**Cons:**
- Multiple `pyproject.toml` files to maintain
- Harder to test cross-module interactions

### Option C: Separate Test Project

Best for: When Python tests are maintained by a different team or need complete isolation.

```
my-project/
├── my-workspace/           # pgpm workspace (SQL only)
│   ├── pgpm.json
│   └── packages/
│       └── my-module/
└── python-tests/           # Separate Python project
    ├── pyproject.toml
    └── tests/
        └── test_my_module.py  # References ../my-workspace/packages/my-module
```

**conftest.py for Option C:**

```python
@pytest.fixture
def db():
    conn = get_connections(
        seed_adapters=[
            seed.pgpm(
                module_path="../my-workspace/packages/my-module",
                package="my-module"
            )
        ]
    )
    # ... rest of fixture
```

**Pros:**
- Complete separation of concerns
- Python project has its own dependencies
- Good for polyglot teams

**Cons:**
- Path management can be tricky
- Need to keep projects in sync

---

## Running Tests

### Basic Test Run

```bash
# Run all tests
poetry run pytest

# Run with verbose output
poetry run pytest -v

# Run specific test file
poetry run pytest tests/test_hello_world.py

# Run specific test
poetry run pytest tests/test_hello_world.py::test_hello_world_default
```

### With Coverage

```bash
# Install coverage
poetry add --group dev pytest-cov

# Run with coverage
poetry run pytest --cov=tests --cov-report=html
```

### Watch Mode

```bash
# Install pytest-watch
poetry add --group dev pytest-watch

# Run in watch mode
poetry run ptw
```

---

## CI/CD Setup

Here's a complete GitHub Actions workflow for testing your pgpm workspace with Python:

**.github/workflows/test.yml:**

```yaml
name: Test

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

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

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: "20"

      - name: Install pgpm
        run: npm install -g pgpm

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

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

---

## Troubleshooting

### "Connection refused" error

Make sure PostgreSQL is running and your environment variables are set:

```bash
# Check if PostgreSQL is running
pg_isready

# Verify environment variables
echo $PGHOST $PGPORT $PGUSER
```

### "pgpm: command not found"

Ensure pgpm is installed globally and in your PATH:

```bash
npm install -g pgpm
which pgpm
```

### "Module not found" in tests

Check that the `module_path` in `seed.pgpm()` is correct relative to where you run pytest:

```python
# If running from workspace root:
seed.pgpm(module_path="./packages/my-module", package="my-module")

# If running from tests/ directory:
seed.pgpm(module_path="../packages/my-module", package="my-module")
```

### Interactive prompt during tests

Always specify the `package` parameter to avoid interactive prompts:

```python
# Wrong - may prompt for package selection
seed.pgpm(module_path="./packages/my-module")

# Correct - explicitly specifies package
seed.pgpm(module_path="./packages/my-module", package="my-module")
```

### Tests interfering with each other

Make sure you're using `before_each()` and `after_each()` for test isolation:

```python
@pytest.fixture
def db():
    conn = get_connections(...)
    db = conn.db
    db.before_each()  # Don't forget this!
    yield db
    db.after_each()   # And this!
    conn.teardown()
```

---

## Next Steps

- Read the [pgsql-test README](https://github.com/constructive-io/pgsql-test-python/blob/main/README.md) for API documentation
- Explore [pgpm documentation](https://pgpm.io) for advanced features
