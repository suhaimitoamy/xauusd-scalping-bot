from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Set

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config.yaml"
REGISTRY_PATH = ROOT / "config" / "method_registry.json"
BRAIN_PATH = ROOT / "src" / "market_brain.py"

LIVE_MAIN = "LIVE_MAIN"
WATCHLIST = "WATCHLIST"
EXPERIMENTAL = "EXPERIMENTAL"
DISABLED = "DISABLED"

DIRECTION_SUFFIXES = ("_BUY", "_SELL")

EXPERIMENTAL_HINTS = (
    "AGGRESSIVE",
    "ANTIGRAVITY",
    "CHOPPY",
    "MICRO_",
    "NEWS_SPIKE",
    "PARABOLIC",
    "MOMENTUM_MARUBOZU",
    "SESSION_OPEN",
)


def normalize_method_name(method: str) -> str:
    return str(method or "").strip().upper()


def base_method_name(method: str) -> str:
    name = normalize_method_name(method)
    for suffix in DIRECTION_SUFFIXES:
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name


def equivalent_method_names(method: str) -> Set[str]:
    name = normalize_method_name(method)
    base = base_method_name(name)
    names = {name, base, f"{base}_BUY", f"{base}_SELL"}
    return {x for x in names if x}


def method_allowed(method: str, whitelist: Iterable[str], backtest_all: bool = False) -> bool:
    if backtest_all:
        return True
    allowed: Set[str] = set()
    for item in whitelist or []:
        allowed.update(equivalent_method_names(item))
    return normalize_method_name(method) in allowed


def load_config(path: Path = CONFIG_PATH) -> Dict[str, Any]:
    if yaml is None:
        raise RuntimeError("PyYAML belum tersedia. Install dengan: pip install pyyaml")
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def save_config(config: Dict[str, Any], path: Path = CONFIG_PATH) -> None:
    if yaml is None:
        raise RuntimeError("PyYAML belum tersedia. Install dengan: pip install pyyaml")
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(config, f, allow_unicode=True, sort_keys=False)


def get_main_methods(config: Dict[str, Any] | None = None) -> List[str]:
    config = config if config is not None else load_config()
    adaptive = config.setdefault("adaptive_brain", {})
    return [normalize_method_name(x) for x in adaptive.get("main_methods", []) or []]


def set_main_methods(methods: Iterable[str], config: Dict[str, Any] | None = None) -> Dict[str, Any]:
    config = config if config is not None else load_config()
    adaptive = config.setdefault("adaptive_brain", {})
    clean: List[str] = []
    seen = set()
    for m in methods:
        name = normalize_method_name(m)
        if name and name not in seen:
            clean.append(name)
            seen.add(name)
    adaptive["main_methods"] = clean
    return config


def discover_methods_from_code(path: Path = BRAIN_PATH) -> List[str]:
    if not path.exists():
        return []
    code = path.read_text(encoding="utf-8", errors="ignore")
    found = set(re.findall(r"['\"]((?:METHOD|AI_METHOD|ANTIGRAVITY)[A-Z0-9_]+|RR2_GROUP_SELL)['\"]", code))
    return sorted(normalize_method_name(x) for x in found if x)


def load_registry(path: Path = REGISTRY_PATH) -> Dict[str, Dict[str, Any]]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if isinstance(data, dict) and "methods" in data:
        data = data.get("methods") or {}
    return {normalize_method_name(k): dict(v or {}) for k, v in (data or {}).items()}


def save_registry(registry: Dict[str, Dict[str, Any]], path: Path = REGISTRY_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "description": "Method status registry. LIVE_MAIN controls live whitelist; WATCHLIST/EXPERIMENTAL stay backtest-only; DISABLED is skipped by manager/report.",
        "methods": dict(sorted(registry.items())),
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def default_status(method: str, live_whitelist: Iterable[str]) -> str:
    name = normalize_method_name(method)
    if method_allowed(name, live_whitelist):
        return LIVE_MAIN
    if any(hint in name for hint in EXPERIMENTAL_HINTS):
        return EXPERIMENTAL
    return WATCHLIST


def build_registry(config: Dict[str, Any] | None = None) -> Dict[str, Dict[str, Any]]:
    config = config if config is not None else load_config()
    live = get_main_methods(config)
    existing = load_registry()
    discovered = set(discover_methods_from_code())
    discovered.update(live)

    registry: Dict[str, Dict[str, Any]] = {}
    for method in sorted(discovered):
        prev = existing.get(method, {})
        status = prev.get("status") or default_status(method, live)
        if method_allowed(method, live):
            status = LIVE_MAIN
        registry[method] = {
            "status": status,
            "base": base_method_name(method),
            "notes": prev.get("notes", ""),
        }
    return registry


def sync_registry() -> Dict[str, Dict[str, Any]]:
    registry = build_registry()
    save_registry(registry)
    return registry


def update_method_status(method: str, status: str) -> Dict[str, Dict[str, Any]]:
    status = status.upper().strip()
    if status not in {LIVE_MAIN, WATCHLIST, EXPERIMENTAL, DISABLED}:
        raise ValueError(f"Status tidak valid: {status}")
    config = load_config()
    live = get_main_methods(config)
    method = normalize_method_name(method)

    if status == LIVE_MAIN:
        names = list(live)
        if method not in names:
            names.append(method)
        set_main_methods(names, config)
    else:
        live = [m for m in live if m != method and base_method_name(m) != method and m != base_method_name(method)]
        set_main_methods(live, config)
    save_config(config)

    registry = build_registry(config)
    entry = registry.setdefault(method, {"base": base_method_name(method)})
    entry["status"] = status
    save_registry(registry)
    return registry


def classify_for_report(method: str) -> str:
    registry = build_registry()
    entry = registry.get(normalize_method_name(method)) or registry.get(base_method_name(method))
    return (entry or {}).get("status") or WATCHLIST


def is_backtest_all_enabled(config: Dict[str, Any] | None = None) -> bool:
    if os.environ.get("BACKTEST_ALL_METHODS", "").lower() in {"1", "true", "yes", "on"}:
        return True
    config = config or {}
    adaptive = config.get("adaptive_brain", {}) if isinstance(config, dict) else {}
    mode = str(adaptive.get("execution_mode") or "").lower()
    return bool(adaptive.get("backtest_all_methods") or mode in {"backtest", "experiment"})
