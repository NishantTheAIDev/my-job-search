"""Unit tests for backend.services.relevance.score_relevance.

The function is pure (no I/O, no LLM calls), so every test is a straightforward
call-and-assert with no fixtures required.

Test coverage:
- Off-role floor (head noun absent from title)
- On-role, no modifiers (base score only)
- Head noun + modifier in title (title boost)
- Description is ignored (title-only scoring; no board bias)
- Two modifiers in title (additive title boosts)
- Whole-word boundary safety ("ai" must not match "available" or "training")
- Synonym matching: modifiers (ai↔ml, senior↔sr, frontend↔front-end) and
  head noun (engineer↔developer)
- Regression: ML/AI roles out-rank off-specialty engineers for "senior ai engineer"
- Empty query → neutral score
- No role noun in query; last token is used as head noun
- Score cap at 100
- Case-insensitivity (lowercase title)
- Score is always within [0, 100]
- Query with leading/trailing whitespace is equivalent to stripped query
"""

import pytest

from backend.services.relevance import (
    _BASE_SCORE,
    _NEUTRAL_SCORE,
    _OFF_ROLE_FLOOR,
    _TITLE_MODIFIER_BOOST,
    ROLE_NOUNS,
    score_relevance,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _score(title: str = "", description: str = "", query: str = "") -> int:
    """Convenience wrapper so tests don't have to repeat positional args."""
    return score_relevance(title, description, query)


# ---------------------------------------------------------------------------
# Constant sanity checks (imported values match documented spec)
# ---------------------------------------------------------------------------


def test_constants_match_spec():
    assert _BASE_SCORE == 50
    assert _TITLE_MODIFIER_BOOST == 10
    assert _OFF_ROLE_FLOOR == 5
    assert _NEUTRAL_SCORE == 50


def test_role_nouns_contains_expected_terms():
    for noun in (
        "engineer",
        "developer",
        "scientist",
        "manager",
        "designer",
        "analyst",
        "architect",
        "lead",
    ):
        assert noun in ROLE_NOUNS, f"Expected {noun!r} in ROLE_NOUNS"


# ---------------------------------------------------------------------------
# Empty / blank query → neutral
# ---------------------------------------------------------------------------


def test_empty_query_returns_neutral():
    assert _score(title="Software Engineer", description="great role", query="") == _NEUTRAL_SCORE


def test_whitespace_only_query_returns_neutral():
    """strip() is applied before the empty check."""
    assert _score(title="Engineer", description="", query="   ") == _NEUTRAL_SCORE


def test_empty_query_concrete_value():
    assert _score(title="Marketing Specialist", query="") == 50


# ---------------------------------------------------------------------------
# Off-role floor: head noun absent from title
# ---------------------------------------------------------------------------


def test_off_role_returns_floor():
    """'engineer' not in 'Marketing Specialist' → off-role floor."""
    result = _score(title="Marketing Specialist", description="", query="senior ai engineer")
    assert result == _OFF_ROLE_FLOOR
    assert result == 5


def test_off_role_ignores_description_match():
    """Even if the head noun appears in the description, absent from title → floor."""
    result = _score(
        title="Marketing Specialist",
        description="we need an engineer for this role",
        query="engineer",
    )
    assert result == _OFF_ROLE_FLOOR


# ---------------------------------------------------------------------------
# On-role, no modifiers → base score only
# ---------------------------------------------------------------------------


def test_on_role_no_modifiers_returns_base():
    """Head noun in title, no modifiers → exactly _BASE_SCORE."""
    result = _score(title="Software Engineer", description="", query="engineer")
    assert result == _BASE_SCORE
    assert result == 50


def test_on_role_single_token_query():
    """Single-token query where token IS a role noun."""
    result = _score(title="Product Manager", description="", query="manager")
    assert result == 50


# ---------------------------------------------------------------------------
# Modifier in title → title boost
# ---------------------------------------------------------------------------


def test_head_noun_plus_one_modifier_in_title():
    """'senior' is a modifier in title → base + 1 × title boost."""
    result = _score(title="Senior Engineer", description="", query="senior engineer")
    assert result == _BASE_SCORE + _TITLE_MODIFIER_BOOST
    assert result == 60


def test_modifier_in_title_concrete():
    assert _score(title="Senior Engineer", query="senior engineer") == 60


# ---------------------------------------------------------------------------
# Description is IGNORED — scoring is title-only (no board bias).
# ---------------------------------------------------------------------------


def test_modifier_in_description_only_gives_no_boost():
    """'senior' only in description → NO boost; description is not scored."""
    result = _score(
        title="Engineer",
        description="senior experience required",
        query="senior engineer",
    )
    assert result == _BASE_SCORE
    assert result == 50


def test_description_never_affects_score():
    """Same title/query, wildly different descriptions → identical score.

    This is the board-bias fix: a posting from a board that returns a rich JD
    (Adzuna/Indeed) must not out-rank an identical role from a search-only
    board (LinkedIn) whose description is empty.
    """
    rich = _score(
        title="ML Engineer",
        description="senior ai machine learning principal staff expert",
        query="senior ai engineer",
    )
    empty = _score(title="ML Engineer", description="", query="senior ai engineer")
    assert rich == empty


# ---------------------------------------------------------------------------
# Two modifiers in title → additive title boosts
# ---------------------------------------------------------------------------


def test_two_modifiers_in_title():
    """'senior' and 'ai' both in title → base + 2 × title boost."""
    result = _score(title="Senior AI Engineer", description="", query="senior ai engineer")
    assert result == _BASE_SCORE + 2 * _TITLE_MODIFIER_BOOST
    assert result == 70


def test_two_modifiers_concrete():
    assert _score(title="Senior AI Engineer", query="senior ai engineer") == 70


# ---------------------------------------------------------------------------
# Whole-word boundary safety
# ---------------------------------------------------------------------------


def test_ai_does_not_match_available():
    """'ai' must not match the substring 'ai' inside 'available'."""
    # Neither "senior" nor "ai" appear as whole words in title or description.
    result = _score(
        title="Engineer",
        description="available for training",
        query="senior ai engineer",
    )
    # Head noun 'engineer' IS in title → base score. Neither modifier hits.
    assert result == _BASE_SCORE
    assert result == 50


def test_ai_does_not_match_training():
    """'ai' must not match the substring inside 'training'."""
    result = _score(
        title="Engineer",
        description="training provided",
        query="ai engineer",
    )
    assert result == _BASE_SCORE  # 'ai' gives no boost; only base


def test_whole_word_boundary_no_false_positive():
    """Explicit assertion: substring match would give 53 or 56; whole-word gives 50."""
    # If matching were naive substring, "ai" in "available"/"training" would boost.
    score = _score(
        title="Engineer",
        description="available for training",
        query="senior ai engineer",
    )
    assert score == 50, (
        "'ai' should not match 'available'/'training'; 'senior' not present → no boosts"
    )


# ---------------------------------------------------------------------------
# No role noun in query → last token is head noun
# ---------------------------------------------------------------------------


def test_no_role_noun_last_token_is_head_noun_in_title():
    """'product' is NOT in ROLE_NOUNS; last token used as head noun.

    query = 'senior product'  → head_noun='product', modifiers=['senior']
    title = 'Senior Product Manager' contains 'product' → base score
    'senior' is also in title → +10
    Expected: 60
    """
    assert "product" not in ROLE_NOUNS, "pre-condition: 'product' must not be a ROLE_NOUN"
    result = _score(title="Senior Product Manager", description="", query="senior product")
    assert result == _BASE_SCORE + _TITLE_MODIFIER_BOOST
    assert result == 60


def test_no_role_noun_last_token_not_in_title():
    """Last token used as head noun, but absent from title → off-role floor."""
    assert "python" not in ROLE_NOUNS
    result = _score(title="Software Engineer", description="", query="senior python")
    assert result == _OFF_ROLE_FLOOR


# ---------------------------------------------------------------------------
# Score cap at 100
# ---------------------------------------------------------------------------


def test_score_is_capped_at_100():
    """Enough modifiers in title should not exceed 100."""
    # Build a query with many modifiers all present in title.
    # head_noun = 'engineer', modifiers = many role-adjacent adjectives
    many_modifier_query = "senior principal staff ai ml data backend engineer"
    big_title = "Senior Principal Staff AI ML Data Backend Engineer"
    result = _score(title=big_title, description="", query=many_modifier_query)
    assert result == 100


def test_score_never_exceeds_100_parametric():
    cases = [
        ("Senior AI ML Engineer", "lots of ai ml data stuff", "senior ai ml engineer"),
        (
            "Principal Staff Senior AI Data Engineer",
            "machine learning backend systems",
            "principal staff senior ai data machine learning engineer",
        ),
    ]
    for title, desc, query in cases:
        assert _score(title=title, description=desc, query=query) <= 100


# ---------------------------------------------------------------------------
# Case-insensitivity
# ---------------------------------------------------------------------------


def test_case_insensitive_title_lowercase():
    """Lowercase title should score the same as title-cased title."""
    upper_result = _score(title="Senior AI Engineer", description="", query="senior ai engineer")
    lower_result = _score(title="senior ai engineer", description="", query="senior ai engineer")
    assert lower_result == upper_result
    assert lower_result == 70


def test_case_insensitive_query_uppercase():
    """Uppercase query tokens should still match."""
    result = _score(title="Senior Engineer", description="", query="SENIOR ENGINEER")
    assert result == 60


def test_case_insensitive_mixed():
    result = _score(title="sEnIoR eNgInEeR", description="", query="Senior Engineer")
    assert result == 60


# ---------------------------------------------------------------------------
# Score always in [0, 100]
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "title,description,query",
    [
        ("", "", ""),
        ("Engineer", "", "engineer"),
        ("Marketing Manager", "", "senior ai engineer"),
        ("Senior AI Engineer", "machine learning systems", "senior ai engineer"),
        ("", "some description", "developer"),
        ("Lead Architect", "cloud infrastructure", "cloud architect"),
    ],
)
def test_score_always_in_valid_range(title: str, description: str, query: str):
    result = _score(title=title, description=description, query=query)
    assert 0 <= result <= 100, f"score={result} out of range for title={title!r}, query={query!r}"


# ---------------------------------------------------------------------------
# Modifier scoring: title boost takes priority over description boost
# ---------------------------------------------------------------------------


def test_modifier_in_both_title_and_description_uses_title_boost():
    """Modifier in title → +10 once. Description presence adds nothing."""
    result = _score(
        title="Senior Engineer",
        description="senior experience preferred",
        query="senior engineer",
    )
    assert result == _BASE_SCORE + _TITLE_MODIFIER_BOOST
    assert result == 60


# ---------------------------------------------------------------------------
# Query whitespace handling
# ---------------------------------------------------------------------------


def test_leading_trailing_whitespace_in_query_normalized():
    """strip() on query should make leading/trailing whitespace irrelevant."""
    result_clean = _score(title="Engineer", description="", query="engineer")
    result_padded = _score(title="Engineer", description="", query="  engineer  ")
    assert result_clean == result_padded


# ---------------------------------------------------------------------------
# Only title modifiers count; description modifiers are ignored
# ---------------------------------------------------------------------------


def test_only_title_modifiers_count():
    """One modifier in title (+10); a second modifier only in description → no boost."""
    result = _score(
        title="Senior Engineer",
        description="experience with ai systems required",
        query="senior ai engineer",
    )
    assert result == _BASE_SCORE + _TITLE_MODIFIER_BOOST
    assert result == 60


# ---------------------------------------------------------------------------
# Regression: 'specialist' IS a ROLE_NOUN (so "Marketing Specialist" test is valid)
# ---------------------------------------------------------------------------


def test_specialist_is_role_noun():
    """'specialist' is in ROLE_NOUNS — so query='specialist' on matching title scores 50."""
    assert "specialist" in ROLE_NOUNS
    result = _score(title="Marketing Specialist", description="", query="specialist")
    assert result == _BASE_SCORE


def test_off_role_query_engineer_vs_specialist_title():
    """Head noun 'engineer' is not in 'Marketing Specialist' → floor."""
    result = _score(title="Marketing Specialist", description="", query="senior ai engineer")
    assert result == _OFF_ROLE_FLOOR


# ---------------------------------------------------------------------------
# Synonym matching — modifiers
# ---------------------------------------------------------------------------


def test_ai_modifier_matches_ml_in_title():
    """'ai' modifier matches an 'ML Engineer' title via the AI/ML synonym group."""
    result = _score(title="ML Engineer", description="", query="ai engineer")
    assert result == _BASE_SCORE + _TITLE_MODIFIER_BOOST
    assert result == 60


def test_ai_modifier_matches_machine_learning_phrase():
    """Multi-word synonym 'machine learning' matched as a phrase in the title."""
    result = _score(title="Machine Learning Engineer", description="", query="ai engineer")
    assert result == 60


def test_senior_modifier_matches_sr_abbreviation():
    result = _score(title="Sr Engineer", description="", query="senior engineer")
    assert result == 60


def test_frontend_modifier_matches_hyphenated_variant():
    result = _score(title="Front-End Engineer", description="", query="frontend engineer")
    assert result == 60


# ---------------------------------------------------------------------------
# Synonym matching — head noun (engineer family)
# ---------------------------------------------------------------------------


def test_head_noun_engineer_matches_developer_title():
    """'engineer' query passes the title gate on a 'Developer' title (synonym)."""
    result = _score(title="AI Developer", description="", query="ai engineer")
    assert result == _BASE_SCORE + _TITLE_MODIFIER_BOOST
    assert result == 60


# ---------------------------------------------------------------------------
# Regression: the exact "senior ai engineer" ranking bug
# ---------------------------------------------------------------------------


def test_ml_engineer_outranks_offspecialty_engineer():
    """ML/AI roles must out-rank an off-specialty engineer for 'senior ai engineer'.

    Before the synonym + board-bias fix, 'GxP Instrument Systems Engineer'
    scored 56 (description boosts) while 'ML Engineer' scored 50 — wrong order.
    Now ML matches 'ai' in the title (+10) and descriptions are ignored.
    """
    ml = _score(title="ML Engineer - DevOps", description="", query="senior ai engineer")
    ml_ops = _score(title="ML Ops Engineer", description="", query="senior ai engineer")
    gxp = _score(
        title="GxP Instrument Systems Engineer- Norwood, MA",
        description="senior role; some ai exposure a plus",
        query="senior ai engineer",
    )
    assert ml == 60
    assert ml_ops == 60
    assert gxp == _BASE_SCORE  # 50 — base only; description no longer boosts
    assert ml > gxp and ml_ops > gxp


# ---------------------------------------------------------------------------
# Morphology / suffix tolerance: "engineer" matches "Engineering" / plurals
# ---------------------------------------------------------------------------


def test_head_noun_matches_engineering_suffix():
    """'engineer' head noun matches an 'Engineering' title (was a real miss → floor 5)."""
    result = _score(
        title="Sr. AVP - AI Security Engineering",
        description="",
        query="senior ai engineer",
    )
    # In-role base (50) + ai in title (+10) + sr→senior in title (+10) = 70.
    assert result == 70


def test_head_noun_matches_plural_suffix():
    """'developer' matches a plural 'Developers' title."""
    assert _score(title="Backend Developers Wanted", query="developer") == _BASE_SCORE


def test_modifier_matches_suffix_form():
    """A modifier still uses whole-word matching; suffix tolerance is length-gated."""
    # 'frontend' (len ≥ 4) is matched; here we just confirm in-role + modifier boost.
    assert _score(title="Frontend Engineering", query="frontend engineer") == 60


def test_short_abbreviation_not_suffix_expanded():
    """Length < 4 terms must NOT match inflected forms — 'go' must not match 'going'."""
    # Query head noun 'go' (golang) must not match the word 'going' in a title.
    assert _score(title="We are going remote — Analyst", query="go") == _OFF_ROLE_FLOOR


def test_ai_modifier_not_matched_via_suffix():
    """'ai' (len 2) must never match 'available' even with suffix tolerance present."""
    assert _score(title="Engineer (seats available)", query="ai engineer") == _BASE_SCORE


# ---------------------------------------------------------------------------
# Soft related-role tier: different-but-related tech role noun in title
# ---------------------------------------------------------------------------


def test_related_role_architect_for_engineer_query():
    """'AI Architect' for an 'ai engineer' search → related tier, not off-role floor."""
    result = _score(
        title="Principal Enterprise Architect - AI",
        description="",
        query="senior ai engineer",
    )
    # Related base (35) + ai in title (+5). 'principal' is not a 'senior' synonym.
    assert result == 40


def test_related_role_scientist_for_engineer_query():
    """'Data Scientist' for an 'ai engineer' search → related tier."""
    result = _score(
        title="Staff Data Scientist | (AI ML | Graph Neural Networks and NLP)",
        description="",
        query="senior ai engineer",
    )
    assert result == 40


def test_related_role_lead_for_engineer_query():
    """'Data Science Lead' for an 'ai engineer' search → related tier ('lead' kept)."""
    result = _score(
        title="Data Science Lead (AI/ML Lead)",
        description="",
        query="senior ai engineer",
    )
    assert result == 40


def test_related_role_always_below_in_role_base():
    """A related-role title can never outrank a true in-role title.

    Even with every modifier matching, the related band is capped at 49 < 50.
    """
    related = _score(
        title="Senior AI ML Architect",
        description="",
        query="senior ai ml engineer",
    )
    in_role_bare = _score(title="Engineer", description="", query="senior ai ml engineer")
    assert related <= 49
    assert related < _BASE_SCORE
    assert in_role_bare == _BASE_SCORE


def test_related_role_visible_above_default_floor():
    """Related-tier scores sit above the default min_relevance=30 filter."""
    result = _score(title="AI Architect", description="", query="ai engineer")
    assert result >= 35  # not hidden by the default floor


def test_generic_role_noun_not_related():
    """Generic nouns (specialist/analyst) are NOT in the family → still off-role floor."""
    assert _score(title="Marketing Specialist", query="ai engineer") == _OFF_ROLE_FLOOR
    assert _score(title="Financial Analyst", query="ai engineer") == _OFF_ROLE_FLOOR


def test_unrelated_role_still_floors():
    """A genuinely off-role title with no family member stays at the floor."""
    assert _score(title="Marketing Manager", query="senior ai engineer") == _OFF_ROLE_FLOOR
    assert (
        _score(title="Mid/Senior AI Cinematic Video Editor", query="senior ai engineer")
        == _OFF_ROLE_FLOOR
    )


def test_non_role_head_noun_no_related_tier():
    """If the query head noun isn't a tech role noun, the related tier never triggers."""
    # 'python' is the head noun (not a role noun); a title with 'architect' must
    # NOT be promoted just because architect is in the family.
    assert _score(title="Cloud Architect", query="python") == _OFF_ROLE_FLOOR
