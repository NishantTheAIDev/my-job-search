"""Unit tests for the YC→ATS resolver's pure slug-derivation logic.

The network-probing parts of scripts/refresh_yc_ats.py are not exercised here
(it's an offline maintenance tool); we only test the deterministic helper.
"""

import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "refresh_yc_ats", Path(__file__).parent.parent / "scripts" / "refresh_yc_ats.py"
)
refresh_yc_ats = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(refresh_yc_ats)
candidate_slugs = refresh_yc_ats.candidate_slugs


def test_website_label_comes_first():
    slugs = candidate_slugs("CircuitHub", "https://circuithub.com", "circuithub")
    assert slugs[0] == "circuithub"


def test_strips_www_and_tld_and_punctuation():
    slugs = candidate_slugs("We Work Remotely", "https://www.we-work-remotely.io", "wwr")
    # www and the .io TLD are dropped; punctuation removed from the label
    assert "weworkremotely" in slugs
    assert "wwr" in slugs


def test_dedupes_preserving_order():
    slugs = candidate_slugs("Acme", "https://acme.com", "acme")
    assert slugs == ["acme"]


def test_handles_missing_fields():
    assert candidate_slugs(None, None, None) == []
    assert candidate_slugs("Stripe", None, None) == ["stripe"]


def test_drops_too_short_slugs():
    # A single-character normalized form is dropped
    slugs = candidate_slugs("X", "https://x.ai", "x")
    assert slugs == []


def test_bare_domain_without_scheme():
    slugs = candidate_slugs("Ramp", "ramp.com", "ramp")
    assert slugs[0] == "ramp"


def test_name_normalization_fallback():
    slugs = candidate_slugs("Hello World, Inc.", None, None)
    assert slugs == ["helloworldinc"]
