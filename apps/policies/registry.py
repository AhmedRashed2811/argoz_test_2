"""Maps DB strategy codes to Python classes (docs §16 registry pattern). Prefers
the StrategyDefinition table, falls back to a static safe registry so the system
still works before any DB rows exist."""
from __future__ import annotations

from importlib import import_module

# code -> dotted class path. Distribution app registers its strategies here at
# import time via register(); this stays decoupled from any one domain app.
_STATIC_REGISTRY: dict[str, str] = {}


def register(code: str, class_path: str) -> None:
    _STATIC_REGISTRY[code] = class_path


def resolve_class(code: str):
    """Return the strategy class for a code, DB definition winning over static."""
    from .models import StrategyDefinition

    class_path = None
    definition = StrategyDefinition.objects.filter(code=code, is_active=True).first()
    if definition:
        class_path = definition.class_path
    class_path = class_path or _STATIC_REGISTRY.get(code)
    if not class_path:
        raise KeyError(f"No strategy registered for code: {code}")
    module_path, _, cls_name = class_path.rpartition(".")
    return getattr(import_module(module_path), cls_name)
