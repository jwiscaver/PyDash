# level_loader.py
from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict

def load_level(path: str | Path) -> Dict[str, Any]:
    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)
    # basic validation
    if "obstacles" not in data or not isinstance(data["obstacles"], list):
        raise ValueError("Level JSON must include an 'obstacles' list")
    return data
