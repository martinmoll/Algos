"""The dataset registry (D-043): key, columns, MTU grid, quality checks and publication rule
of every curated table, read from configs/datasets.toml. Leaf module: imports only polars."""

import tomllib
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import polars as pl

# ponytail: path assumes a source checkout, same as publication.py
REGISTRY = Path(__file__).resolve().parents[2] / "configs" / "datasets.toml"
UTC_TIME = pl.Datetime("us", "UTC")
DTYPES: dict[str, pl.DataType] = {
    "String": pl.String(),
    "Float64": pl.Float64(),
    "Int64": pl.Int64(),
    "Boolean": pl.Boolean(),
    "Date": pl.Date(),
    "Datetime": UTC_TIME,
}
META: dict[str, pl.DataType] = {
    "knowledge_time": UTC_TIME,
    "knowledge_time_grade": pl.String(),
    "source": pl.String(),
    "ingested_at": UTC_TIME,
    "raw_ref": pl.String(),
}
CHECKS = ("completeness", "duplicate", "range")


@dataclass(frozen=True)
class Dataset:
    name: str
    key: tuple[str, ...]
    columns: dict[str, pl.DataType]  # key and value columns, not meta
    mtu: str
    quality: tuple[str, ...]
    publication_rule: str | None

    @property
    def group(self) -> tuple[str, ...]:
        """The key without event_time: one series per group (e.g. a zone, a border)."""
        return tuple(c for c in self.key if c != "event_time")

    @property
    def values(self) -> tuple[str, ...]:
        return tuple(c for c in self.columns if c not in self.key)

    @property
    def schema(self) -> dict[str, pl.DataType]:
        """Every stored column: key, values, then meta."""
        return self.columns | META

    def validate(self, rows: pl.DataFrame) -> None:
        """Rows must have exactly the registered columns with the registered dtypes."""
        expected, got = self.schema, dict(rows.schema)
        missing, extra = set(expected) - set(got), set(got) - set(expected)
        if missing or extra:
            raise ValueError(
                f"{self.name}: columns do not match the registry: missing {sorted(missing)}, "
                f"unexpected {sorted(extra)}"
            )
        wrong = {c: (str(got[c]), str(t)) for c, t in expected.items() if got[c] != t}
        if wrong:
            raise ValueError(f"{self.name}: wrong dtypes (got, registered): {wrong}")


def _parse(name: str, spec: dict) -> Dataset:
    columns = {c: DTYPES[t] for c, t in spec["columns"].items()}
    key = tuple(spec["key"])
    if "event_time" not in key:
        raise ValueError(f"{name}: key must include event_time")
    if not set(key) <= set(columns):
        raise ValueError(f"{name}: key columns {sorted(set(key) - set(columns))} not declared")
    if columns["event_time"] != UTC_TIME:
        raise ValueError(f"{name}: event_time must be a UTC Datetime")
    if set(columns) & set(META):
        raise ValueError(f"{name}: meta columns are added by the store, do not declare them")
    unknown = set(spec.get("quality", [])) - set(CHECKS)
    if unknown:
        raise ValueError(f"{name}: unknown quality checks {sorted(unknown)}")
    return Dataset(
        name=name,
        key=key,
        columns=columns,
        mtu=spec["mtu"],
        quality=tuple(spec.get("quality", [])),
        publication_rule=spec.get("publication_rule"),
    )


def parse_registry(text: str) -> dict[str, Dataset]:
    return {name: _parse(name, spec) for name, spec in tomllib.loads(text).items()}


@cache
def load_registry(path: Path = REGISTRY) -> dict[str, Dataset]:
    return parse_registry(path.read_text(encoding="utf-8"))
