---
name: Python test runner
description: Environment convention for running and importing the project's Python tests.
---

Use the project's uv-managed environment to run Python tests with `uv run
pytest`. A test that imports a helper module stored under `tests/` should use
the package-qualified import path rather than assuming that directory is on the
top-level module path.

**Why:** The workspace does not expose pytest as a standalone shell command by
default, and direct root-module imports from `tests/` fail during pytest
collection even though the helper file exists.

**How to apply:** Install project test dependencies through the package manager,
run targeted or full checks with `uv run pytest`, and treat collection errors as
test-environment/import issues before interpreting product-test failures.