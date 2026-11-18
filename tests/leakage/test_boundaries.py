"""Boundary checks: model code reads data only through a KnowledgeView, and the look-ahead
suite always runs in the check command. CI-blocking; do not weaken (CLAUDE.md)."""

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
CONTRACT = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["tool"][
    "importlinter"
]["contracts"][0]
# Single source of truth: the packages guarded by the import contract in pyproject.toml.
GUARDED = [SRC / Path(*m.split(".")) for m in CONTRACT["source_modules"]]
# ponytail: line-regex policy check; aliased or multi-line calls can slip through. Replace
# with an AST visitor (or a sandboxed import test) if a leak ever gets past it.
DIRECT_DATA_ACCESS = re.compile(
    r"\bopen\(|\bio\.open|pl\.(read|scan)_|\bpd\.read_|pickle|shelve|\bglob\b|listdir|os\.walk"
    r"|\bPath\b|[\"']data[/\\]|\bStore\b|\._store\b|\._parts\b|importlib|__import__"
    r"|\bKnowledgeView\(|(?i:vault)|_issued"  # building a view or touching the vault (D-031)
)


def guarded_sources() -> list[Path]:
    return [p for d in GUARDED for p in sorted(d.rglob("*.py"))]


def test_import_contract_guards_the_model_packages():
    assert CONTRACT["type"] == "forbidden"
    assert "nordpower.models" in CONTRACT["source_modules"]
    assert {"nordpower.ingest", "nordpower.curate"} <= set(CONTRACT["forbidden_modules"])
    assert all(d.is_dir() for d in GUARDED), GUARDED


def test_model_code_never_reads_data_files_or_the_store_directly():
    assert guarded_sources()
    offences = [
        f"{p.relative_to(ROOT)}:{i}: {line.strip()}"
        for p in guarded_sources()
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
        if DIRECT_DATA_ACCESS.search(line)
    ]
    assert offences == []


def test_the_data_access_check_catches_typical_leaks():
    for leak in [
        'pl.read_parquet("data/curated/da_price/*.parquet")',
        'pl.scan_ipc("x.arrow")',
        "pl.read_ndjson(p)",
        "Store(root).as_of(far_future)",
        "view._store._parts('da_price')",
        'open("data/raw/x.json")',
        "io.open(p)",
        "pickle.load(f)",
        "glob.glob('*.parquet')",
        "os.listdir(d)",
        "Path.cwd()",
        'importlib.import_module("nordpower.curate")',
        '__import__("nordpower.curate")',
        "KnowledgeView(view._store, t, sealed_from=None)",
        "view.vault_start = far_future",
        "VaultToken('D-031', now)",
    ]:
        assert DIRECT_DATA_ACCESS.search(leak), leak
    assert not DIRECT_DATA_ACCESS.search("from nordpower.store import KnowledgeView")


def test_check_command_runs_import_contracts_and_the_leakage_suite_unfiltered():
    check = (ROOT / "check.py").read_text(encoding="utf-8")
    assert '["lint-imports"]' in check
    assert '"tests/leakage"' in check and '"addopts="' in check
    assert "NORDPOWER_LEAKAGE_GATE" in check and "PYTEST_ADDOPTS" in check
