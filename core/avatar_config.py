"""Plantillas de instalación y `avatar config check`.

No activa nada. Un TODO_MAURO es un hueco, no un valor. Un secreto en el
archivo es un error.
"""
from __future__ import annotations

import os
import re
import sys
from typing import Any, Dict, List, Tuple

REQUIRED = (
    "mauro_charter.yaml",
    "allowed_paths.yaml",
    "command_allowlist.yaml",
    "envelope_night.yaml",
    "spend_caps.yaml",
    "marketplaces.yaml",
    "suppliers.yaml",
    "markets_watchlist.yaml",
    "ide_roster.yaml",
    "channels.yaml",
    "credentials_manifest.md",
)

_SECRET = re.compile(
    r"(?i)(api[_-]?key\s*[:=]\s*\S+|sk-[a-z0-9]{8,}|-----BEGIN |AKIA[0-9A-Z]{16})"
)


def parse_simple_yaml(text: str) -> Any:
    """Subconjunto: mapas, listas y escalares. Suficiente para estas plantillas."""
    lines = []
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        lines.append((indent, raw.strip()))
    value, _ = _parse_block(lines, 0, 0)
    return value


def _scalar(token: str) -> Any:
    if token in ("true", "false"):
        return token == "true"
    if token == "[]":
        return []
    if token == "{}":
        return {}
    if re.fullmatch(r"-?\d+", token):
        return int(token)
    if len(token) >= 2 and token[0] == token[-1] and token[0] in ("'", '"'):
        return token[1:-1]
    return token


def _parse_block(lines: List[Tuple[int, str]], index: int, indent: int) -> Tuple[Any, int]:
    if index >= len(lines):
        return {}, index
    kind = "list" if lines[index][1].startswith("- ") else "map"
    if kind == "list":
        items: List[Any] = []
        while index < len(lines) and lines[index][0] == indent and lines[index][1].startswith("- "):
            body = lines[index][1][2:]
            index += 1
            if index < len(lines) and lines[index][0] > indent and ":" in body and not body.endswith(":"):
                # `- key: value` seguido de hermanos más indentados no se usa en estas plantillas.
                pass
            if body.endswith(":") and index < len(lines) and lines[index][0] > indent:
                key = body[:-1]
                child, index = _parse_block(lines, index, lines[index][0])
                items.append({key: child})
            elif ":" in body and not body.endswith(":"):
                key, rest = body.split(":", 1)
                item: Dict[str, Any] = {key.strip(): _scalar(rest.strip())}
                while index < len(lines) and lines[index][0] > indent and ":" in lines[index][1]:
                    k, r = lines[index][1].split(":", 1)
                    item[k.strip()] = _scalar(r.strip())
                    index += 1
                items.append(item)
            else:
                items.append(_scalar(body))
        return items, index
    mapping: Dict[str, Any] = {}
    while index < len(lines) and lines[index][0] == indent and not lines[index][1].startswith("- "):
        key, rest = lines[index][1].split(":", 1)
        key = key.strip()
        rest = rest.strip()
        index += 1
        if rest == "" and index < len(lines) and lines[index][0] > indent:
            child, index = _parse_block(lines, index, lines[index][0])
            mapping[key] = child
        elif rest == "":
            mapping[key] = {}
        else:
            mapping[key] = _scalar(rest)
    return mapping, index


def _walk_todos(value: Any, path: str, found: List[str]) -> None:
    if value == "TODO_MAURO":
        found.append(path)
    elif isinstance(value, dict):
        for key, child in value.items():
            _walk_todos(child, f"{path}.{key}", found)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _walk_todos(child, f"{path}[{index}]", found)


def _read(folder: str, name: str) -> str:
    with open(os.path.join(folder, name), "r", encoding="utf-8") as handle:
        return handle.read()


def check_config(folder: str) -> Tuple[int, List[str]]:
    """0 completo, 1 le faltan datos a Mauro, 2 la plantilla no es segura."""
    lines: List[str] = []
    missing_files = [name for name in REQUIRED if not os.path.isfile(os.path.join(folder, name))]
    for name in missing_files:
        lines.append(f"FALTA archivo {name}")
    if missing_files:
        return 2, lines
    parsed: Dict[str, Any] = {}
    for name in REQUIRED:
        text = _read(folder, name)
        if _SECRET.search(text):
            lines.append(f"SECRETO en {name}")
        if name.endswith(".md"):
            for number, row in enumerate(text.splitlines(), 1):
                if "TODO_MAURO" in row:
                    lines.append(f"FALTA {name}:{number} TODO_MAURO")
            continue
        try:
            parsed[name] = parse_simple_yaml(text)
        except (ValueError, IndexError) as exc:
            lines.append(f"NO_LEE {name}: {exc}")
    if any(line.startswith("SECRETO") or line.startswith("NO_LEE") for line in lines):
        return 2, lines
    todos: List[str] = []
    for name, tree in parsed.items():
        _walk_todos(tree, name, todos)
    for item in todos:
        lines.append(f"FALTA {item}")
    charter = parsed.get("mauro_charter.yaml") or {}
    night = parsed.get("envelope_night.yaml") or {}
    caps = parsed.get("spend_caps.yaml") or {}
    markets = parsed.get("marketplaces.yaml") or {}
    roster = parsed.get("ide_roster.yaml") or {}
    channels = parsed.get("channels.yaml") or {}
    watch = parsed.get("markets_watchlist.yaml") or {}
    broken = False
    if charter.get("hotkey_listener") is not False:
        lines.append("INSEGURO mauro_charter.yaml hotkey_listener debe ser false")
        broken = True
    if charter.get("enabled") is not False:
        lines.append("INSEGURO mauro_charter.yaml enabled debe ser false")
        broken = True
    if night.get("enabled") is not False:
        lines.append("INSEGURO envelope_night.yaml enabled debe ser false")
        broken = True
    if markets.get("active"):
        lines.append("INSEGURO marketplaces.yaml active debe estar vacío")
        broken = True
    if roster.get("real_ides_enabled") is not False:
        lines.append("INSEGURO ide_roster.yaml real_ides_enabled debe ser false")
        broken = True
    if watch.get("trade") is not False:
        lines.append("INSEGURO markets_watchlist.yaml trade debe ser false")
        broken = True
    for key in ("telegram", "mail", "voice"):
        block = channels.get(key) or {}
        if isinstance(block, dict) and block.get("enabled") is not False:
            lines.append(f"INSEGURO channels.yaml {key}.enabled debe ser false")
            broken = True
    for key in ("per_session", "per_day", "per_month"):
        amount = caps.get(key)
        if not isinstance(amount, int) or amount < 0:
            lines.append(f"INSEGURO spend_caps.yaml {key} debe ser un entero >= 0")
            broken = True
    if broken:
        return 2, lines
    if any(line.startswith("FALTA") for line in lines):
        return 1, lines
    lines.append("COMPLETO")
    return 0, lines


def main(argv: List[str]) -> int:
    if argv[:2] != ["config", "check"]:
        print("Uso: avatar config check")
        return 2
    folder = os.environ.get("AVATAR_CONFIG_DIR") or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "avatar"
    )
    code, lines = check_config(folder)
    for line in lines:
        print(line)
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
