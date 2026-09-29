"""
Secret redaction for text that may leave the process: provider errors, logs, chat replies.

Two layers, because neither alone is enough:
  1. Known secret values (the keys Avatar actually loaded) are replaced verbatim.
  2. Well-known credential shapes are replaced even when the value is not known here,
     e.g. a key echoed back inside a proxy's error page.
"""
import re
from typing import Iterable

REDACTED = "[REDACTED]"

_PREFIXED_PATTERNS = (
    re.compile(r"(?i)([?&](?:key|api_key|apikey|access_token|token)=)[^&\s'\"]+"),
    re.compile(r"(?i)(bearer\s+)[0-9a-z._\-]{16,}"),
    re.compile(r"(?i)(x-goog-api-key['\"]?\s*[:=]\s*['\"]?)[0-9a-z_\-]{16,}"),
    re.compile(r"(/bot)\d{5,}:[0-9A-Za-z_\-]{20,}"),
)

_BARE_PATTERNS = (
    re.compile(r"AIza[0-9A-Za-z_\-]{20,}"),
    re.compile(r"\bgsk_[0-9A-Za-z]{20,}"),
    re.compile(r"\bsk-[0-9A-Za-z_\-]{20,}"),
    re.compile(r"\bgh[pousr]_[0-9A-Za-z]{20,}"),
    re.compile(r"\bgithub_pat_[0-9A-Za-z_]{20,}"),
    re.compile(r"\b\d{6,}:AA[0-9A-Za-z_\-]{30,}"),
)

#: Values shorter than this are not treated as secrets, so an empty or placeholder
#: value can never blank out ordinary text.
_MIN_SECRET_LEN = 8


def redact_secret_text(text, known_secrets: Iterable[str] = ()) -> str:
    if not text:
        return text
    out = str(text)
    for secret in sorted({s for s in known_secrets if s and len(s) >= _MIN_SECRET_LEN},
                         key=len, reverse=True):
        out = out.replace(secret, REDACTED)
    for pattern in _PREFIXED_PATTERNS:
        out = pattern.sub(lambda m: m.group(1) + REDACTED, out)
    for pattern in _BARE_PATTERNS:
        out = pattern.sub(REDACTED, out)
    return out
