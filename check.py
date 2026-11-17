"""Run every quality gate: `uv run python check.py`. Exits non-zero if any gate fails.

The look-ahead gates (lint-imports, tests/leakage) are CI-blocking. Never remove, skip or
filter them to get a build green (CLAUDE.md)."""

import os
import subprocess
import sys

# The leakage gate runs with config addopts and PYTEST_ADDOPTS cleared, and with
# NORDPOWER_LEAKAGE_GATE=1, which makes tests/leakage/conftest.py fail the run if any test
# is skipped, xfailed or deselected. Zero collected tests also fails (pytest exit code 5).
LEAKAGE_ENV = {k: v for k, v in os.environ.items() if k != "PYTEST_ADDOPTS"} | {
    "NORDPOWER_LEAKAGE_GATE": "1"
}

GATES = [
    (["ruff", "check", "."], None),
    (["ruff", "format", "--check", "."], None),
    (["pyright"], None),
    (["lint-imports"], None),
    (["pytest", "-q", "-o", "addopts=", "tests/leakage"], LEAKAGE_ENV),
    (["pytest", "-q", "--ignore=tests/leakage"], None),
]

failed = [" ".join(cmd[:2]) for cmd, env in GATES if subprocess.run(cmd, env=env).returncode]
if failed:
    sys.exit(f"FAILED: {', '.join(failed)}")
print("all checks passed")
