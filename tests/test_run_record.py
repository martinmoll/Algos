"""Run records (#9, D-037): provenance, exploratory status, sealing, and the registry."""

import json
import os
import stat
from datetime import UTC, date, datetime, timedelta

import pytest

from nordpower import cli, runs
from nordpower.backtest import run_backtest
from nordpower.models.naive import Naive
from nordpower.store import KnowledgeView, Store
from nordpower.timeutil import delivery_span
from tests.leakage.conftest import price_rows

FIRST, LAST = date(2024, 3, 11), date(2024, 3, 17)


@pytest.fixture
def store(tmp_path) -> Store:
    start, end = delivery_span(FIRST - timedelta(days=7), LAST)
    hours = [start + timedelta(hours=i) for i in range((end - start) // timedelta(hours=1))]
    prices = {(z, t): float(i % 97) for z in ["DK1"] for i, t in enumerate(hours)}
    s = Store(tmp_path / "store")
    s.append("da_price", price_rows(prices, datetime(2024, 4, 1, tzinfo=UTC)))
    return s


@pytest.fixture
def clean(monkeypatch):
    monkeypatch.setattr(runs, "git_state", lambda: {"sha": "abc123", "dirty": False})


def run(store: Store, tmp_path, **kw):
    return run_backtest(store, Naive(["DK1"]), ["DK1"], FIRST, LAST, tmp_path / "runs", **kw)


def load(run_dir, name):
    return json.loads((run_dir / name).read_text(encoding="utf-8"))


def test_provenance_names_code_packages_and_data(store, tmp_path, clean):
    p = load(run(store, tmp_path), "provenance.json")
    assert p["git_sha"] == "abc123" and p["git_dirty"] is False
    assert {"python", "polars", "nordpower"} <= set(p["packages"])
    assert p["data_snapshot_id"] == "2024-04-01T00:00:00+00:00"  # max ingested_at
    assert p["vault_opening"] is None


def test_a_clean_tree_gives_ok_and_a_dirty_tree_gives_exploratory(store, tmp_path, monkeypatch):
    monkeypatch.setattr(runs, "git_state", lambda: {"sha": "abc123", "dirty": False})
    assert load(run(store, tmp_path), "status.json")["status"] == "ok"
    monkeypatch.setattr(runs, "git_state", lambda: {"sha": "abc123", "dirty": True})
    status = load(run(store, tmp_path), "status.json")
    assert status["status"] == "exploratory"
    assert status["reasons"] == ["git working tree is dirty or unknown"]


def test_git_state_reads_this_checkout():
    state = runs.git_state()
    assert len(state["sha"]) == 40 and isinstance(state["dirty"], bool)


def test_a_sealed_run_is_read_only_and_verifies(store, tmp_path, clean):
    d = run(store, tmp_path)
    assert not d.name.startswith(".")
    names = {p.name for p in d.iterdir()}
    assert {
        "config.json",
        "provenance.json",
        "forecasts.parquet",
        "metrics.json",
        "leakage_checks.json",
        "quality.json",
        "status.json",
        "manifest.json",
    } == names
    for p in [d, *d.iterdir()]:
        assert not p.stat().st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH), p
    assert runs.verify(d) == []
    assert not [p for p in (tmp_path / "runs").iterdir() if p.name.startswith(".incomplete")]


def test_tampering_with_a_sealed_run_is_detected(store, tmp_path, clean):
    d = run(store, tmp_path)
    d.chmod(0o755)
    metrics = d / "metrics.json"
    metrics.chmod(0o644)
    metrics.write_text("{}", encoding="utf-8")
    (d / "notes.txt").write_text("added later", encoding="utf-8")
    os.remove(d / "status.json")
    assert runs.verify(d) == [
        "missing: status.json",
        "not in manifest: notes.txt",
        "changed: metrics.json",
    ]


def test_sealing_never_overwrites_an_existing_run(tmp_path):
    (tmp_path / "tmp").mkdir()
    (tmp_path / "final").mkdir()
    with pytest.raises(FileExistsError):
        runs.seal(tmp_path / "tmp", tmp_path / "final")


class Broken(Naive):
    name = "broken"

    def predict(self, view: KnowledgeView, delivery_day: date):
        raise RuntimeError("model blew up")


def test_the_registry_lists_every_run_including_failed_ones(store, tmp_path, clean):
    root = tmp_path / "runs"
    ok = run(store, tmp_path)
    run(store, tmp_path, family="S6")
    with pytest.raises(RuntimeError):
        run_backtest(store, Broken(["DK1"]), ["DK1"], FIRST, LAST, root)
    runs.register(root, {"event": "started", "run_id": "crashed", "at": "x", "family": "S1"})

    listed = runs.registry(root)
    assert [r["state"] for r in listed] == ["ok", "ok", "failed", "abandoned"]
    assert listed[0]["run_id"] == ok.name
    assert listed[2]["error"] == "RuntimeError: model blew up"
    assert runs.trial_counts(listed) == {"S1": 3, "S6": 1}
    # a failed run leaves no sealed directory, only its registry entries
    assert len([p for p in root.iterdir() if p.is_dir() and not p.name.startswith(".")]) == 2


def test_registry_lines_are_only_ever_appended(store, tmp_path, clean):
    path = tmp_path / "runs" / runs.REGISTRY
    run(store, tmp_path)
    before = path.read_text(encoding="utf-8")
    run(store, tmp_path)
    assert path.read_text(encoding="utf-8").startswith(before)


def test_cli_lists_runs_and_trial_counts(store, tmp_path, clean, capsys):
    run(store, tmp_path)
    cli.main(["--data-dir", str(tmp_path), "runs"])
    out = capsys.readouterr().out
    assert "naive  ok" in out and "S1: 1 trials" in out


@pytest.mark.parametrize("n", [0, 1, 2, 3, 30])
def test_poison_sampling_always_includes_the_last_day(n):
    from nordpower.backtest import _sample

    days = [FIRST + timedelta(days=i) for i in range(7)]
    picked = _sample(days, n)
    assert picked[-1] == days[-1] and picked == sorted(set(picked))
    assert len(picked) == min(max(n, 1), len(days))


def test_cli_lists_a_hand_written_registry_entry_without_a_model(tmp_path, capsys):
    runs.register(tmp_path / "runs", {"event": "started", "run_id": "x", "at": "t", "family": "S1"})
    cli.main(["--data-dir", str(tmp_path), "runs"])
    assert "x  S1  ?  abandoned" in capsys.readouterr().out


def test_the_quality_summary_covers_the_run_and_its_lookback(store, tmp_path, clean):
    q = load(run(store, tmp_path), "quality.json")
    assert q["first_delivery_day"] == (FIRST - timedelta(days=7)).isoformat()
    assert q["last_delivery_day"] == LAST.isoformat()
    dk1 = q["view"]["DK1"]
    assert dk1["zone_days"] == 14
    # the fixture holds every hour of every day, so nothing fails
    assert dk1["failed"] == 0 and q["view"]["failures"] == []


def test_the_quality_summary_reports_a_missing_day(tmp_path, clean):
    start, end = delivery_span(FIRST - timedelta(days=7), LAST)
    hours = [start + timedelta(hours=i) for i in range((end - start) // timedelta(hours=1))]
    gap = delivery_span(FIRST + timedelta(days=2), FIRST + timedelta(days=2))
    prices = {("DK1", t): 50.0 for t in hours if not gap[0] <= t < gap[1]}
    s = Store(tmp_path / "store")
    s.append("da_price", price_rows(prices, datetime(2024, 4, 1, tzinfo=UTC)))
    q = load(run(s, tmp_path), "quality.json")
    assert q["view"]["DK1"]["failed"] == 1
    assert q["view"]["DK1"]["by_check"] == {"completeness": 1}
    assert q["view"]["failures"][0]["delivery_day"] == (FIRST + timedelta(days=2)).isoformat()
