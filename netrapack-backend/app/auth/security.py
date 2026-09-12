"""Authentication primitives: password hashing + signed session tokens.

Deliberately dependency-free (stdlib only) but REAL, not hardcoded string
comparison:
  * Passwords -> PBKDF2-HMAC-SHA256 with a per-user random salt.
  * Session tokens -> compact signed tokens (payload.signature) using HMAC-SHA256
    with a server secret, carrying username/role/expiry. Verified on each
    protected request. (A full JWT library would work too; this keeps the
    footprint minimal for the hackathon while remaining tamper-evident.)

The signing secret comes from AUTH_SECRET env var; a dev default is used if
unset (fine for the demo, should be set in production).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Any, Optional

_PBKDF2_ITERATIONS = 200_000
_TOKEN_TTL_SECONDS = int(os.environ.get("AUTH_TOKEN_TTL", 12 * 3600))  # 12h


def _secret() -> bytes:
    return os.environ.get("AUTH_SECRET", "netrapack-dev-secret-change-me").encode()


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------
def hash_password(password: str) -> str:
    """Return 'salt$iterations$hash' (all hex/int) for storage."""
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ITERATIONS)
    return f"{salt.hex()}${_PBKDF2_ITERATIONS}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Constant-time verify against a stored 'salt$iterations$hash'."""
    try:
        salt_hex, iters_str, hash_hex = stored.split("$")
        salt = bytes.fromhex(salt_hex)
        iterations = int(iters_str)
        expected = bytes.fromhex(hash_hex)
    except (ValueError, AttributeError):
        return False
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return hmac.compare_digest(dk, expected)


# ---------------------------------------------------------------------------
# Signed session tokens
# ---------------------------------------------------------------------------
def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def create_token(username: str, role: str) -> str:
    """Create a signed token carrying username, role, and expiry."""
    payload = {
        "sub": username,
        "role": role,
        "exp": int(time.time()) + _TOKEN_TTL_SECONDS,
        "iat": int(time.time()),
    }
    payload_b64 = _b64url(json.dumps(payload, separators=(",", ":")).encode())
    sig = hmac.new(_secret(), payload_b64.encode(), hashlib.sha256).digest()
    return f"{payload_b64}.{_b64url(sig)}"


def verify_token(token: str) -> Optional[dict[str, Any]]:
    """Return the payload dict if the token is valid + unexpired, else None."""
    try:
        payload_b64, sig_b64 = token.split(".")
    except ValueError:
        return None
    expected_sig = hmac.new(_secret(), payload_b64.encode(), hashlib.sha256).digest()
    if not hmac.compare_digest(expected_sig, _b64url_decode(sig_b64)):
        return None
    try:
        payload = json.loads(_b64url_decode(payload_b64))
    except (ValueError, json.JSONDecodeError):
        return None
    if int(payload.get("exp", 0)) < int(time.time()):
        return None
    return payload
