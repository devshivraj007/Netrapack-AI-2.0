"""Authentication routes: login + who-am-i.

  POST /api/v1/auth/login  -> validates username/password (hashed), returns a
                              signed session token + role.
  GET  /api/v1/auth/me     -> returns the current token's user (for the app to
                              confirm the session is still valid).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth.deps import current_user
from app.auth.security import create_token, verify_password
from app.db import repository

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    role: str
    username: str
    display_name: str | None = None


@router.post("/login", response_model=LoginResponse, summary="Officer/Admin login")
def login(req: LoginRequest) -> LoginResponse:
    user = repository.get_user(req.username)
    # Verify against the stored hash. Same generic error for unknown user or
    # bad password (don't leak which one was wrong).
    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    token = create_token(user["username"], user["role"])
    return LoginResponse(
        token=token,
        role=user["role"],
        username=user["username"],
        display_name=user.get("display_name"),
    )


@router.get("/me", summary="Return the current authenticated user")
def me(user: dict = Depends(current_user)) -> dict:
    return {"username": user.get("sub"), "role": user.get("role"),
            "exp": user.get("exp")}
