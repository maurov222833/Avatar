"""Cuenta misiones, actos y memoria por día y tipo.

Solo lectura. Copia la base y abre esa copia con mode=ro. No toca el archivo original.
Sirve para ver si una corrida de pruebas dejó filas en la base operativa.
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import sys
import tempfile
from typing import Dict, List, Tuple


_QUERIES = (
    ("misiones", "missions", "created_at", "status"),
    ("actos", "acts", "created_at", "act_type"),
    ("memoria", "history_entries", "timestamp", "role"),
)

_TEST_MARK = (
    "%test_%", "%echo %", "%AVATAR_%", "%avatar_test_%", "%TEST_E2E%",
)


def _copy_database(source: str, folder: str) -> str:
    name = "ledger_copy.db"
    target = os.path.join(folder, name)
    shutil.copy2(source, target)
    for suffix in ("-wal", "-shm"):
        side = source + suffix
        if os.path.isfile(side):
            shutil.copy2(side, target + suffix)
    return target


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    return row is not None


def _counts(conn: sqlite3.Connection, table: str, when: str, kind: str) -> List[Tuple[str, str, int]]:
    if not _table_exists(conn, table):
        return []
    rows = conn.execute(
        f"SELECT substr({when}, 1, 10), COALESCE({kind}, ''), COUNT(*) "
        f"FROM {table} GROUP BY 1, 2 ORDER BY 1, 2"
    ).fetchall()
    return [(str(day or ""), str(label or ""), int(count)) for day, label, count in rows]


def _suspected(conn: sqlite3.Connection) -> Dict[str, int]:
    found = {"misiones": 0, "actos": 0, "memoria": 0}
    if _table_exists(conn, "missions"):
        clause = " OR ".join("raw_prompt LIKE ?" for _ in _TEST_MARK)
        found["misiones"] = int(conn.execute(
            f"SELECT COUNT(*) FROM missions WHERE {clause}", _TEST_MARK,
        ).fetchone()[0])
    if _table_exists(conn, "acts"):
        clause = " OR ".join("request LIKE ?" for _ in _TEST_MARK)
        found["actos"] = int(conn.execute(
            f"SELECT COUNT(*) FROM acts WHERE {clause}", _TEST_MARK,
        ).fetchone()[0])
    if _table_exists(conn, "history_entries"):
        clause = " OR ".join("content LIKE ?" for _ in _TEST_MARK)
        found["memoria"] = int(conn.execute(
            f"SELECT COUNT(*) FROM history_entries WHERE {clause}", _TEST_MARK,
        ).fetchone()[0])
    return found


def inspect_database(source: str) -> str:
    """Copia `source`, la abre en solo lectura y devuelve el informe."""
    if not os.path.isfile(source):
        raise FileNotFoundError(source)
    with open(source, "rb") as handle:
        before = handle.read()
    folder = tempfile.mkdtemp(prefix="avatar_ledger_")
    try:
        copy_path = _copy_database(source, folder)
        uri = "file:" + copy_path.replace("\\", "/") + "?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
        try:
            conn.execute("PRAGMA query_only = ON")
            lines = [f"origen: {os.path.abspath(source)}", "copia: mode=ro", ""]
            for label, table, when, kind in _QUERIES:
                lines.append(f"## {label} ({table}, por día y {kind})")
                rows = _counts(conn, table, when, kind)
                if not rows:
                    lines.append("(sin tabla o sin filas)")
                for day, name, count in rows:
                    lines.append(f"{day or '(sin fecha)'}  {name or '(sin tipo)'}  {count}")
                lines.append("")
            suspected = _suspected(conn)
            lines.append("## parecidas a pruebas")
            for label, count in suspected.items():
                lines.append(f"{label}  {count}")
        finally:
            conn.close()
    finally:
        shutil.rmtree(folder, ignore_errors=True)
    with open(source, "rb") as handle:
        after = handle.read()
    if after != before:
        raise RuntimeError("la base original cambió durante la lectura")
    return "\n".join(lines)


def main(argv: List[str]) -> int:
    if len(argv) != 2:
        print("Uso: python tools/ledger_forensics.py RUTA_DE_LA_BASE", file=sys.stderr)
        return 2
    try:
        print(inspect_database(argv[1]))
    except FileNotFoundError:
        print(f"No está el archivo: {argv[1]}", file=sys.stderr)
        return 2
    except sqlite3.Error as exc:
        print(f"No se pudo leer la copia: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
