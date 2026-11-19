"""Position map loader (config/position_map.yaml). Use this wherever a take's `position`
field is interpreted (geometry, along/across-link grouping, figures); never hard-code it."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
MAP_PATH = ROOT / "config" / "position_map.yaml"


@lru_cache(maxsize=4)
def load(path: str | Path = MAP_PATH) -> dict:
    return yaml.safe_load(Path(path).read_text())


def position(name: str, path: str | Path = MAP_PATH) -> dict:
    """Entry for a meta.json `position` value (KeyError if unknown)."""
    return load(path)["positions"][name]


def centre(name: str, path: str | Path = MAP_PATH) -> tuple[float, float] | None:
    """(x, y) of a point, or the middle of a segment/area; None for 'none'."""
    p = position(name, path)
    if p["kind"] == "point":
        return float(p["x"]), float(p["y"])
    if p["kind"] in ("segment", "area"):
        return float(sum(p["x"]) / 2), float(sum(p["y"]) / 2)
    return None


def link_relation(name: str, path: str | Path = MAP_PATH) -> str | None:
    """'along_link' / 'across_link' for walk paths, else None."""
    return position(name, path).get("relation")
