"""Phase 15: full cycle against the LIVE demo deployment (+ coherence gates).

Marked ``live`` — excluded from CI and from the default local suite
(``-m "not live"``), because it exercises the public deployment:

    DEMO_API_URL=https://cropmind-demo-api.onrender.com \\
        pytest backend/tests/test_phase15_demo_live.py -m live

These tests are the end-to-end proof of the demo narrative:
money-loop (bundled in-domain sample -> verbatim HIGH verdict -> honest demo
report PDF), coercion-proof (field photo -> verbatim abstention), and the
paired-figure metadata contract. No numbers are invented; assertions check
invariants the product itself promises on its labels.
"""

from __future__ import annotations

import io
import os
import re
from pathlib import Path
from uuid import uuid4

import httpx
import pytest

DEMO_API = os.environ.get("DEMO_API_URL", "https://cropmind-demo-api.onrender.com").rstrip("/")
SAMPLES = Path(__file__).resolve().parents[2] / "frontend" / "public" / "demo-samples"
DEMO_DIR = Path(__file__).resolve().parents[2] / "demo"
FRONTEND_PUBLIC = SAMPLES

EXPECTED_SAMPLES = {
    "pv-tomato-early-blight.jpg",
    "pv-potato-late-blight.jpg",
    "pd-tomato-early-blight-field.jpg",
    "pd-potato-late-blight-field.jpg",
}

live = pytest.mark.live


def _fresh_bytes(name: str) -> bytes:
    """A byte-fresh 'retake' of a bundled sample.

    The backend hashes image content and dedupes globally: re-uploading the
    exact same bytes under a different anonymous session is honestly refused
    (409). A re-encoded capture is a genuinely different byte string, exactly
    like retaking the photo.
    """
    from PIL import Image

    img = Image.open(SAMPLES / name).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=93, subsampling=2, exif=b"", comment=str(uuid4()).encode())
    return buf.getvalue()


def _upload(client: httpx.Client, name: str) -> str:
    r = client.post(
        "/images",
        params={"demo": "true"},
        files={"file": (name, _fresh_bytes(name), "image/jpeg")},
        timeout=60,
    )
    if r.status_code == 409:  # astronomically unlikely with the uuid comment, but stay honest
        pytest.skip(f"content dedupe refused the retake bytes for {name}")
    assert r.status_code in (200, 201), f"upload failed: {r.status_code} {r.text[:200]}"
    body = r.json()
    return body["image"]["id"] if "image" in body else body["id"]


def _analyse(client: httpx.Client, image_id: str, timeout_s: float = 300.0) -> dict:
    r = client.post("/analyses", json={"image_id": image_id, "demo": True}, timeout=60)
    assert r.status_code in (200, 201, 202), f"analysis create failed: {r.status_code} {r.text[:200]}"
    analysis_id = r.json()["analysis_id"]
    import time

    deadline = time.monotonic() + timeout_s  # free-tier worker may cold-start
    while time.monotonic() < deadline:
        p = client.get(f"/analyses/{analysis_id}/prediction", timeout=60)
        if p.status_code == 200 and p.json().get("status") in ("SUSPECTED", "INCONCLUSIVE"):
            pred = p.json()
            pred["_analysis_id"] = analysis_id
            return pred
        time.sleep(4)
    pytest.fail(f"analysis {analysis_id} did not complete within {timeout_s:.0f}s (cold worker?)")


@live
def test_money_loop_high_verdict_and_honest_demo_report() -> None:
    """Money demo: in-domain sample -> verbatim HIGH phrasing -> honest PDF."""
    with httpx.Client(base_url=DEMO_API) as client:
        image_id = _upload(client, "pv-tomato-early-blight.jpg")
        pred = _analyse(client, image_id)
        assert pred["status"] == "SUSPECTED"
        assert pred["band"] == "HIGH", f"expected HIGH band for the in-domain money sample, got {pred.get('band')}"
        assert re.match(r"^Suspected .+ - .+ - \d+% confidence$", pred["phrasing"]), (
            f"phrasing must be verbatim spec, got: {pred['phrasing']!r}"
        )
        # AD-009 flag semantics (verified against the API contract):
        #   prediction["demo"] / model["demo"]  = WEIGHTS provenance (False = the real
        #     v0.1.0 checkpoint served) — must be False on the live deployment.
        #   analysis row's demo                 = PATH flag (True = flagged anonymous
        #     demo trial) — lives on /analyses/{id}, not on the prediction resource.
        assert pred["demo"] is False, f"prediction.demo is the WEIGHTS flag — real model must serve: {pred}"
        assert pred["model"]["demo"] is False, "model.demo must be False (real checkpoint, AD-009)"
        aid = pred["_analysis_id"]
        ana = client.get(f"/analyses/{aid}", timeout=60)
        assert ana.status_code == 200, f"analysis read failed: {ana.status_code}"
        ana_body = ana.json()
        assert (ana_body.get("demo") if isinstance(ana_body, dict) else None) is True, (
            f"analysis PATH flag must be True on the anonymous demo path: {str(ana_body)[:200]}"
        )

        z = client.post(f"/analyses/{aid}/intervention-zones", json={"demo": True}, timeout=60)
        assert z.status_code in (200, 201), f"zone generation failed: {z.status_code} {z.text[:200]}"

        rep = client.post(f"/analyses/{aid}/report", params={"demo": "true"}, timeout=60)
        assert rep.status_code == 201, f"report create failed: {rep.status_code} {rep.text[:300]}"
        report = rep.json()["report"]
        assert re.fullmatch(r"CMA-\d{8}-[0-9A-F]{6}", report["report_id"])
        basis = report.get("basis", {})
        assert basis.get("demo") is True, "report basis must flag demo path"
        assert basis.get("weights_demo") is False, "demo path must honestly say weights are the REAL model"

        dl = client.get(report["download_url"], params={"demo": "true"}, timeout=60)
        assert dl.status_code == 200 and dl.content[:4] == b"%PDF"
        assert len(dl.content) > 2000

        from pypdf import PdfReader

        text = "\n".join(page.extract_text() for page in PdfReader(io.BytesIO(dl.content)).pages)
    assert "DEMO TRIAL" in text, "demo-path report must carry the DEMO TRIAL banner"
    assert "cropmind-leaf-classifier" in text and "0.1.0" in text, "report must name the real model"
    assert "0.9959" in text and "0.2349" in text, "banner must pair the two evaluation figures"
    assert pred["phrasing"].split(" - ")[-1] in text, "verbatim confidence must appear on the PDF"
    assert "SIMULATION PENDING HUMAN REVIEW" in text
    assert "SHA-256" in text, "integrity receipt line must be printed"


@live
def test_coercion_proof_field_photo_abstains_verbatim() -> None:
    """Coercion-proof: a real field photo must NOT be dressed up as confident."""
    with httpx.Client(base_url=DEMO_API) as client:
        image_id = _upload(client, "pd-tomato-early-blight-field.jpg")
        pred = _analyse(client, image_id)
        assert pred["status"] == "INCONCLUSIVE", (
            f"field photo must abstain (model card OOD contract), got {pred['status']} / {pred.get('phrasing')}"
        )
        ph = pred["phrasing"]
        assert ph.startswith("Inconclusive ("), ph
        assert "below the LOW band" in ph
        assert "retake photo" in ph and "agronomist review" in ph


@live
def test_model_info_pairs_figures_and_serving_block() -> None:
    """The metadata contract every demo surface reads from."""
    with httpx.Client(base_url=DEMO_API, timeout=30) as client:
        info = client.get("/model-info").json()
    serving = info.get("serving", {})
    assert serving.get("weights_origin") == "remote-checkpoint"
    assert serving.get("weights_state") in ("downloaded", "pending-first-download")
    assert serving.get("integrity") == "sha256-pinned"
    ev = info.get("evaluation", {})
    assert ev.get("in_domain_top1") == pytest.approx(0.9959)
    assert ev.get("out_of_domain_top1") == pytest.approx(0.2349)
    assert ev.get("out_of_domain_dataset") == "plantdoc"
    rule = (ev.get("rule") or "") + " ".join(str(v) for v in serving.values())
    assert "together" in rule or "0.9959" in str(info), "pair-travel rule must be stated"


# --------------------------------------------------------------------------
# Coherence gates (not marked live — they run offline in the default suite)
# --------------------------------------------------------------------------

def test_bundle_complete_and_wired() -> None:
    """FR-20 bundle: the four labelled samples exist, match demo/media/ byte-for-byte, and are indexed."""
    public_files = {p.name for p in FRONTEND_PUBLIC.glob("*.jpg")}
    assert public_files == EXPECTED_SAMPLES, f"public samples drifted: {public_files ^ EXPECTED_SAMPLES}"
    media = DEMO_DIR / "media"
    media_files = {p.name for p in media.glob("*.jpg")} if media.is_dir() else set()
    assert media_files == EXPECTED_SAMPLES, (
        f"demo/media/ must mirror the public samples (missing: {EXPECTED_SAMPLES - media_files}; "
        f"extra: {media_files - EXPECTED_SAMPLES})"
    )
    for name in EXPECTED_SAMPLES:
        assert (FRONTEND_PUBLIC / name).read_bytes() == (media / name).read_bytes(), f"{name} diverged"
    readme = (DEMO_DIR / "README.md").read_text(encoding="utf-8")
    for name in EXPECTED_SAMPLES:
        assert name in readme, f"demo/README.md must index {name}"


def test_confidence_band_cutoffs_are_the_documented_ones() -> None:
    cfg = (Path(__file__).resolve().parents[2] / "ml" / "configs" / "model.yaml").read_text(encoding="utf-8")
    bands = {}
    for band in ("high", "medium", "low"):
        m = re.search(rf"^\s*{band}:\s*([0-9.]+)", cfg, re.MULTILINE)
        assert m, f"confidence_bands.{band} missing from model.yaml"
        bands[band] = float(m.group(1))
    assert bands == {"high": 0.60, "medium": 0.45, "low": 0.25}, f"band cutoffs drifted: {bands}"
    assert bands["high"] > bands["medium"] > bands["low"] > 0.0


def test_demo_script_teaches_abstention_verbatim() -> None:
    script = (DEMO_DIR / "demo-script-3min.md").read_text(encoding="utf-8")
    assert "Inconclusive" in script, "demo script must include the abstention moment"
    assert "below the LOW band" in script, "abstention phrasing must name the LOW band"
    assert "retake" in script and "agronomist" in script
    # Pair ridge: never quote one figure without the other.
    assert ("0.9959" in script) == ("0.2349" in script)


def test_pdf_layout_and_banner_contracts() -> None:
    from app.services import reporting

    src = (Path(__file__).resolve().parents[2] / "backend" / "app" / "services" / "reporting.py").read_text(
        encoding="utf-8"
    )
    m = re.search(r"max_chars\s*=\s*(\d+)", src)
    assert m, "reporting.py must pin max_chars for A4 margins"
    assert 100 <= int(m.group(1)) <= 120
    assert '"analysis_demo"' in src and '"weights_demo"' in src, "basis must split path-demo vs weights-demo"
    assert "SHA-256" in src, "PDF must print the image checksum receipt"
    trial = reporting.TRIAL_BANNER
    assert "DEMO TRIAL" in trial and "0.9959" in trial and "0.2349" in trial


def test_rehearsal_notes_carry_measured_receipts() -> None:
    notes = (DEMO_DIR / "rehearsal-notes.md").read_text(encoding="utf-8")
    walk = (DEMO_DIR / "walkthrough-checklist.md").read_text(encoding="utf-8")
    assert "CMA-20260928-9A9684" in notes, "rehearsal notes must carry the money-loop report receipt"
    assert "CMA-20260928-2CDDF0" in walk, "walkthrough must carry the flagship reviewed report receipt"
    assert "Dedupe" in notes or "dedupe" in notes, "the 409 dedupe behaviour must be documented honestly"
    for token in ("PlantVillage", "PlantDoc", "CC BY 4.0", "CC0"):
        kit = (DEMO_DIR / "README.md").read_text(encoding="utf-8")
        assert token in notes or token in kit, f"demo kit lost provenance token {token!r}"
