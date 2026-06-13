"""rendercv integration: build YAML models and render PDFs."""

import glob
import logging
import subprocess
import sys
import tempfile
from pathlib import Path

import phonenumbers
import yaml
from rendercv.exception import RenderCVUserValidationError
from rendercv.schema.rendercv_model_builder import build_rendercv_dictionary_and_model

logger = logging.getLogger(__name__)

_PLACEHOLDER_NAME = "Candidate"

# rendercv strictly validates some fields (phone must be a valid international
# number, email a valid address, dates well-formed). LLM-extracted data often
# violates these (e.g. a local-format phone with no country code), and a single
# bad field makes rendercv reject the WHOLE document — silently dropping us to
# the plain reportlab fallback. _make_renderable() repairs the data so the
# rendercv template is actually used. Region inference keeps a phone when we can,
# rather than discarding it.
_COUNTRY_TO_REGION: dict[str, str] = {
    "india": "IN",
    "united states": "US",
    "usa": "US",
    "u.s.a": "US",
    "united kingdom": "GB",
    "u.k": "GB",
    " uk": "GB",
    "england": "GB",
    "canada": "CA",
    "australia": "AU",
    "germany": "DE",
    "france": "FR",
    "spain": "ES",
    "italy": "IT",
    "netherlands": "NL",
    "ireland": "IE",
    "singapore": "SG",
    "japan": "JP",
    "china": "CN",
    "brazil": "BR",
    "mexico": "MX",
    "pakistan": "PK",
    "bangladesh": "BD",
    "nigeria": "NG",
    "south africa": "ZA",
    "new zealand": "NZ",
    "switzerland": "CH",
    "sweden": "SE",
    "poland": "PL",
    "portugal": "PT",
    "united arab emirates": "AE",
    "uae": "AE",
}


class RenderError(Exception):
    pass


# RenderCV themes installed with the package. Used to validate a user-selected
# theme before it is swapped into a stored document for rendering.
RENDERCV_THEMES: tuple[str, ...] = (
    "engineeringresumes",
    "engineeringclassic",
    "classic",
    "harvard",
    "sb2nov",
    "moderncv",
    "ember",
    "ink",
    "opal",
)


def apply_theme(yaml_str: str, theme: str) -> str:
    """Return *yaml_str* with its ``design.theme`` replaced by *theme*.

    Lets a stored document (built with the default theme at prepare time) be
    re-rendered under a different theme at download time without re-tailoring.
    Returns the original string unchanged if it can't be parsed.
    """
    try:
        document = yaml.safe_load(yaml_str)
    except yaml.YAMLError as exc:
        logger.warning("rendercv: could not parse YAML to apply theme: %s", exc)
        return yaml_str
    if not isinstance(document, dict):
        return yaml_str
    design = document.get("design")
    if not isinstance(design, dict):
        design = {}
        document["design"] = design
    design["theme"] = theme
    return yaml.dump(document, allow_unicode=True, sort_keys=False)


def _guess_region(cv: dict) -> str | None:
    text = str(cv.get("location", "")).lower()
    for name, region in _COUNTRY_TO_REGION.items():
        if name in text:
            return region
    return None


def _normalize_phone(raw: object, region: str | None) -> str | None:
    """Return an E.164 phone string rendercv accepts, or None if impossible."""
    candidate = str(raw).strip()
    if not candidate:
        return None
    # Try with no region first (works when already +CC), then the inferred region.
    for reg in (None, region):
        try:
            parsed = phonenumbers.parse(candidate, reg)
        except phonenumbers.NumberParseException:
            continue
        if phonenumbers.is_valid_number(parsed):
            return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    return None


def _delete_at(document: dict, location: tuple) -> bool:
    """Delete the leaf at *location* (a rendercv schema path). Returns True if removed."""
    if not location:
        return False
    node: object = document
    for key in location[:-1]:
        if isinstance(node, dict):
            node = node.get(key)
        elif isinstance(node, list) and isinstance(key, int) and 0 <= key < len(node):
            node = node[key]
        else:
            return False
        if node is None:
            return False
    last = location[-1]
    if isinstance(node, dict) and last in node:
        node.pop(last)
        return True
    if isinstance(node, list) and isinstance(last, int) and 0 <= last < len(node):
        node.pop(last)
        return True
    return False


def _make_renderable(document: dict) -> dict:
    """Repair a {cv, design} document so rendercv validation passes.

    Normalizes the phone, converts year-only dates to literal date fields (so
    RenderCV stops inventing a month), then iteratively drops any leaf field
    rendercv still rejects. Mutates and returns *document*.
    """
    cv = document.get("cv")
    if isinstance(cv, dict) and cv.get("phone"):
        normalized = _normalize_phone(cv["phone"], _guess_region(cv))
        if normalized:
            cv["phone"] = normalized
        else:
            logger.info("rendercv: dropping unparseable phone %r", cv["phone"])
            cv.pop("phone", None)

    # Convert year-only start_date/end_date to a literal ``date`` field BEFORE
    # rendercv validation.  RenderCV parses a bare "2011" as January 2011 and
    # renders "Jan 2011"; a non-ISO string is rendered verbatim.  This must run
    # before the validation loop so the repaired document is what gets validated.
    if isinstance(cv, dict):
        _normalize_entry_dates(cv)

    for _ in range(10):
        yaml_str = yaml.dump(document, allow_unicode=True, sort_keys=False)
        try:
            build_rendercv_dictionary_and_model(yaml_str)
            return document
        except RenderCVUserValidationError as exc:
            removed = False
            for err in exc.validation_errors:
                location = getattr(err, "schema_location", None)
                if location and _delete_at(document, tuple(location)):
                    logger.info(
                        "rendercv: dropped invalid field %s (%s)",
                        ".".join(str(p) for p in location),
                        getattr(err, "message", ""),
                    )
                    removed = True
            if not removed:
                break
        except Exception as exc:  # noqa: BLE001 — validation helper must never raise
            logger.warning("rendercv: validation probe failed: %s", exc)
            break
    return document


def build_resume_yaml(cv: dict, theme: str) -> str:
    """Merge a rendercv cv dict with a design block and return a YAML string.

    Ensures the required ``name`` key is always present.
    """
    if not cv.get("name"):
        cv = dict(cv)
        cv["name"] = _PLACEHOLDER_NAME

    document = _make_renderable(
        {
            "cv": cv,
            "design": {"theme": theme},
        }
    )
    return yaml.dump(document, allow_unicode=True, sort_keys=False)


def build_cover_letter_yaml(
    contact: dict,
    paragraphs: list[str],
    theme: str,
) -> str:
    """Build a rendercv YAML string that renders a cover letter as a PDF.

    rendercv has no native cover letter type, so we model it as a CV whose
    only section is a list of plain-string (TextEntry) paragraphs. The name
    and contact fields come from ``contact``.
    """
    cv: dict = {}

    # Copy recognised contact keys in rendercv order.
    for key in ("name", "headline", "location", "email", "phone", "website"):
        if contact.get(key):
            cv[key] = contact[key]

    if contact.get("social_networks"):
        cv["social_networks"] = contact["social_networks"]

    if not cv.get("name"):
        cv["name"] = _PLACEHOLDER_NAME

    cv["sections"] = {"Cover Letter": paragraphs}

    document = _make_renderable(
        {
            "cv": cv,
            "design": {"theme": theme},
        }
    )
    return yaml.dump(document, allow_unicode=True, sort_keys=False)


def render_pdf(yaml_str: str) -> bytes:
    """Write *yaml_str* to a temp file, run rendercv, and return the PDF bytes.

    Raises ``RenderError`` if rendercv exits non-zero or produces no PDF.
    """
    # Repair the document first so rows stored before _make_renderable existed
    # (or any field rendercv rejects) still render the template instead of
    # erroring into the caller's plain-text fallback.
    try:
        document = yaml.safe_load(yaml_str)
        if isinstance(document, dict) and "cv" in document:
            yaml_str = yaml.dump(_make_renderable(document), allow_unicode=True, sort_keys=False)
    except yaml.YAMLError as exc:
        logger.warning("rendercv: could not pre-parse YAML for repair: %s", exc)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir) / "input.yaml"
        tmp_path.write_text(yaml_str, encoding="utf-8")

        outdir = Path(tmpdir) / "out"
        outdir.mkdir()

        cmd = [
            sys.executable,
            "-m",
            "rendercv",
            "render",
            str(tmp_path),
            "-o",
            str(outdir),
            "-nomd",
            "-nohtml",
            "-nopng",
            # NOTE: intentionally NOT passing -q. With -q, rendercv suppresses its
            # validation-error output, so a rejected document failed silently into
            # the reportlab fallback with an empty stderr — hard to diagnose.
        ]

        logger.debug("rendercv: running %s", " ".join(cmd))
        result = subprocess.run(cmd, capture_output=True, timeout=120)

        if result.returncode != 0:
            stderr = result.stderr.decode(errors="replace").strip()
            stdout = result.stdout.decode(errors="replace").strip()
            logger.error(
                "rendercv: non-zero exit %d\nstdout: %s\nstderr: %s",
                result.returncode,
                stdout,
                stderr,
            )
            raise RenderError(f"rendercv exited {result.returncode}: {stderr or stdout}")

        pdf_files = glob.glob(str(outdir / "*.pdf"))
        if not pdf_files:
            logger.error("rendercv: no PDF produced in %s", outdir)
            raise RenderError("rendercv produced no PDF output")

        pdf_path = pdf_files[0]
        logger.debug("rendercv: produced %s", pdf_path)
        return Path(pdf_path).read_bytes()


# RenderCV month abbreviations (June/July are full; Sept has a 't').
_RENDERCV_MONTHS = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "June",
    "July",
    "Aug",
    "Sept",
    "Oct",
    "Nov",
    "Dec",
)


def _format_single_date(value: str | None) -> str:
    """Format a single date value the same way RenderCV would display it.

    - None / empty string         → ""
    - "present" / "ongoing"       → "present"
    - ISO YYYY-MM or YYYY-MM-DD   → "Mon YYYY"  (RenderCV abbreviation)
    - Bare YYYY (4 digits)        → the year string unchanged ("2011")
    - Anything else (free text)   → returned as-is, stripped of trailing space
                                    (the trailing-space trick used in RenderCV
                                    YAML is invisible to readers here)
    """
    if not value:
        return ""
    value = str(value)
    stripped = value.strip()
    if not stripped:
        return ""
    if stripped.lower() in ("present", "ongoing"):
        return "present"
    # ISO YYYY-MM or YYYY-MM-DD
    parts = stripped.split("-")
    if len(parts) >= 2 and parts[0].isdigit() and len(parts[0]) == 4 and parts[1].isdigit():
        year = int(parts[0])
        month = int(parts[1])
        if 1 <= month <= 12:
            return f"{_RENDERCV_MONTHS[month - 1]} {year}"
    # Bare YYYY
    if stripped.isdigit() and len(stripped) == 4:
        return stripped
    # Free text (e.g. "Fall 2011") — strip trailing space used in YAML trick
    return stripped


def _format_date_display(entry: dict) -> str:
    """Produce the human-readable date string for an entry, matching RenderCV's logic.

    Checks for a ``date`` field first (RenderCV precedence), then falls back to
    ``start_date`` / ``end_date``.  En-dash (U+2013) with surrounding spaces
    matches RenderCV's ``date_range`` default "START_DATE – END_DATE".
    """
    date_val = entry.get("date")
    if date_val is not None:
        return _format_single_date(str(date_val))

    start = entry.get("start_date")
    end = entry.get("end_date")
    if start and end:
        return f"{_format_single_date(str(start))} – {_format_single_date(str(end))}"
    if end:
        return _format_single_date(str(end))
    if start:
        return f"{_format_single_date(str(start))} – present"
    return ""


def _normalize_entry_dates(cv: dict) -> None:
    """Walk every section entry and convert year-only dates to a literal ``date`` field.

    RenderCV parses a bare 4-digit year (e.g. ``end_date: "2011"``) as
    January of that year and renders "Jan 2011".  A non-ISO string is rendered
    verbatim, so we convert year-precision entries to a single ``date`` field.

    Trailing-space trick: a bare "2011" is still a 4-digit string that RenderCV
    would parse as a date.  Appending a single trailing space ("2011 ") makes it
    non-ISO, so RenderCV renders it literally; Typst trims the space visually.

    Rules applied to entries that use start_date / end_date (NOT already a date field):
      - start(YYYY) + end(YYYY)  → date = "YYYY – YYYY"  (en-dash; non-ISO verbatim)
      - end(YYYY) only           → date = "YYYY "         (trailing space; renders "YYYY")
      - start(YYYY) only         → date = "YYYY – present"
    If ANY part is month-precision (YYYY-MM / YYYY-MM-DD), leave start_date/end_date
    untouched so RenderCV renders "Mon YYYY" normally.
    """

    def _is_year_only(val: str) -> bool:
        return val.isdigit() and len(val) == 4

    def _is_month_precision(val: str) -> bool:
        parts = val.split("-")
        return len(parts) >= 2 and parts[0].isdigit() and len(parts[0]) == 4 and parts[1].isdigit()

    def _is_present(val: str) -> bool:
        return val.lower() in ("present", "ongoing")

    sections = cv.get("sections", {})
    if not isinstance(sections, dict):
        return

    for entries in sections.values():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            # Skip entries that already use the free-text date field.
            if "date" in entry:
                continue
            start = str(entry.get("start_date", "")).strip()
            end = str(entry.get("end_date", "")).strip()
            if not start and not end:
                continue

            # Check precision of each present value.
            start_is_year = bool(start) and (_is_year_only(start) or _is_present(start))
            start_is_month = bool(start) and _is_month_precision(start)
            end_is_year = bool(end) and (_is_year_only(end) or _is_present(end))
            end_is_month = bool(end) and _is_month_precision(end)

            # If any part is month-precision, leave as-is for RenderCV.
            if start_is_month or end_is_month:
                continue

            # All present parts are year-precision (or "present") — convert to literal date.
            if start_is_year and end_is_year:
                if _is_present(end):
                    # "2021 – present" is already non-ISO; no trailing space needed.
                    entry["date"] = f"{start} – present"
                else:
                    # "2008 – 2011" is non-ISO; RenderCV renders it verbatim.
                    entry["date"] = f"{start} – {end}"
                entry.pop("start_date", None)
                entry.pop("end_date", None)
            elif end_is_year and not start:
                # end-only year: trailing space forces verbatim rendering in RenderCV.
                # Without it, RenderCV parses "2011" as a date and shows "Jan 2011".
                entry["date"] = f"{end} "
                entry.pop("start_date", None)
                entry.pop("end_date", None)
            elif start_is_year and not end:
                # start-only year with no end date.
                entry["date"] = f"{start} – present"
                entry.pop("start_date", None)
                entry.pop("end_date", None)


def cv_to_text(cv: dict) -> str:
    """Deterministic plain-text flattening of a rendercv cv dict.

    Produces a stable, readable plain-text resume suitable for the difflib
    diff view and DOCX export. Format:

        <Name>
        <contact line>

        SECTION NAME
        <entries...>

    Entry types handled:
    - ExperienceEntry: "Position — Company (Mar 2021 – May 2023, Location)"  + "- highlight" lines
    - EducationEntry:  "Degree in Area — Institution (2011)" + highlights
    - OneLineEntry:    "Label: Details"
    - Plain strings:   rendered as-is (TextEntry / paragraph)
    - Other dicts:     best-effort "key: value" serialisation
    """
    lines: list[str] = []

    name = cv.get("name", "")
    if name:
        lines.append(name)

    contact_parts: list[str] = []
    for key in ("headline", "location", "email", "phone", "website"):
        val = cv.get(key)
        if val:
            contact_parts.append(str(val))
    if cv.get("social_networks"):
        for sn in cv["social_networks"]:
            network = sn.get("network", "")
            username = sn.get("username", "")
            if network and username:
                contact_parts.append(f"{network}: {username}")
    if contact_parts:
        lines.append(" | ".join(contact_parts))

    sections: dict = cv.get("sections", {})
    for section_name, entries in sections.items():
        lines.append("")
        lines.append(section_name.upper())

        for entry in entries:
            if isinstance(entry, str):
                lines.append(entry)
                continue

            if not isinstance(entry, dict):
                lines.append(str(entry))
                continue

            # ExperienceEntry
            if "company" in entry and "position" in entry:
                date_str = _format_date_display(entry)
                location = entry.get("location", "")
                loc_str = f", {location}" if location else ""
                header = f"{entry['position']} — {entry['company']}"
                if date_str:
                    header += f" ({date_str}{loc_str})"
                lines.append(header)
                summary = entry.get("summary", "")
                if summary:
                    lines.append(summary)
                for h in entry.get("highlights", []):
                    lines.append(f"- {h}")

            # EducationEntry
            elif "institution" in entry:
                date_str = _format_date_display(entry)
                degree = entry.get("degree", "")
                area = entry.get("area", "")
                degree_str = f"{degree} in {area}" if degree and area else (degree or area)
                header = f"{degree_str} — {entry['institution']}"
                if date_str:
                    header += f" ({date_str})"
                lines.append(header)
                for h in entry.get("highlights", []):
                    lines.append(f"- {h}")

            # OneLineEntry
            elif "label" in entry and "details" in entry:
                lines.append(f"{entry['label']}: {entry['details']}")

            # NormalEntry / generic
            else:
                name_val = entry.get("name", "")
                if name_val:
                    lines.append(str(name_val))
                for h in entry.get("highlights", []):
                    lines.append(f"- {h}")
                # Remaining scalar keys as "key: value"
                for k, v in entry.items():
                    if k not in ("name", "highlights") and isinstance(v, (str, int, float)):
                        lines.append(f"{k}: {v}")

    return "\n".join(lines)
