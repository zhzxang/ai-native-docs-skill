"""Read and write item quantities in a local JSON object."""
from __future__ import annotations

import json
from pathlib import Path


def load(path: Path) -> dict[str, int]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or any(
        not isinstance(name, str)
        or not name.strip()
        or not isinstance(quantity, int)
        or isinstance(quantity, bool)
        or quantity < 0
        for name, quantity in data.items()
    ):
        raise ValueError("Inventory must map non-empty item names to non-negative integers")
    return data


def save(path: Path, items: dict[str, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(items, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

