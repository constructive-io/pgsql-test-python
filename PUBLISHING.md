# Publishing to PyPI

This guide explains how to publish `pgsql-test` to PyPI using Poetry.

## Prerequisites

1. **PyPI Account**: Create an account at https://pypi.org/account/register/
2. **API Token**: Generate an API token at https://pypi.org/manage/account/token/
3. **Poetry**: Already installed if you've been developing locally

## One-Time Setup

Configure Poetry with your PyPI token:

```bash
poetry config pypi-token.pypi <your-token>
```

Alternatively, you can use environment variables:

```bash
export POETRY_PYPI_TOKEN_PYPI=<your-token>
```

## Publishing Steps

### 1. Update Version

Update the version in `pyproject.toml`:

```toml
[tool.poetry]
name = "pgsql-test"
version = "0.1.1"  # Bump this
```

Or use Poetry's version command:

```bash
# Bump patch version (0.1.0 -> 0.1.1)
poetry version patch

# Bump minor version (0.1.0 -> 0.2.0)
poetry version minor

# Bump major version (0.1.0 -> 1.0.0)
poetry version major

# Set specific version
poetry version 1.0.0
```

### 2. Run Tests

Ensure all tests pass before publishing:

```bash
poetry run pytest -v
poetry run ruff check .
poetry run mypy src --ignore-missing-imports
```

### 3. Build the Package

```bash
poetry build
```

This creates distribution files in the `dist/` directory:
- `pgsql_test-0.1.1.tar.gz` (source distribution)
- `pgsql_test-0.1.1-py3-none-any.whl` (wheel)

### 4. Publish to PyPI

```bash
poetry publish
```

Or build and publish in one command:

```bash
poetry publish --build
```

## Testing with TestPyPI

Before publishing to the real PyPI, you can test with TestPyPI:

### 1. Create TestPyPI Account

Register at https://test.pypi.org/account/register/

### 2. Configure TestPyPI

```bash
poetry config repositories.testpypi https://test.pypi.org/legacy/
poetry config pypi-token.testpypi <your-testpypi-token>
```

### 3. Publish to TestPyPI

```bash
poetry publish --build -r testpypi
```

### 4. Test Installation

```bash
pip install --index-url https://test.pypi.org/simple/ pgsql-test
```

## GitHub Actions Automation

To automate publishing on releases, add this workflow to `.github/workflows/publish.yml`:

```yaml
name: Publish to PyPI

on:
  release:
    types: [published]

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install Poetry
        uses: snok/install-poetry@v1

      - name: Build and publish
        env:
          POETRY_PYPI_TOKEN_PYPI: ${{ secrets.PYPI_TOKEN }}
        run: poetry publish --build
```

Then add your PyPI token as a repository secret named `PYPI_TOKEN`.

## Versioning Guidelines

Follow [Semantic Versioning](https://semver.org/):

- **MAJOR** (1.0.0): Breaking changes to the public API
- **MINOR** (0.1.0): New features, backwards compatible
- **PATCH** (0.0.1): Bug fixes, backwards compatible

For pre-release versions:
- `0.1.0a1` - Alpha release
- `0.1.0b1` - Beta release
- `0.1.0rc1` - Release candidate

## Checklist Before Publishing

- [ ] All tests pass locally
- [ ] Version number updated in `pyproject.toml`
- [ ] CHANGELOG updated (if you have one)
- [ ] README is up to date
- [ ] Commit and push all changes
- [ ] Create a git tag for the release

```bash
git tag v0.1.1
git push origin v0.1.1
```

## Troubleshooting

### "File already exists" Error

PyPI doesn't allow overwriting existing versions. You must bump the version number.

### Authentication Failed

Verify your token is correct:

```bash
poetry config pypi-token.pypi --unset
poetry config pypi-token.pypi <new-token>
```

### Package Name Conflict

If `pgsql-test` is taken, you may need to use a different name like `pgsql-test-py` or `constructive-pgsql-test`.
