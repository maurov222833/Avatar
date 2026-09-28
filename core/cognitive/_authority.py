"""
Internal signing authority.

Deliberately private (underscore module, no public export of the key material). Both
`GateAuthorization` and `AuthorizedEvidence` are authenticated with a process-local HMAC key
that never leaves this module, so:

  * a caller cannot recompute a valid signature, because the key is not obtainable;
  * a caller cannot edit a signed object and keep the signature valid;
  * `copy`/`deepcopy`/`pickle` of a signed object does not produce anything usable, because
    the reconstructed object no longer carries a signature this module will accept.

This replaces the previous design, where integrity was a plain SHA-256 that the holder of the
object could recompute at will, and where "was it issued" was answered by object identity.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from typing import Any, Dict

#: Process-local key. Never returned by any function in this module.
_KEY: bytes = secrets.token_bytes(32)


def _canonical(payload: Dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def sign(payload: Dict[str, Any]) -> str:
    """Return the hex HMAC-SHA256 of `payload` under the internal key."""
    return hmac.new(_KEY, _canonical(payload), hashlib.sha256).hexdigest()


def verify_signature(payload: Dict[str, Any], signature: Any) -> bool:
    """Constant-time verification of a signature produced by :func:`sign`."""
    if not isinstance(signature, str) or not signature:
        return False
    try:
        expected = sign(payload)
    except Exception:
        return False
    return hmac.compare_digest(expected, signature)


def new_nonce() -> str:
    """Opaque, non-secret unique value for evaluation ids."""
    return secrets.token_hex(8)
