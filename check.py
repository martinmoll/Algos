"""Run every quality gate: `uv run python check.py`. Exits non-zero if any gate fails."""

import subprocess
import sys

GATES = [
    ["ruff", "check", "."],
    ["ruff", "format", "--check", "."],
    ["pyright"],
    ["pytest", "-q"],
]

failed = [g[0] for g in GATES if subprocess.run(g).returncode != 0]
if failed:
    sys.exit(f"FAILED: {', '.join(failed)}")
print("all checks passed")
