"""Structured logging for Avatar (R2 / E-17).

Replaces ad-hoc `print(...)` with a JSON (or plain) logger that always runs
messages through `redact_secret_text` so API keys and bot tokens never land
in stdout/stderr or log files.
"""
from __future__ import annotations

import json
import logging
import os
import sys
import threading
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional

from core.redaction import redact_secret_text

_CONFIGURED = False
_CONFIG_LOCK = threading.Lock()
_EXTRA_SECRETS: list[str] = []
_SECRETS_LOCK = threading.Lock()

LOG_ENV_LEVEL = "AVATAR_LOG_LEVEL"
LOG_ENV_JSON = "AVATAR_LOG_JSON"
LOG_ENV_FILE = "AVATAR_LOG_FILE"


def register_secrets(secrets: Iterable[str]) -> None:
    """Register known secret values (bot token, API keys) for redaction."""
    with _SECRETS_LOCK:
        for s in secrets:
            if s and len(s) >= 8 and s not in _EXTRA_SECRETS:
                _EXTRA_SECRETS.append(s)


def _known_secrets() -> list[str]:
    with _SECRETS_LOCK:
        return list(_EXTRA_SECRETS)


def _env_truthy(name: str, default: bool = True) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() not in ("0", "false", "no", "off")


class _RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        secrets = _known_secrets()
        if isinstance(record.msg, str):
            record.msg = redact_secret_text(record.msg, secrets)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: redact_secret_text(str(v), secrets) if isinstance(v, str) else v
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    redact_secret_text(str(a), secrets) if isinstance(a, str) else a
                    for a in record.args
                )
        # Structured extras (component, event, …)
        for key in list(record.__dict__.keys()):
            if key.startswith("_") or key in (
                "name", "msg", "args", "levelname", "levelno", "pathname",
                "filename", "module", "exc_info", "exc_text", "stack_info",
                "lineno", "funcName", "created", "msecs", "relativeCreated",
                "thread", "threadName", "processName", "process", "message",
                "asctime",
            ):
                continue
            val = getattr(record, key, None)
            if isinstance(val, str):
                setattr(record, key, redact_secret_text(val, secrets))
        return True


class JsonFormatter(logging.Formatter):
    """One JSON object per line — easy to ship / grep without secret leaks."""

    _SKIP = {
        "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
        "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
        "created", "msecs", "relativeCreated", "thread", "threadName",
        "processName", "process", "message", "asctime", "taskName",
    }

    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        for key, val in record.__dict__.items():
            if key in self._SKIP or key.startswith("_"):
                continue
            if val is None:
                continue
            try:
                json.dumps(val)
                payload[key] = val
            except TypeError:
                payload[key] = str(val)
        return json.dumps(payload, ensure_ascii=False)


class PlainFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        component = getattr(record, "component", None) or record.name
        base = f"[{component}]: {record.getMessage()}"
        if record.exc_info:
            base = f"{base}\n{self.formatException(record.exc_info)}"
        return base


def configure_logging(
    *,
    level: Optional[str] = None,
    json_logs: Optional[bool] = None,
    log_file: Optional[str] = None,
    force: bool = False,
) -> None:
    """Idempotent process-wide logging setup. Safe to call from GUI and server."""
    global _CONFIGURED
    with _CONFIG_LOCK:
        if _CONFIGURED and not force:
            return

        level_name = (level or os.environ.get(LOG_ENV_LEVEL) or "INFO").upper()
        lvl = getattr(logging, level_name, logging.INFO)
        use_json = _env_truthy(LOG_ENV_JSON, True) if json_logs is None else bool(json_logs)
        file_path = log_file if log_file is not None else os.environ.get(LOG_ENV_FILE, "").strip()

        root = logging.getLogger("avatar")
        for handler in list(root.handlers):
            try:
                handler.close()
            except Exception:
                pass
        root.handlers.clear()
        root.setLevel(lvl)
        root.propagate = False

        fmt: logging.Formatter = JsonFormatter() if use_json else PlainFormatter()
        filt = _RedactingFilter()

        stream = logging.StreamHandler(sys.stderr)
        stream.setFormatter(fmt)
        stream.addFilter(filt)
        root.addHandler(stream)

        if file_path:
            try:
                parent = os.path.dirname(os.path.abspath(file_path))
                if parent:
                    os.makedirs(parent, exist_ok=True)
                fh = logging.FileHandler(file_path, encoding="utf-8")
                fh.setFormatter(fmt)
                fh.addFilter(filt)
                root.addHandler(fh)
            except Exception:
                # Never fail process start because of a bad log path.
                root.error("Could not open AVATAR_LOG_FILE=%s", file_path)

        _CONFIGURED = True


def get_logger(name: str = "avatar") -> logging.Logger:
    """Return a child logger under the `avatar` namespace."""
    if not _CONFIGURED:
        configure_logging()
    if not name.startswith("avatar"):
        name = f"avatar.{name}"
    return logging.getLogger(name)


def log(
    level: str,
    message: str,
    *,
    component: str = "Avatar",
    **fields: Any,
) -> None:
    """Convenience one-liner used across bridges/core (replaces print)."""
    logger = get_logger(component.lower().replace(" ", "_"))
    lvl = getattr(logging, (level or "INFO").upper(), logging.INFO)
    # Merge component into extras for JSON / plain formatters.
    extra = {"component": component, **fields}
    logger.log(lvl, message, extra=extra)
