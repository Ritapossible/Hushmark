"""The landing page states only what Hushmark's verifiers computed (scripts/build_site_data.py)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"


def test_site_evidence_matches_the_verified_recordings() -> None:
    spec = importlib.util.spec_from_file_location(
        "build_site_data", ROOT / "scripts" / "build_site_data.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    committed = (ROOT / "site" / "evidence.js").read_text()
    assert committed == module.render(), "run: uv run python scripts/build_site_data.py"


def test_page_inserts_evidence_as_text_only() -> None:
    app = (ROOT / "site" / "app.js").read_text()
    assert "innerHTML" not in app and "insertAdjacentHTML" not in app


def test_verify_page_never_claims_a_tee_it_cannot_check() -> None:
    """Audit 2026-11-08: the page cannot check Intel's or NVIDIA's evidence, so a receipt's own
    signature (any laptop key can make one) must never be shown as "Verified" or as signed
    inside a TEE. The page's verdicts are only these three."""
    js = (SITE / "verify.js").read_text()
    assert '"Verified"' not in js and "signed inside the TEE" not in js
    for verdict in (
        "Not verified",
        "Signature matches; TEE not checked",
        "Not the anchored receipt",
    ):
        assert f'"{verdict}"' in js
    assert "a different receipt is the anchored one" in js.lower()
