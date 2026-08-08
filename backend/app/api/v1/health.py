"""Liveness & readiness endpoints (spec §28, §54)."""

from fastapi import APIRouter, HTTPException

from app import __version__
from app.db.session import check_database

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    """Liveness: process is up. Never touches dependencies."""
    return {"status": "ok", "service": "cropmind-api", "version": __version__}


@router.get("/health/ready")
def readiness() -> dict:
    """Readiness: critical dependencies (database) reachable."""
    if not check_database():
        raise HTTPException(
            status_code=503,
            detail={"status": "not_ready", "database": "unreachable"},
        )
    return {"status": "ready", "database": "ok"}
