from __future__ import annotations

import json
import re
from pathlib import Path

from .models import ModuleDefinition

BASE_DIR = Path(__file__).resolve().parent.parent
MODULES_DIR = BASE_DIR / "modules"

_registry: dict[str, ModuleDefinition] = {}


def _parse_prompts_md(text: str) -> dict[str, str]:
    prompts: dict[str, str] = {}
    for m in re.finditer(
        r"^###\s+([A-Z_]+)\s*\n([\s\S]*?)(?=\n###\s+[A-Z_]+|\Z)",
        text,
        flags=re.MULTILINE,
    ):
        prompts[m.group(1).strip()] = m.group(2).strip()
    return prompts


def _load_module(module_dir: Path) -> ModuleDefinition | None:
    module_json = module_dir / "module.json"
    if not module_json.exists():
        return None

    with open(module_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    content_md = module_dir / "content.md"
    if content_md.exists():
        data["content"] = content_md.read_text(encoding="utf-8").strip()

    prompts_md = module_dir / "prompts.md"
    if prompts_md.exists():
        data["prompts"] = _parse_prompts_md(prompts_md.read_text(encoding="utf-8"))

    return ModuleDefinition(**data)


def load_all_modules() -> dict[str, ModuleDefinition]:
    """Discover and load every module under ``modules/``."""
    global _registry
    _registry.clear()

    if not MODULES_DIR.is_dir():
        print(f"WARN: modules directory not found at {MODULES_DIR}")
        return _registry

    for child in sorted(MODULES_DIR.iterdir()):
        if child.is_dir():
            mod = _load_module(child)
            if mod is not None:
                _registry[mod.id] = mod
                print(f"Loaded module: {mod.id} ({mod.name})")

    return _registry


def get_module(module_id: str) -> ModuleDefinition | None:
    return _registry.get(module_id)


def list_modules() -> list[dict]:
    return [
        {
            "id": m.id,
            "name": m.name,
            "system": m.system,
            "description": m.description,
        }
        for m in _registry.values()
    ]


def load_tools_config(filename: str = "tools.json") -> dict:
    path = BASE_DIR / filename
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    print(f"WARN: {filename} not found!")
    return {"GEMINI_TOOLS": [], "GROQ_TOOLS": []}
