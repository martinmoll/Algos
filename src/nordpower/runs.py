"""Run records: provenance, status, sealing and the run registry (plan 05 §6, D-037).

A run directory is written under a temporary name, hashed into `manifest.json`, made
read-only and only then renamed into place, so a run id that exists is a finished, sealed
record. The registry `registry.jsonl` is append-only: a `started` line before any work and a
`finished` or `failed` line after, so crashed and failed runs are still counted as trials.
"""

import hashlib
import json
import os
import platform
import stat
import subprocess
import tomllib
from importlib import metadata
from pathlib import Path

from nordpower.store import REPO

STATUS_CONFIG = REPO / "configs" / "run_status.toml"
REGISTRY = "registry.jsonl"
MANIFEST = "manifest.json"
# Most severe first: a run gets the first status whose condition holds.
STATUSES = ("invalid", "suspect", "exploratory", "ok")
PACKAGES = ("nordpower", "polars", "tzdata")


def git_state() -> dict:
    """HEAD SHA and whether the working tree differs from it (untracked files count)."""

    def git(*args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=REPO, capture_output=True, text=True, check=True
        ).stdout.strip()

    try:
        return {"sha": git("rev-parse", "HEAD"), "dirty": bool(git("status", "--porcelain"))}
    except (OSError, subprocess.CalledProcessError):
        return {"sha": "unknown", "dirty": True}  # not reproducible, so treated as dirty


def package_versions() -> dict:
    versions = {"python": platform.python_version()}
    for name in PACKAGES:
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            versions[name] = "not installed"
    return versions


def load_status_rules(path: Path = STATUS_CONFIG) -> dict:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _rmaes(metrics: dict) -> list[tuple[str, float]]:
    """(label, rMAE) for every zone total and every zone era that has one."""
    out = []
    for zone, m in metrics.items():
        if m.get("rmae") is not None:
            out.append((zone, m["rmae"]))
        for era, e in m.get("eras", {}).items():
            if e.get("rmae") is not None:
                out.append((f"{zone} {era}", e["rmae"]))
    return out


def run_status(metrics: dict, checks: list[dict], dirty: bool, rules: dict) -> dict:
    """Status and the reasons for it. invalid > suspect > exploratory > ok."""
    floor = rules["suspect"]["rmae_floor"]
    reasons = {
        "invalid": [f"look-ahead check failed: {c['name']}" for c in checks if not c["passed"]],
        "suspect": [
            f"rMAE {r:.3f} < {floor} ({label}): too good, review before promotion"
            for label, r in _rmaes(metrics)
            if r < floor
        ],
        "exploratory": ["git working tree is dirty or unknown"] if dirty else [],
    }
    status = next((s for s in STATUSES[:-1] if reasons[s]), "ok")
    return {"status": status, "reasons": [r for s in STATUSES[:-1] for r in reasons[s]]}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def seal(tmp_dir: Path, final_dir: Path) -> Path:
    """Hash every file into the manifest, make the directory read-only, move it into place."""
    files = sorted(p for p in tmp_dir.iterdir() if p.is_file())
    manifest = {p.name: _sha256(p) for p in files}
    (tmp_dir / MANIFEST).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    read_only = stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH
    for p in tmp_dir.iterdir():
        p.chmod(read_only)
    tmp_dir.chmod(read_only | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    if final_dir.exists():
        raise FileExistsError(f"run {final_dir.name} already exists; runs are never overwritten")
    os.rename(tmp_dir, final_dir)
    return final_dir


def verify(run_dir: Path) -> list[str]:
    """Problems with a sealed run: changed, missing or extra files. Empty means intact."""
    manifest = json.loads((run_dir / MANIFEST).read_text(encoding="utf-8"))
    present = {p.name for p in run_dir.iterdir() if p.is_file() and p.name != MANIFEST}
    problems = [f"missing: {n}" for n in sorted(set(manifest) - present)]
    problems += [f"not in manifest: {n}" for n in sorted(present - set(manifest))]
    problems += [
        f"changed: {n}"
        for n in sorted(set(manifest) & present)
        if _sha256(run_dir / n) != manifest[n]
    ]
    return problems


def register(runs_root: Path, event: dict) -> None:
    """Append one event to the registry. Never rewritten."""
    runs_root.mkdir(parents=True, exist_ok=True)
    with open(runs_root / REGISTRY, "a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")


def registry(runs_root: Path) -> list[dict]:
    """One entry per run, in start order: `state` is the run status, `failed`, or
    `abandoned` (started, never finished)."""
    path = runs_root / REGISTRY
    if not path.exists():
        return []
    runs: dict[str, dict] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        e = json.loads(line)
        if e["event"] == "started":
            runs[e["run_id"]] = {k: v for k, v in e.items() if k != "event"} | {
                "state": "abandoned"
            }
        elif e["run_id"] in runs:
            run = runs[e["run_id"]]
            run["finished_at"] = e["at"]
            run["state"] = e["status"] if e["event"] == "finished" else "failed"
            if "error" in e:
                run["error"] = e["error"]
    return list(runs.values())


def trial_counts(runs: list[dict]) -> dict[str, int]:
    """Trials per strategy family: every started run counts, whatever its outcome."""
    counts: dict[str, int] = {}
    for run in runs:
        counts[run["family"]] = counts.get(run["family"], 0) + 1
    return counts
