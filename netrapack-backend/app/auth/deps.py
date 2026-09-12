"""FastAPI auth dependencies: extract + verify the bearer token and enforce roles."""

from __future__ import annotations

from typing import Any

from fastapi import Depends, Header, HTTPException

from .security import verify_token


def current_user(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    """Require a valid 'Authorization: Bearer <token>' header; return its payload."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token.")
    token = authorization.split(" ", 1)[1].strip()
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")
    return payload


def require_officer(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    """Officer OR admin may pass (admin is a superset of officer here)."""
    if user.get("role") not in ("officer", "admin"):
        raise HTTPException(status_code=403, detail="Officer role required.")
    return user


def require_admin(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin role required.")
    return user
