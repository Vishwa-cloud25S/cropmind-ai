"""Authentication, sessions and access scoping (Phase 10 — FR-01/02/23, docs/04 §3.10).

Posture (honest by design, documented in docs/04):

  * Passwords are bcrypt-hashed (self-describing `$2b$` format); nothing weaker
    ever touches the users table.
  * Sessions are HS256 JWT access tokens (12 h default). Logout is REAL: the
    token's jti lands in the `revoked_tokens` denylist and every request checks
    it — signing out actually kills the token (no client-side theatre).
  * JWT_SECRET_KEY unset/placeholder ⇒ an ephemeral per-boot secret is used and
    a warning is logged: tokens simply do not survive restarts in that mode.
    Never a hardcoded shared secret in the repo.
  * No account enumeration: login failures return one generic 401; 401s carry
    `WWW-Authenticate: Bearer` per RFC 9110.
  * Role bootstrap: the FIRST registered user becomes ADMIN (documented, one-
    time); everyone after registers as FARMER. AGRONOMIST/ADMIN roles are only
    assigned by an admin via /admin.
  * Scoping (v1, deliberately simple and stated in every scoped payload):
    FARMER sees rows they own plus legacy NULL-owner rows (pre-auth/demo
    records — a shared workspace until claimed); AGRONOMIST + ADMIN see all
    (they are the reviewers/operators). Role-hidden rows answer 404 (existence
    isn't confirmed); role-forbidden actions answer 403 with the reason.
  * Demo mode keeps a clearly-flagged anonymous path: with DEMO_MODE on,
    anonymous callers may run demo-flagged uploads/analyses only, and read
    demo/legacy rows. Everything else requires an account.
"""

from __future__ import annotations

import logging
import re
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select, true
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db import models
from app.db.session import DbSession

logger = logging.getLogger("cropmind.auth")

PASSWORD_MIN_LEN = 10
EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}$")  # sanity only — no verification email in MVP
BOOTSTRAP_NOTE = "first registered account becomes ADMIN (documented one-time bootstrap); later accounts are FARMER"

_EPHEMERAL_SECRET: str | None = None


# ── passwords ──────────────────────────────────────────────────────────────────


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("ascii"))
    except ValueError:  # malformed stored hash — fail closed, never crash-open
        return False


def check_password_policy(password: str) -> list[str]:
    """Returns the list of unmet rules (empty = acceptable). Verbatim, user-facing."""
    problems: list[str] = []
    if len(password) < PASSWORD_MIN_LEN:
        problems.append(f"at least {PASSWORD_MIN_LEN} characters")
    if not any(c.isalpha() for c in password):
        problems.append("at least one letter")
    if not any(c.isdigit() for c in password):
        problems.append("at least one digit")
    return problems


def check_email(email: str) -> bool:
    return bool(EMAIL_RE.match(email)) and len(email) <= 320


# ── tokens ─────────────────────────────────────────────────────────────────────


def _jwt_secret() -> str:
    """JWT secret: configured value, or an ephemeral per-boot one (with a loud warning once)."""
    global _EPHEMERAL_SECRET
    configured = get_settings().jwt_secret_key
    if configured and not configured.startswith("change-me"):
        return configured
    if _EPHEMERAL_SECRET is None:
        _EPHEMERAL_SECRET = secrets.token_urlsafe(48)
        logger.warning(
            "JWT_SECRET_KEY is unset/placeholder — using an EPHEMERAL per-boot secret; "
            "all tokens die on restart (fine for local dev; set a real secret otherwise)"
        )
    return _EPHEMERAL_SECRET


def mint_token(user: models.User, *, ttl_minutes: int | None = None) -> tuple[str, datetime]:
    """Mint an HS256 access token; returns (token, expires_at utc)."""
    settings = get_settings()
    ttl = ttl_minutes if ttl_minutes is not None else settings.access_token_expire_minutes
    expires_at = datetime.now(UTC) + timedelta(minutes=ttl)
    payload = {
        "sub": user.id,
        "role": user.role,
        "jti": uuid.uuid4().hex,
        "iat": int(datetime.now(UTC).timestamp()),
        "exp": int(expires_at.timestamp()),
        "iss": "cropmind-api",
    }
    token = jwt.encode(payload, _jwt_secret(), algorithm=settings.jwt_algorithm)
    return token, expires_at


def decode_token(token: str) -> dict[str, Any]:
    """Validate signature + expiry; raises jwt.PyJWTError subclasses on failure."""
    settings = get_settings()
    return jwt.decode(
        token,
        _jwt_secret(),
        algorithms=[settings.jwt_algorithm],
        issuer="cropmind-api",
        options={"require": ["sub", "exp", "jti"]},
    )


def is_revoked(db: Session, jti: str) -> bool:
    return db.get(models.RevokedToken, jti) is not None


def revoke_token(db: Session, jti: str, user_id: str, expires_at: datetime) -> None:
    db.add(models.RevokedToken(jti=jti, user_id=user_id, expires_at=expires_at))
    # opportunistic hygiene: drop denylist rows whose tokens are expired anyway
    db.query(models.RevokedToken).filter(models.RevokedToken.expires_at < datetime.now(UTC)).delete()


# ── request plumbing ───────────────────────────────────────────────────────────


def _unauthorized(reason: str, code: str) -> HTTPException:
    return HTTPException(
        401,
        {"detail": reason, "auth": code},
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(request: Request, db: DbSession) -> models.User | None:
    """Dependency: resolve the caller.

    No Authorization header ⇒ anonymous (None) — endpoints then apply their own
    rules (some allow the demo path). A PRESENT but invalid/expired/revoked
    token is a hard 401 — silently degrading a bad token to anonymous would
    hide session expiry from the user.
    """
    header = request.headers.get("authorization", "")
    if not header:
        return None  # anonymous — each endpoint applies its own rules (demo path, role gates)
    if not header.lower().startswith("bearer "):
        raise _unauthorized("malformed Authorization header — expected 'Bearer <token>'", "malformed")
    raw = header[7:].strip()
    try:
        claims = decode_token(raw)
    except jwt.ExpiredSignatureError as exc:
        raise _unauthorized("session expired — sign in again", "expired") from exc
    except jwt.PyJWTError as exc:
        raise _unauthorized("invalid session token — sign in again", "invalid") from exc
    if is_revoked(db, claims["jti"]):
        raise _unauthorized("session was signed out — sign in again", "revoked")
    user = db.get(models.User, claims["sub"])
    if user is None:
        raise _unauthorized("account no longer exists — sign in again", "invalid")
    return user


CurrentUser = Annotated[models.User | None, Depends(get_current_user)]

PUBLIC_PATH_PREFIXES = ("/health", "/supported-crops", "/model-info", "/auth/", "/openapi", "/docs")


def require_user(user: CurrentUser, *, demo_ok: bool = False) -> models.User | None:
    """Gate: authenticated user, or the clearly-flagged anonymous demo path.

    demo_ok endpoints additionally accept anonymous callers when DEMO_MODE is
    on — those actions are flagged demo and stored accordingly, never silent.
    Returns the user (None only when the demo path applied); raises 401/403.
    """
    if user is not None:
        return user
    if demo_ok and get_settings().demo_mode:
        return None
    if not get_settings().auth_required:
        return None  # documented local-dev bypass
    hint = " — or run with the demo option (DEMO_MODE is on)" if demo_ok and get_settings().demo_mode else ""
    raise _unauthorized(f"authentication required for this action — sign in first{hint}", "missing")


def read_gate(user: models.User | None) -> None:
    """401 for anonymous READS unless the demo path (DEMO_MODE) is on.

    Demo/legacy NULL-owner rows are public-by-design demo material in demo
    mode; with demo off (or auth fully required) anonymous reads get a clear
    401 instead of silent empty lists.
    """
    if user is None and get_settings().auth_required and not get_settings().demo_mode:
        raise _unauthorized("authentication required — sign in first", "missing")


def require_role(user: models.User | None, *roles: str) -> models.User:
    """Role gate with the honest reason; 401 when anonymous, 403 when wrong role."""
    if user is None:
        raise _unauthorized("authentication required — sign in first", "missing")
    if user.role not in roles:
        raise HTTPException(
            403,
            {
                "detail": f"this action requires role {' or '.join(roles)} — your role is {user.role}",
                "your_role": user.role,
                "requires": list(roles),
            },
        )
    return user


# ── scoping (v1 rules — see module docstring) ──────────────────────────────────

VISION_ALL_ROLES = {"ADMIN", "AGRONOMIST"}


def ownership_filter(column, user: models.User | None):
    """SQLAlchemy clause implementing the documented v1 visibility rule."""
    if user is not None and user.role in VISION_ALL_ROLES:
        return true()
    if user is not None:
        return column.is_(None) | (column == user.id)
    # anonymous (demo mode): legacy/demo NULL-owner rows only
    return column.is_(None)


def visible_or_404(owner_id: str | None, user: models.User | None, noun: str) -> None:
    """404 when the row exists but isn't in the caller's scope (existence stays unconfirmed)."""
    if user is not None and user.role in VISION_ALL_ROLES:
        return
    if owner_id is None:
        return
    if user is not None and owner_id == user.id:
        return
    raise HTTPException(404, f"{noun} not found")


def user_payload(user: models.User) -> dict[str, Any]:
    return {
        "id": user.id,
        "email": user.email,
        "role": user.role,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


def list_users(db: Session) -> list[models.User]:
    return db.execute(select(models.User).order_by(models.User.created_at.asc())).scalars().all()


def users_count(db: Session) -> int:
    return len(list_users(db))
