"""Assumed knowledge times for backfilled values, from the reviewed publication-rules config."""

import tomllib
from datetime import datetime, time
from functools import cache
from pathlib import Path

from nordpower.timeutil import local_time_on_day_before_delivery

# ponytail: path assumes a source checkout, same as zones.py
RULES = Path(__file__).resolve().parents[2] / "configs" / "publication_rules.toml"
ASSUMED = "assumed"  # knowledge-time grade of every value timed by a publication rule


@cache
def load_rules(path: Path = RULES) -> dict[str, dict]:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def assumed_knowledge_time(
    dataset: str, event_time: datetime, rules: dict[str, dict] | None = None
) -> datetime:
    """Knowledge time of a backfilled value of `dataset` at `event_time`; grade it ASSUMED."""
    rule = (rules if rules is not None else load_rules())[dataset]
    if rule["rule"] != "local_time_on_day_before_delivery":
        raise ValueError(f"unknown publication rule {rule['rule']!r} for {dataset}")
    return local_time_on_day_before_delivery(event_time, time.fromisoformat(rule["local_time"]))
