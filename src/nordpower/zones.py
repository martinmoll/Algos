import tomllib
from pathlib import Path

# ponytail: path assumes a source checkout (editable install); use importlib.resources if packaged
CONFIG = Path(__file__).resolve().parents[2] / "configs" / "zones.toml"


def load_zones() -> dict[str, dict]:
    """Zone id -> {eic, country, pseudo?}. Includes the SYS pseudo-zone."""
    return tomllib.loads(CONFIG.read_text(encoding="utf-8"))
