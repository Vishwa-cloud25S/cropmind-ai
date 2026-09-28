"""Phase 13 — documentation set integrity.

The full numbered doc set (01–16) is itself a deliverable: README promises it, and
README's screenshots must be files that exist — anything else would be a broken
claim on the front page. Pins are textual, same as test_deploy_config: files win.

Phase 14 addendum: the license placeholder was closed by founder decision (MIT,
2026-09-28) — LICENSE must exist and README must not regress to "to be confirmed".
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

DOC_SET = [
    "docs/01-product-requirements.md",
    "docs/02-system-architecture.md",
    "docs/03-user-workflows.md",
    "docs/04-api-design.md",
    "docs/05-ml-pipeline.md",
    "docs/06-model-card.md",
    "docs/07-data-card.md",
    "docs/08-eval-runbook.md",
    "docs/09-security.md",
    "docs/10-privacy.md",
    "docs/11-testing.md",
    "docs/12-deployment.md",
    "docs/13-user-guide.md",
    "docs/14-roadmap.md",
    "docs/15-limitations.md",
    "docs/16-responsible-ai.md",
    "docs/datasets.md",
]


def _read(rel: str) -> str:
    path = REPO_ROOT / rel
    assert path.is_file(), f"documentation file missing: {rel}"
    return path.read_text(encoding="utf-8")


def test_numbered_doc_set_is_complete() -> None:
    """Numbers 01–16 exist (dataset register rides along) — no silent gap in the set."""
    for rel in DOC_SET:
        assert (REPO_ROOT / rel).is_file(), f"missing from the 01–16 set: {rel}"


def test_readme_links_every_doc() -> None:
    """The README documentation table must point at every doc in the set."""
    readme = _read("README.md")
    for rel in DOC_SET:
        assert f"({rel})" in readme, f"README does not link {rel}"


def test_readme_local_images_exist_on_disk() -> None:
    """Every *local* image the README embeds (screenshots, logo) must be a real file.

    Remote badge URLs are ignored; a missing local image would silently render a
    broken frame on the repo front page.
    """
    readme = _read("README.md")
    # markdown embeds: ![alt](path) ; html embeds: src="path"
    refs = re.findall(r"!\[[^\]]*\]\(([^)\s]+)\)", readme)
    refs += re.findall(r'src="([^"]+)"', readme)
    local = [r for r in refs if not r.startswith(("http://", "https://", "data:"))]
    assert local, "README should carry at least one local image (logo/screenshots) — pin vacuous otherwise"
    missing = [r for r in local if not (REPO_ROOT / r).is_file()]
    assert not missing, f"README references images that do not exist: {missing}"


def test_docs_do_not_link_missing_docs() -> None:
    """Cross-links between docs resolve (Phase 13 found a stale 11-* link — pin the class)."""
    for rel in DOC_SET:
        text = _read(rel)
        for target in re.findall(r"\]\(((?:\.\./)?docs/[^)\s]+\.md|\d{2}-[a-z0-9-]+\.md|datasets\.md)\)", text):
            base = (REPO_ROOT / rel).parent
            resolved = (base / target).resolve()
            assert resolved.is_file(), f"{rel} links missing doc {target}"


def test_license_is_declared_and_readme_matches() -> None:
    """Founder confirmed MIT 2026-09-28 (business/08 action item closed): the LICENSE
    file must exist with the standard MIT text + copyright holder, and README must not
    regress to the old "to be confirmed" placeholder while claiming open source."""
    lic = _read("LICENSE")
    assert "MIT License" in lic
    assert "Copyright (c) 2026 Vishwa Odduri" in lic
    readme = _read("README.md")
    assert "to be confirmed by the founder" not in readme
    assert "](LICENSE)" in readme
