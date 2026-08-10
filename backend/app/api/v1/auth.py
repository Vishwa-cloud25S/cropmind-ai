"""Auth API (Phase 10 — FR-01/02): register, login, logout (real revocation), me.

Security honesty (docs/04 §3.10): bcrypt hashing; no account enumeration
(one generic login failure message); rate-limited credential endpoints; the
first registered account is ADMIN (one-time documented bootstrap), all later
ones FARMER; logout denylist-makes-dead the exact token (audited).
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.logging import request_id_ctx
from app.db import models
from app.db.session import DbSession
from app.services import security
from app.services.ratelimit import client_ip, enforce_auth

router = APIRouter(tags=["auth"])


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=128)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=128)


def _audit(db, action: str, user_id: str | None, request: Request, entity_id: str | None = None) -> None:
    db.add(
        models.AuditLog(
            user_id=user_id,
            action=action,
            entity="user",
            entity_id=entity_id or user_id,
            ip=client_ip(request),
            request_id=request_id_ctx.get(),
        )
    )


def _token_response(user: models.User) -> dict:
    token, expires_at = security.mint_token(user)
    settings = get_settings()
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_at": expires_at.isoformat(),
        "expires_in_s": settings.access_token_expire_minutes * 60,
        "user": security.user_payload(user),
    }


@router.post("/auth/register", status_code=201)
def register(body: RegisterRequest, db: DbSession, request: Request) -> dict:
    enforce_auth(request)
    email = body.email.strip().lower()
    if not security.check_email(email):
        raise HTTPException(422, [{"loc": ["body", "email"], "msg": "not a plausible email address", "type": "value_error"}])
    problems = security.check_password_policy(body.password)
    if problems:
        raise HTTPException(
            422,
            {
                "detail": "password does not meet the local policy",
                "unmet_rules": problems,
            },
        )
    existing = db.execute(select(models.User).where(func.lower(models.User.email) == email)).scalar_one_or_none()
    if existing is not None:
        # Registration inevitably reveals an address is taken (mitigation = a
        # verification-email flow, post-MVP) — stated plainly rather than faked.
        raise HTTPException(409, "an account with this email already exists")

    is_first = db.execute(select(func.count()).select_from(models.User)).scalar_one() == 0
    role = "ADMIN" if is_first else "FARMER"
    user = models.User(email=email, password_hash=security.hash_password(body.password), role=role)
    db.add(user)
    db.flush()
    _audit(db, "AUTH_REGISTERED", user.id, request)
    return {
        **_token_response(user),
        "role_note": (
            security.BOOTSTRAP_NOTE if is_first else "registered as FARMER — admins can promote roles via /admin"
        ),
    }


@router.post("/auth/login")
def login(body: LoginRequest, db: DbSession, request: Request) -> dict:
    enforce_auth(request)
    email = body.email.strip().lower()
    user = db.execute(select(models.User).where(func.lower(models.User.email) == email)).scalar_one_or_none()
    if user is None or not security.verify_password(body.password, user.password_hash):
        # One generic message for unknown email AND wrong password — no enumeration.
        # The audit row is committed BEFORE raising: the request dependency would
        # otherwise roll it back with the 401, and a failed login is exactly the
        # security event that must survive.
        _audit(db, "AUTH_LOGIN_FAILED", user.id if user else None, request)
        db.commit()
        raise HTTPException(401, "invalid email or password", headers={"WWW-Authenticate": "Bearer"})
    _audit(db, "AUTH_LOGIN_SUCCESS", user.id, request)
    return _token_response(user)


@router.post("/auth/logout")
def logout(db: DbSession, request: Request, user: security.CurrentUser) -> dict:
    user = security.require_user(user)
    header = request.headers.get("authorization", "")
    raw = header[7:].strip()
    claims = security.decode_token(raw)
    security.revoke_token(
        db,
        jti=claims["jti"],
        user_id=user.id,
        expires_at=datetime.fromtimestamp(claims["exp"], tz=UTC),
    )
    _audit(db, "AUTH_LOGOUT", user.id, request)
    db.flush()
    return {"detail": "signed out — this token is now revoked server-side (denylist), not just discarded"}


@router.get("/auth/me")
def me(request: Request, user: security.CurrentUser) -> dict:
    user = security.require_user(user)
    claims = security.decode_token(request.headers["authorization"][7:].strip())
    return {
        "user": security.user_payload(user),
        "session": {
            "expires_at": datetime.fromtimestamp(claims["exp"], tz=UTC).isoformat(),
            "issuer": "cropmind-api",
            "revocation": "server-side denylist — logout really revokes",
        },
    }
