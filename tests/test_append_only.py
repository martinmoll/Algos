"""Policy check: the modules that write raw snapshots and curated vintages can only create
new files (open mode "x"), never overwrite, rename or delete."""

import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "nordpower"
# ponytail: regex policy check; write_parquet must target an open handle named `f`
WRITERS = [SRC / "store.py", SRC / "curate.py", *sorted((SRC / "ingest").glob("*.py"))]
FORBIDDEN = re.compile(
    r"\.unlink\(|\brmtree\b|os\.remove|os\.replace|\.rename\((?!\{)|write_text\(|write_bytes\("
    r"|open\([^)]*[\"'][wa]b?\+?[\"']|write_parquet\(\s*[^f)]"
)
# The one file that is meant to grow: the vault log gains a line per opening (D-031).
VAULT_LOG_APPEND = re.compile(r"open\(self\.root / \"vault_log\.jsonl\", \"a\"")


def test_raw_and_curated_writers_never_overwrite_or_delete():
    offences = [
        f"{p.name}:{i}: {line.strip()}"
        for p in WRITERS
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
        if FORBIDDEN.search(line) and not VAULT_LOG_APPEND.search(line)
    ]
    assert offences == []


def test_the_check_catches_an_overwrite():
    assert FORBIDDEN.search('path.write_text("x")')
    assert FORBIDDEN.search('open(path, "w")')
    assert FORBIDDEN.search("rows.write_parquet(d / 'x.parquet')")
    assert not FORBIDDEN.search('open(path, "xb")')
    assert not FORBIDDEN.search("rows.write_parquet(f)")
    assert not FORBIDDEN.search("datetime.fromisoformat(s).replace(tzinfo=UTC)")
    assert not FORBIDDEN.search('df.rename({"a": "b"})')
    assert FORBIDDEN.search("path.rename(target)")
    assert FORBIDDEN.search('open(d / "part.parquet", "a")')
    assert not VAULT_LOG_APPEND.search('open(d / "part.parquet", "a")')
