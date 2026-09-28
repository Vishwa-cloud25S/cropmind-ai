"""Real-checkpoint delivery for the public deployment (AD-009, Phase 14).

AD-008 still stands: weights are never committed to git. The founder decided
(2026-09-28, AD-009 in docs/02-system-architecture.md) that the PUBLIC deployment
may serve the real checkpoint delivered out-of-band — a private Hugging Face model
repo read through a read-only token configured as platform environment variables.

This module is imported by BOTH the API process (/model-info serving block) and
the worker process (actual inference), so it must stay torch-free and stdlib-only.

Honesty rules enforced here:

  * Origin is decided by CONFIGURATION, never by runtime chance: local path wins,
    then the remote URL, then the clearly-flagged synthetic sample model.
  * A configured-but-failing remote checkpoint fails the job with the verbatim
    reason — it NEVER silently falls back to the sample model.
  * The access token is never logged, never part of an error message, and never
    exposed through the API (only the source host is shown).
  * An optional pinned sha256 is verified after download; a mismatch deletes the
    file and raises — tampered or truncated weights are never served.
"""

from __future__ import annotations

import hashlib
import logging
import os
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

logger = logging.getLogger("cropmind.model_delivery")

ORIGIN_LOCAL = "local-checkpoint"
ORIGIN_REMOTE = "remote-checkpoint"
ORIGIN_SAMPLE = "sample"

_CHUNK = 1024 * 1024  # 1 MiB streaming


class CheckpointDeliveryError(RuntimeError):
    """Remote checkpoint could not be fetched or verified. Message never contains the token."""


def weights_origin(model_checkpoint: str | None, model_url: str | None) -> str:
    """Which weights this environment serves — pure configuration logic, no I/O."""
    if model_checkpoint:
        return ORIGIN_LOCAL
    if model_url:
        return ORIGIN_REMOTE
    return ORIGIN_SAMPLE


def download_filename(url: str) -> str:
    """Cache filename for a remote checkpoint URL (last path segment)."""
    name = Path(urlparse(url).path).name
    return name or "downloaded-checkpoint.pt"


def source_host(url: str | None) -> str | None:
    """Only the host is ever shown publicly — never credentials or signed params."""
    return urlparse(url).hostname if url else None


def cached_checkpoint_path(cache_dir: Path, url: str) -> Path:
    return cache_dir / download_filename(url)


def _sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_checkpoint(
    url: str,
    *,
    token: str | None = None,
    sha256: str | None = None,
    cache_dir: Path,
    timeout_s: float = 300,
    _opener=urllib.request.urlopen,  # injectable for tests
) -> Path:
    """Fetch the remote checkpoint once; reuse the cache afterwards.

    Writes to a `.partial` sibling and atomically renames so a crashed download
    can never masquerade as a complete file. A pinned-sha256 mismatch deletes
    the file and raises — tampered weights are never served.
    """
    target = cached_checkpoint_path(cache_dir, url)
    if target.exists():
        logger.info("checkpoint cache hit: %s", target)
        return target

    cache_dir.mkdir(parents=True, exist_ok=True)
    headers = {"Accept": "application/octet-stream"}
    if token:
        # attached to the request object only — never logged and never rendered anywhere
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    partial = target.with_suffix(target.suffix + ".partial")
    logger.info("downloading checkpoint from %s (no credentials logged)", source_host(url))
    try:
        with _opener(request, timeout=timeout_s) as response, partial.open("wb") as out:
            while True:
                chunk = response.read(_CHUNK)
                if not chunk:
                    break
                out.write(chunk)
    except urllib.error.HTTPError as exc:
        partial.unlink(missing_ok=True)
        raise CheckpointDeliveryError(
            f"checkpoint download failed: HTTP {exc.code} from {source_host(url)} "
            f"(check MODEL_URL and that the read token has access to the repository)"
        ) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        partial.unlink(missing_ok=True)
        raise CheckpointDeliveryError(
            f"checkpoint download failed from {source_host(url)}: {exc.reason if isinstance(exc, urllib.error.URLError) else exc}"
        ) from exc

    if sha256:
        actual = _sha256_of(partial)
        if actual.lower() != sha256.lower():
            partial.unlink(missing_ok=True)
            raise CheckpointDeliveryError(
                f"checkpoint sha256 mismatch from {source_host(url)}: got {actual}, expected {sha256} — refusing to serve"
            )
        logger.info("checkpoint sha256 verified (%s)", actual[:12])
    os.replace(partial, target)
    return target


def serving_block(settings, *, repo_root: Path, sample_checkpoint: Path) -> dict:
    """/model-info `serving` block — the UI derives every model label from this,
    so the same codebase tells the truth on the demo (sample), on the founder's
    machine (local real checkpoint) and on the AD-009 public deployment (remote).
    """
    origin = weights_origin(settings.model_checkpoint, settings.model_url)
    if origin == ORIGIN_LOCAL:
        state = "present" if Path(settings.model_checkpoint).exists() else "missing-on-disk — analyses will fail honestly"
        host = None
    elif origin == ORIGIN_REMOTE:
        cached = cached_checkpoint_path(settings.resolved_model_cache_dir, settings.model_url).exists()
        state = "downloaded" if cached else "pending-first-download"
        host = source_host(settings.model_url)
    else:
        state = "present" if (repo_root / sample_checkpoint).exists() else "generated-on-first-analysis"
        host = None
    return {
        "weights_origin": origin,
        "demo_mode": bool(settings.demo_mode),
        "weights_state": state,
        "source_host": host,
        "integrity": "sha256-pinned" if settings.model_url_sha256 else "operator-verified",
        "label_rule": "labels on every surface are derived from this block — never hardcoded marketing copy",
    }
