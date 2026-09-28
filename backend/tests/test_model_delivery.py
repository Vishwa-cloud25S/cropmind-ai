"""Phase 14 (AD-009) — out-of-band real-checkpoint delivery.

Pins the honesty rules of the public real-model launch:

  * origin is decided by configuration (local path → remote URL → sample), never
    by runtime chance;
  * a failing remote download raises with the reason and NEVER silently swaps to
    the sample model (that would change model identity under the user);
  * the token is attached to the request only — never rendered in messages and
    never exposed via the /model-info serving block;
  * a pinned sha256 mismatch deletes the bytes and refuses to serve;
  * the PDF banner distinguishes sample weights from real-weights demo trials,
    and the trial banner always carries BOTH evaluation figures, matching
    ml/configs/model.yaml exactly (files win — one source of truth).
"""

from __future__ import annotations

import hashlib
import io
import json
import urllib.error
from pathlib import Path

import pytest
import yaml

from app.core.config import Settings
from app.services import model_delivery
from app.services.mlbridge import get_predictor, reset_cache
from app.services.reporting import BAND_TEXT, SAMPLE_BANNER, TRIAL_BANNER

REPO_ROOT = Path(__file__).resolve().parents[2]


def _model_yaml_evaluation() -> dict:
    config = yaml.safe_load((REPO_ROOT / "ml" / "configs" / "model.yaml").read_text(encoding="utf-8"))
    return config["evaluation"]


# ── origin resolution ────────────────────────────────────────────────────────


def test_origin_resolution_order_is_configuration_fixed() -> None:
    assert model_delivery.weights_origin("/x/checkpoint.pt", "https://h/x") == model_delivery.ORIGIN_LOCAL
    assert model_delivery.weights_origin(None, "https://huggingface.co/u/r/resolve/main/checkpoint.pt") == model_delivery.ORIGIN_REMOTE
    assert model_delivery.weights_origin("", "") == model_delivery.ORIGIN_SAMPLE
    assert model_delivery.weights_origin(None, None) == model_delivery.ORIGIN_SAMPLE


def test_get_predictor_remote_never_falls_back_to_sample(monkeypatch, tmp_path) -> None:
    """A configured-but-failing download must raise — silently serving the sample
    model instead would lie about which model made the prediction."""
    reset_cache()

    def _boom(*args, **kwargs):
        raise model_delivery.CheckpointDeliveryError("checkpoint download failed: HTTP 401 from huggingface.co")

    monkeypatch.setattr(model_delivery, "download_checkpoint", _boom)
    with pytest.raises(model_delivery.CheckpointDeliveryError, match="HTTP 401"):
        get_predictor(None, REPO_ROOT, model_url="https://huggingface.co/u/r/resolve/main/checkpoint.pt", model_cache_dir=tmp_path)
    # and the sample checkpoint was NOT engaged instead
    assert not any(k.startswith(model_delivery.ORIGIN_SAMPLE) for k in _cache_keys())
    reset_cache()


def _cache_keys() -> list[str]:
    from app.services import mlbridge

    return list(mlbridge._cache.keys())


def test_get_predictor_remote_marks_handle_real(monkeypatch, tmp_path) -> None:
    reset_cache()
    fake_ckpt = tmp_path / "checkpoint.pt"
    fake_ckpt.write_bytes(b"fake")
    monkeypatch.setattr(model_delivery, "download_checkpoint", lambda *a, **k: fake_ckpt)

    class _StubPredictor:
        def __init__(self, path, device="cpu"):
            self.path = path

    import sys
    import types

    stub_module = types.ModuleType("ml.inference.predictor")
    stub_module.Predictor = _StubPredictor
    monkeypatch.setitem(sys.modules, "ml.inference.predictor", stub_module)

    handle = get_predictor(None, REPO_ROOT, model_url="https://huggingface.co/u/r/resolve/main/checkpoint.pt", model_cache_dir=tmp_path)
    assert handle.demo is False
    assert handle.origin == model_delivery.ORIGIN_REMOTE
    assert handle.checkpoint_path == fake_ckpt
    reset_cache()


# ── downloader ───────────────────────────────────────────────────────────────


def _opener_returning(payload: bytes):
    def _open(request, timeout=0):
        return io.BytesIO(payload)

    return _open


def test_download_writes_via_partial_and_sends_bearer(tmp_path) -> None:
    payload = b"checkpoint-bytes" * 100
    seen = {}

    def _open(request, timeout=0):
        seen["auth"] = request.headers.get("Authorization")
        return io.BytesIO(payload)

    target = model_delivery.download_checkpoint(
        "https://huggingface.co/vishwa/cropmind/resolve/main/checkpoint.pt",
        token="hf_secret_TEST",
        cache_dir=tmp_path,
        _opener=_open,
    )
    assert target.read_bytes() == payload
    assert seen["auth"] == "Bearer hf_secret_TEST"
    assert not (tmp_path / "checkpoint.pt.partial").exists()  # no partial corpse


def test_download_cache_hit_skips_network(tmp_path) -> None:
    (tmp_path / "checkpoint.pt").write_bytes(b"cached")
    target = model_delivery.download_checkpoint(
        "https://huggingface.co/u/r/resolve/main/checkpoint.pt",
        cache_dir=tmp_path,
        _opener=lambda *a, **k: (_ for _ in ()).throw(AssertionError("network must not be touched on cache hit")),
    )
    assert target.read_bytes() == b"cached"


def test_download_http_error_is_honest_and_leaks_no_token(tmp_path) -> None:
    def _open(request, timeout=0):
        raise urllib.error.HTTPError(request.full_url, 404, "Not Found", None, None)

    with pytest.raises(model_delivery.CheckpointDeliveryError) as excinfo:
        model_delivery.download_checkpoint(
            "https://huggingface.co/u/private/resolve/main/checkpoint.pt",
            token="hf_secret_NEVER_PRINT",
            cache_dir=tmp_path,
            _opener=_open,
        )
    message = str(excinfo.value)
    assert "HTTP 404" in message
    assert "huggingface.co" in message
    assert "hf_secret_NEVER_PRINT" not in message
    assert not (tmp_path / "checkpoint.pt.partial").exists()  # cleaned up


def test_download_sha256_mismatch_deletes_and_refuses_to_serve(tmp_path) -> None:
    payload = b"tampered"
    with pytest.raises(model_delivery.CheckpointDeliveryError, match="sha256 mismatch"):
        model_delivery.download_checkpoint(
            "https://huggingface.co/u/r/resolve/main/checkpoint.pt",
            sha256="0" * 64,
            cache_dir=tmp_path,
            _opener=_opener_returning(payload),
        )
    assert not (tmp_path / "checkpoint.pt").exists()
    assert not (tmp_path / "checkpoint.pt.partial").exists()


def test_download_sha256_match_passes(tmp_path) -> None:
    payload = b"honest bytes"
    digest = hashlib.sha256(payload).hexdigest()
    target = model_delivery.download_checkpoint(
        "https://huggingface.co/u/r/resolve/main/checkpoint.pt",
        sha256=digest,
        cache_dir=tmp_path,
        _opener=_opener_returning(payload),
    )
    assert target.read_bytes() == payload


# ── serving block (drives every UI label) ────────────────────────────────────


@pytest.fixture
def settings_factory(monkeypatch):
    """Settings built per-test (no lru_cache) so no state can leak across tests."""

    def _make(**env):
        for key in ("MODEL_CHECKPOINT", "MODEL_URL", "MODEL_URL_TOKEN", "MODEL_URL_SHA256", "MODEL_CACHE_DIR"):
            monkeypatch.delenv(key, raising=False)
        for key, value in env.items():
            if value is not None:
                monkeypatch.setenv(key, value)
        return Settings(_env_file=None)

    return _make


def test_serving_block_sample_default(settings_factory) -> None:
    settings = settings_factory(MODEL_CHECKPOINT=None, MODEL_URL=None, UPLOAD_DIR="/tmp/cm-test")
    block = model_delivery.serving_block(settings, repo_root=REPO_ROOT, sample_checkpoint=Path("ml/models/pretrained/sample-mobilenetv3.pt"))
    assert block["weights_origin"] == model_delivery.ORIGIN_SAMPLE
    assert block["source_host"] is None
    assert block["label_rule"]


def test_serving_block_remote_pending_then_cached(settings_factory, tmp_path) -> None:
    url = "https://huggingface.co/u/r/resolve/main/checkpoint.pt"
    settings = settings_factory(MODEL_CHECKPOINT=None, MODEL_URL=url, MODEL_CACHE_DIR=str(tmp_path))
    block = model_delivery.serving_block(settings, repo_root=REPO_ROOT, sample_checkpoint=Path("ml/models/pretrained/x.pt"))
    assert block["weights_origin"] == model_delivery.ORIGIN_REMOTE
    assert block["weights_state"] == "pending-first-download"
    assert block["source_host"] == "huggingface.co"
    (tmp_path / "checkpoint.pt").write_bytes(b"x")
    block2 = model_delivery.serving_block(settings, repo_root=REPO_ROOT, sample_checkpoint=Path("ml/models/pretrained/x.pt"))
    assert block2["weights_state"] == "downloaded"


def test_serving_block_never_exposes_the_token(settings_factory, tmp_path) -> None:
    settings = settings_factory(
        MODEL_CHECKPOINT=None,
        MODEL_URL="https://huggingface.co/u/r/resolve/main/checkpoint.pt",
        MODEL_URL_TOKEN="hf_secret_NEVER_EXPOSE",
        MODEL_CACHE_DIR=str(tmp_path),
    )
    block = model_delivery.serving_block(settings, repo_root=REPO_ROOT, sample_checkpoint=Path("x"))
    assert "hf_secret_NEVER_EXPOSE" not in json.dumps(block)


def test_serving_block_local_reports_missing_honestly(settings_factory) -> None:
    settings = settings_factory(MODEL_CHECKPOINT="/nonexistent/checkpoint.pt", MODEL_URL=None)
    block = model_delivery.serving_block(settings, repo_root=REPO_ROOT, sample_checkpoint=Path("x"))
    assert block["weights_origin"] == model_delivery.ORIGIN_LOCAL
    assert "missing-on-disk" in block["weights_state"]


def test_model_info_endpoint_carries_serving_and_evaluation_pair(client) -> None:
    body = client.get("/model-info").json()
    assert body["serving"]["weights_origin"] == model_delivery.ORIGIN_SAMPLE  # test env: neither var set
    evaluation = body["evaluation"]
    config = _model_yaml_evaluation()
    # the pair must always travel together and match the config file exactly
    assert evaluation["in_domain_top1"] == config["in_domain_top1"] == 0.9959
    assert evaluation["out_of_domain_top1"] == config["out_of_domain_top1"] == 0.2349
    assert evaluation["out_of_domain_dataset"] == "plantdoc"
    assert "together" in evaluation["rule"]


# ── report banners ───────────────────────────────────────────────────────────


def _basis(*, demo: bool, weights_demo, name: str = "cropmind-leaf-classifier", version: str = "0.1.0") -> dict:
    return {
        "demo": demo,
        "weights_demo": weights_demo,
        "analysis_demo": False,
        "generated_at_utc": "2026-09-28T00:00:00+00:00",
        "analysis_id": "a",
        "prediction": {
            "phrasing": "Suspected Tomato - Early blight - 61% confidence",
            "status": "SUSPECTED",
            "crop": "tomato",
            "condition": "early_blight",
            "condition_name": "Early blight",
            "confidence": 0.61,
            "band": "HIGH",
            "uncertainty": 0.4,
            "severity": 0.5,
            "severity_label": "Estimated visual severity",
            "latency_ms": 100.0,
            "limitation_notice": "x",
            "explainability_caveat": "y",
        },
        "model": {"name": name, "version": version, "dataset_version": "plantvillage@v1", "demo": weights_demo},
        "image": {"id": "i", "captured_at": None, "width": 1, "height": 1, "source_type": "upload", "sha256_12": "abc"},
        "field": None,
        "zones": [],
        "zone_review_totals": {"PENDING": 0, "APPROVED": 0, "REJECTED": 0},
    }


class _ReportStub:
    report_id = "CMA-20260928-AAAAAA"


def test_sample_weights_keep_the_pinned_demo_banner() -> None:
    from app.services.reporting import _report_lines

    lines = _report_lines(_ReportStub(), _basis(demo=True, weights_demo=True))
    assert SAMPLE_BANNER in lines
    assert "synthetic sample model" in SAMPLE_BANNER


def test_real_weights_via_demo_path_get_trial_banner_with_both_figures() -> None:
    from app.services.reporting import _report_lines

    lines = _report_lines(_ReportStub(), _basis(demo=True, weights_demo=False))
    banner = TRIAL_BANNER.format(name="cropmind-leaf-classifier", version="0.1.0")
    assert banner in lines
    config = _model_yaml_evaluation()
    # both figures, verbatim from the config pair — the banner may never drift from files
    assert f"{config['in_domain_top1']:.4f}" in banner
    assert f"{config['out_of_domain_top1']:.4f}" in banner
    assert "no chemical product or dosage" in banner
    assert "synthetic sample model" not in banner


def test_non_demo_report_has_no_banner() -> None:
    from app.services.reporting import _report_lines

    lines = _report_lines(_ReportStub(), _basis(demo=False, weights_demo=False))
    assert SAMPLE_BANNER not in lines
    assert "DEMO TRIAL" not in "".join(lines)
    assert BAND_TEXT in "".join(lines)  # bands are always printed
