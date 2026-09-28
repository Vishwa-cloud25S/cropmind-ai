"""Phase 14 — business package integrity.

The package is public endorsement evidence, so the pins protect its honesty
scaffolding: every document exists and is indexed, the 0-traction baseline survives
any edit, dated headers stay, internal links resolve to real files, sourced anchors
stay present, and the paired evaluation figures keep travelling together in any
doc that quotes them.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BUS = REPO_ROOT / "business"

DOCS = [
    "README.md",
    "01-business-plan.md",
    "02-lean-canvas.md",
    "03-market-research.md",
    "04-competitor-landscape.md",
    "05-uk-strategy.md",
    "06-pricing-validation.md",
    "07-financial-model.md",
    "08-data-ip-strategy.md",
    "09-risk-register.md",
    "10-endorsement-evidence-map.md",
]

_MD_LINK = re.compile(r"\]\((?!https?://|mailto:|#)([^)#]+)(?:#[^)]*)?\)")


def _read(name: str) -> str:
    return (BUS / name).read_text(encoding="utf-8")


def test_business_package_complete_and_indexed() -> None:
    for name in DOCS:
        assert (BUS / name).is_file(), f"business package document missing: {name}"
        if name != "README.md":
            assert f"]({name})" in _read("README.md"), f"business/README.md must index {name}"


def test_every_document_carries_its_dated_author_header() -> None:
    for name in DOCS:
        assert "Prepared:** 2026-09-28" in _read(name), f"{name} lost its dated 'Prepared' header"


def test_honest_zero_traction_baseline_survives() -> None:
    assert "0 paying users" in _read("README.md")
    assert "pre-incorporation" in _read("README.md")
    assert "£0" in _read("07-financial-model.md")  # revenue baseline states zero, always
    # the evidence map must keep marking future items as planned, never blur them into done
    assert "🔄" in _read("10-endorsement-evidence-map.md")


def test_internal_links_resolve_to_real_files() -> None:
    for name in DOCS:
        for target in _MD_LINK.findall(_read(name)):
            resolved = (BUS / target).resolve()
            assert resolved.is_file() or resolved.is_dir(), f"{name} links a missing local target: {target}"


def test_sourced_anchors_stay_present() -> None:
    assert "fao.org" in _read("03-market-research.md")
    assert "gov.uk" in _read("03-market-research.md").lower()
    assert "Plantix" in _read("04-competitor-landscape.md")
    assert "Small Robot Company" in _read("04-competitor-landscape.md")
    guidance = _read("05-uk-strategy.md")
    assert "endorsing-bodies-guidance" in guidance
    assert "Innovative, Viable and Scalable" in guidance or "innovative, viable, and scalable" in guidance.lower()


def test_paired_figures_travel_together_in_business_claims() -> None:
    for name in ("01-business-plan.md", "10-endorsement-evidence-map.md"):
        body = _read(name)
        if "0.9959" in body or "0.2349" in body:
            assert "0.9959" in body and "0.2349" in body, f"{name} quotes one evaluation figure without the other"


def test_pricing_is_marked_indicative_not_final() -> None:
    body = _read("06-pricing-validation.md").lower()
    assert "indicative" in body
    assert "nothing here is a real price" in body
