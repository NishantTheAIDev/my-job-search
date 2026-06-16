"""Lexical relevance scoring for job postings against a search query.

Pure function — no I/O, no LLM calls, unit-testable in isolation.

Score range: 0–100, in three bands:
  - Head noun IN title              → 50 base + 10 per modifier in title, cap 100.
  - Head noun NOT in title, but the
    title carries a DIFFERENT but
    related tech role noun           → 35 base + 5 per modifier in title, cap 49
    (the "soft related-role tier").  (AI/ML titles use Engineer / Architect /
    Scientist / Lead interchangeably, so an "AI engineer" search should
    surface "AI Architect" or "Data Scientist" — ranked below true in-role matches
    but above the off-role floor, and above the default min_relevance filter.)
  - Otherwise (off-role)             → 5   (the off-role killer).
  - Empty query                      → 50 for everything (neutral; don't drop anything).

The three bands never overlap: off-role 5 < related 35–49 < in-role 50–100, so a
related-role title can never outrank a true in-role title.

Matching tolerates common word-form suffixes (`engineer` matches `Engineering`,
`developer` matches `developers`) for alphabetic terms of length ≥ 4 — short
abbreviations (`go`, `ai`, `be`) are NOT suffix-expanded so `go` never matches
`going`.

Scoring is **title-only**. The description is intentionally NOT used: a
description boost silently rewarded boards that return JD text (Adzuna, Indeed)
and penalized search-only boards (LinkedIn, We Work Remotely) whose postings
have no description — so two identical roles ranked differently purely by
source. The `description` parameter is kept for signature stability but unused.

The head noun is the LAST query token that belongs to ROLE_NOUNS.
If no query token is a role noun, the last token is used as the head noun.
All remaining tokens are modifiers.

Synonyms: every term (head noun and modifiers) is expanded through
SYNONYM_GROUPS before matching, so "ai" matches an "ML Engineer" title,
"engineer" matches an "AI Developer" title, "frontend" matches "front-end",
etc. Matching is whole-word (\\b boundaries) and case-insensitive so short
terms like "ai" don't hit substrings inside unrelated words ("available",
"training", "email"). Multi-word synonyms ("machine learning") are matched as
phrases in the target text.
"""

import re

# Common role head nouns.  Keep this as a flat set — easy to extend.
ROLE_NOUNS: frozenset[str] = frozenset(
    {
        "engineer",
        "developer",
        "scientist",
        "manager",
        "designer",
        "analyst",
        "architect",
        "lead",
        "consultant",
        "administrator",
        "specialist",
        "programmer",
        "director",
        "coordinator",
        "recruiter",
        "writer",
        "researcher",
        "strategist",
        "advisor",
        "intern",
    }
)

# Synonym groups: every term in a group is treated as equivalent for matching.
# Terms are lowercase; multi-word phrases are matched as phrases in the target.
# Keep groups focused — over-broad synonyms cause off-role false positives.
SYNONYM_GROUPS: tuple[frozenset[str], ...] = tuple(
    frozenset(g)
    for g in (
        # --- AI / ML family ---
        {
            "ai",
            "a.i.",
            "artificial intelligence",
            "ml",
            "machine learning",
            "deep learning",
            "dl",
        },
        {"nlp", "natural language processing"},
        {"cv", "computer vision"},
        {
            "genai",
            "gen ai",
            "generative ai",
            "llm",
            "llms",
            "large language model",
            "large language models",
        },
        {"mlops", "ml ops"},
        {"data science", "ds"},
        # --- Seniority ---
        {"senior", "sr", "sr.", "snr"},
        {"junior", "jr", "jr.", "entry", "entry-level", "entry level", "associate"},
        {"principal", "staff", "distinguished"},
        # --- Role-noun equivalents (engineer family) ---
        {"engineer", "developer", "dev", "programmer", "coder"},
        # --- Stack position ---
        {"frontend", "front-end", "front end", "fe", "ui"},
        {"backend", "back-end", "back end", "be"},
        {"fullstack", "full-stack", "full stack"},
        {"devops", "dev ops", "sre", "site reliability"},
        {"qa", "quality assurance", "sdet"},
        {"ux", "user experience"},
        {"ui/ux", "ui ux"},
        # --- Product / management ---
        {"pm", "product manager", "product management"},
        {"product owner", "po"},
        {"em", "engineering manager"},
        {"tpm", "technical program manager", "technical project manager"},
        # --- Platforms / clouds ---
        {"aws", "amazon web services"},
        {"gcp", "google cloud", "google cloud platform"},
        {"azure", "microsoft azure"},
        {"kubernetes", "k8s"},
        {"infrastructure", "infra"},
        # --- Languages ---
        {"javascript", "js"},
        {"typescript", "ts"},
        {"python", "py"},
        {"golang", "go"},
        {"database", "db"},
        # --- Domains ---
        {"cybersecurity", "cyber security", "infosec", "information security"},
        {"software", "sw"},
        {"hardware", "hw"},
        {"mobile", "ios/android"},
        {"site reliability engineer", "sre"},
    )
)

# Reverse lookup: term -> the full group it belongs to (including itself).
SYNONYM_LOOKUP: dict[str, frozenset[str]] = {
    term: group for group in SYNONYM_GROUPS for term in group
}

# Technical IC/role family used for the soft related-role tier. When the query's
# head noun is one of these and the title carries a DIFFERENT member, the posting
# scores in the related band (below in-role, above the off-role floor) instead of
# flooring. Deliberately excludes management/ops/creative nouns (manager, director,
# recruiter, designer, …) so "engineer" doesn't softly match "Recruiter".
TECH_ROLE_FAMILY: frozenset[str] = frozenset(
    {
        "engineer",
        "developer",
        "programmer",
        "scientist",
        "architect",
        "researcher",
        "lead",
    }
)
# NOTE: deliberately omits generic nouns like "specialist" / "analyst" / "manager"
# — they appear in unrelated roles (Marketing Specialist, Financial Analyst) and
# would pollute the related tier. "lead" is kept (Data Science Lead) by intent.

# Scoring constants — named so the test engineer can import them.
_BASE_SCORE = 50
_TITLE_MODIFIER_BOOST = 10
_OFF_ROLE_FLOOR = 5
_NEUTRAL_SCORE = 50
# Soft related-role tier (different-but-related role noun in title).
_RELATED_ROLE_SCORE = 35
_RELATED_MODIFIER_BOOST = 5
_RELATED_ROLE_CAP = 49  # keep related strictly below the in-role base of 50

# Suffix tolerance for whole-word matching: lets "engineer" match "Engineering"
# / "engineers". Only applied to alphabetic terms of length ≥ 4 so short
# abbreviations ("go", "ai", "be") never match "going" / "available" / "being".
_MIN_SUFFIX_LEN = 4
_SUFFIX_RE = r"(?:s|ed|ing)?"


def _word_in_text(word: str, text: str) -> bool:
    """Return True if *word* appears as a whole word/phrase in *text* (case-insensitive).

    Alphabetic terms of length ≥ 4 also match common inflected forms
    (plural / -ed / -ing), so "engineer" matches "Engineering".
    """
    pattern = re.escape(word)
    if len(word) >= _MIN_SUFFIX_LEN and word.isalpha():
        pattern += _SUFFIX_RE
    return bool(re.search(r"\b" + pattern + r"\b", text, re.IGNORECASE))


def _expand(term: str) -> frozenset[str]:
    """Return *term* plus all its synonyms (lowercased)."""
    return SYNONYM_LOOKUP.get(term, frozenset({term}))


def _term_in_text(term: str, text: str) -> bool:
    """True if *term* or any of its synonyms appears as a whole word/phrase in *text*."""
    return any(_word_in_text(syn, text) for syn in _expand(term))


def _title_has_related_role(title: str, exclude: str) -> bool:
    """True if *title* carries a tech role noun OTHER than *exclude*'s family.

    Used for the soft related-role tier: the head noun itself was already found
    absent from the title, so any family member present here is a *different*
    role (Architect / Scientist / Lead …).
    """
    exclude_group = _expand(exclude)
    return any(
        role not in exclude_group and _term_in_text(role, title) for role in TECH_ROLE_FAMILY
    )


def _parse_query(query: str) -> tuple[str, list[str]]:
    """Split *query* into (head_noun, modifiers).

    The head noun is the last token that appears in ROLE_NOUNS.
    If no token is a role noun, the last token is the head noun.
    All other tokens are modifiers.
    """
    tokens = query.lower().split()
    if not tokens:
        return "", []

    # Find the last token that is a role noun.
    head_noun = ""
    head_index = -1
    for i, token in enumerate(tokens):
        if token in ROLE_NOUNS:
            head_noun = token
            head_index = i

    if not head_noun:
        # No recognised role noun — treat the last token as head noun.
        head_noun = tokens[-1]
        head_index = len(tokens) - 1

    modifiers = [t for i, t in enumerate(tokens) if i != head_index]
    return head_noun, modifiers


def score_relevance(title: str, description: str, query: str) -> int:
    """Score a job posting's relevance to *query* on a 0–100 scale.

    Parameters
    ----------
    title:       The job posting title (untrusted; treated as plain text).
    description: Unused — kept for signature stability (see module docstring).
    query:       The user's search query string.

    Returns
    -------
    int in [0, 100].
    """
    query = query.strip()
    if not query:
        return _NEUTRAL_SCORE

    head_noun, modifiers = _parse_query(query)

    if not head_noun:
        return _NEUTRAL_SCORE

    # Gate: head noun (or a synonym) must appear in the title.
    if not _term_in_text(head_noun, title):
        # Soft related-role tier: the head noun is a tech role and the title
        # carries a *different* tech role noun (Architect / Scientist / Lead …).
        # Score below the in-role base but above the off-role floor.
        if head_noun in TECH_ROLE_FAMILY and _title_has_related_role(title, head_noun):
            score = _RELATED_ROLE_SCORE
            for mod in modifiers:
                if _term_in_text(mod, title):
                    score += _RELATED_MODIFIER_BOOST
            return min(score, _RELATED_ROLE_CAP)
        return _OFF_ROLE_FLOOR

    # Head noun is in title — start from base and boost per modifier in title.
    score = _BASE_SCORE
    for mod in modifiers:
        if _term_in_text(mod, title):
            score += _TITLE_MODIFIER_BOOST

    return min(score, 100)
