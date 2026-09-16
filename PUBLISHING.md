# Publishing to PyPI

Package: https://pypi.org/project/pgsql-test/
Reference: https://packaging.python.org/en/latest/tutorials/packaging-projects/

The build backend is `poetry-core` (see `pyproject.toml`), but you do not need
Poetry installed to release. The standard `build` + `twine` tools work.

## One-time setup

```bash
python3 -m pip install --upgrade build twine
```

Create a PyPI API token at https://pypi.org/manage/account/#api-tokens and put it
in `~/.pypirc`:

```ini
[pypi]
  username = __token__
  password = pypi-...
```

## Release

1. Bump `version` in `pyproject.toml` (PyPI will reject a re-upload of an existing version).
2. Make sure CI is green on `main`.
3. Build and check:

   ```bash
   rm -rf dist
   python3 -m build
   twine check dist/*
   ```

4. Upload:

   ```bash
   twine upload dist/*
   ```

5. Tag and push:

   ```bash
   git tag v$(python3 -c "import tomllib;print(tomllib.load(open('pyproject.toml','rb'))['tool']['poetry']['version'])")
   git push --tags
   ```

To do a dry run against TestPyPI first, add a `[testpypi]` section to `~/.pypirc`
with a token from https://test.pypi.org and run
`twine upload --repository testpypi dist/*`.
