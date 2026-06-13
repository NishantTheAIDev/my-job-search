"""Tests for rendercv_service: cv_to_text, build_resume_yaml, build_cover_letter_yaml,
and render_pdf (one real subprocess render + one mocked RenderError path)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from backend.services.rendercv_service import (
    RenderError,
    _format_date_display,
    _format_single_date,
    _normalize_entry_dates,
    build_cover_letter_yaml,
    build_resume_yaml,
    cv_to_text,
    render_pdf,
)

# ---------------------------------------------------------------------------
# Sample cv fixture used across multiple tests
# ---------------------------------------------------------------------------

SAMPLE_CV = {
    "name": "Jane Smith",
    "headline": "Senior Software Engineer",
    "location": "San Francisco, CA",
    "email": "jane@example.com",
    "phone": "+1-555-123-4567",
    "website": "https://janesmith.dev",
    "social_networks": [{"network": "LinkedIn", "username": "janesmith"}],
    "sections": {
        "Summary": ["Experienced engineer with 8 years building distributed systems."],
        "Experience": [
            {
                "company": "Acme Corp",
                "position": "Staff Engineer",
                "start_date": "2020-03",
                "end_date": "present",
                "location": "Remote",
                "highlights": [
                    "Led migration to Kubernetes reducing infra costs by 30%",
                    "Mentored 5 junior engineers",
                ],
            },
            {
                "company": "Beta Ltd",
                "position": "Software Engineer",
                "start_date": "2016",
                "end_date": "2020",
                "highlights": ["Built REST APIs serving 10M requests/day"],
            },
        ],
        "Education": [
            {
                "institution": "MIT",
                "degree": "BS",
                "area": "Computer Science",
                "start_date": "2012",
                "end_date": "2016",
                "highlights": ["GPA: 3.9"],
            }
        ],
        "Skills": [
            {"label": "Languages", "details": "Python, Go, TypeScript"},
            {"label": "Platforms", "details": "AWS, Kubernetes, Docker"},
        ],
    },
}


# ---------------------------------------------------------------------------
# cv_to_text
# ---------------------------------------------------------------------------


class TestCvToText:
    def test_includes_name(self):
        text = cv_to_text(SAMPLE_CV)
        assert "Jane Smith" in text

    def test_includes_contact_fields(self):
        text = cv_to_text(SAMPLE_CV)
        assert "jane@example.com" in text
        assert "San Francisco, CA" in text
        assert "+1-555-123-4567" in text
        assert "https://janesmith.dev" in text

    def test_includes_social_network(self):
        text = cv_to_text(SAMPLE_CV)
        assert "LinkedIn" in text
        assert "janesmith" in text

    def test_section_headings_uppercased(self):
        text = cv_to_text(SAMPLE_CV)
        assert "EXPERIENCE" in text
        assert "EDUCATION" in text
        assert "SKILLS" in text
        assert "SUMMARY" in text

    def test_experience_entry_format(self):
        text = cv_to_text(SAMPLE_CV)
        # Position — Company (Mon YYYY – present, location)
        assert "Staff Engineer — Acme Corp" in text
        assert "Mar 2020 – present" in text
        assert "Remote" in text

    def test_experience_highlights_prefixed(self):
        text = cv_to_text(SAMPLE_CV)
        assert "- Led migration to Kubernetes" in text
        assert "- Mentored 5 junior engineers" in text

    def test_education_entry_format(self):
        text = cv_to_text(SAMPLE_CV)
        assert "BS in Computer Science — MIT" in text
        # Year-only range: both sides are bare years, shown as "2012 – 2016"
        assert "2012 – 2016" in text
        assert "- GPA: 3.9" in text

    def test_one_line_entry_format(self):
        text = cv_to_text(SAMPLE_CV)
        assert "Languages: Python, Go, TypeScript" in text
        assert "Platforms: AWS, Kubernetes, Docker" in text

    def test_plain_string_entry_rendered(self):
        text = cv_to_text(SAMPLE_CV)
        assert "Experienced engineer with 8 years building distributed systems." in text

    def test_is_deterministic(self):
        """Same input always produces the same output."""
        assert cv_to_text(SAMPLE_CV) == cv_to_text(SAMPLE_CV)

    def test_empty_cv_returns_empty_string(self):
        assert cv_to_text({}) == ""

    def test_cv_without_name_omits_name_line(self):
        cv = {"sections": {"Summary": ["Just a summary."]}}
        text = cv_to_text(cv)
        assert text.startswith("\nSUMMARY") or "SUMMARY" in text
        # No stray empty name
        assert text.strip() != ""

    def test_missing_end_date_shows_present(self):
        cv = {
            "sections": {
                "Experience": [
                    {
                        "company": "X Corp",
                        "position": "Engineer",
                        "start_date": "2022",
                    }
                ]
            }
        }
        text = cv_to_text(cv)
        assert "2022 – present" in text

    def test_no_dates_produces_no_date_range(self):
        cv = {
            "sections": {
                "Experience": [
                    {
                        "company": "X Corp",
                        "position": "Engineer",
                    }
                ]
            }
        }
        text = cv_to_text(cv)
        # Should still render the position line without a date range
        assert "Engineer — X Corp" in text
        # No stray parentheses or en-dash for date range
        assert " – " not in text


# ---------------------------------------------------------------------------
# build_resume_yaml
# ---------------------------------------------------------------------------


class TestBuildResumeYaml:
    def test_returns_valid_yaml(self):
        yaml_str = build_resume_yaml(SAMPLE_CV, "classic")
        doc = yaml.safe_load(yaml_str)
        assert isinstance(doc, dict)

    def test_contains_design_and_theme(self):
        yaml_str = build_resume_yaml(SAMPLE_CV, "classic")
        doc = yaml.safe_load(yaml_str)
        assert "design" in doc
        assert doc["design"]["theme"] == "classic"

    def test_contains_cv_name(self):
        yaml_str = build_resume_yaml(SAMPLE_CV, "classic")
        doc = yaml.safe_load(yaml_str)
        assert doc["cv"]["name"] == "Jane Smith"

    def test_placeholder_name_when_cv_has_no_name(self):
        cv_no_name = {k: v for k, v in SAMPLE_CV.items() if k != "name"}
        yaml_str = build_resume_yaml(cv_no_name, "classic")
        doc = yaml.safe_load(yaml_str)
        # Should inject the placeholder, not leave it empty
        assert doc["cv"]["name"]
        assert doc["cv"]["name"] == "Candidate"

    def test_does_not_mutate_original_cv(self):
        cv_no_name = {"sections": {}}
        build_resume_yaml(cv_no_name, "classic")
        # Original dict should not have "name" added to it
        assert "name" not in cv_no_name

    def test_theme_is_configurable(self):
        for theme in ("classic", "sb2nov", "engineeringresumes"):
            yaml_str = build_resume_yaml(SAMPLE_CV, theme)
            doc = yaml.safe_load(yaml_str)
            assert doc["design"]["theme"] == theme


# ---------------------------------------------------------------------------
# build_cover_letter_yaml
# ---------------------------------------------------------------------------


class TestBuildCoverLetterYaml:
    def test_returns_valid_yaml(self):
        contact = {"name": "Jane Smith", "email": "jane@example.com"}
        paragraphs = ["I am excited to apply.", "I have 8 years of experience."]
        yaml_str = build_cover_letter_yaml(contact, paragraphs, "classic")
        doc = yaml.safe_load(yaml_str)
        assert isinstance(doc, dict)

    def test_paragraphs_in_cover_letter_section(self):
        contact = {"name": "Jane Smith", "email": "jane@example.com"}
        paragraphs = ["First paragraph.", "Second paragraph."]
        yaml_str = build_cover_letter_yaml(contact, paragraphs, "classic")
        doc = yaml.safe_load(yaml_str)
        sections = doc["cv"]["sections"]
        # Exactly one section containing our paragraphs
        all_paras = [p for paras in sections.values() for p in paras]
        assert "First paragraph." in all_paras
        assert "Second paragraph." in all_paras

    def test_contact_fields_copied(self):
        contact = {
            "name": "Jane Smith",
            "email": "jane@example.com",
            "phone": "+1-415-555-2671",
            "location": "SF",
        }
        yaml_str = build_cover_letter_yaml(contact, ["Para."], "classic")
        doc = yaml.safe_load(yaml_str)
        cv = doc["cv"]
        assert cv["name"] == "Jane Smith"
        assert cv["email"] == "jane@example.com"
        # _make_renderable normalizes valid phones to E.164 so rendercv accepts them.
        assert cv["phone"] == "+14155552671"
        assert cv["location"] == "SF"

    def test_placeholder_name_when_contact_has_no_name(self):
        yaml_str = build_cover_letter_yaml({}, ["Para."], "classic")
        doc = yaml.safe_load(yaml_str)
        assert doc["cv"]["name"] == "Candidate"

    def test_design_block_present(self):
        yaml_str = build_cover_letter_yaml({"name": "X"}, ["P."], "sb2nov")
        doc = yaml.safe_load(yaml_str)
        assert doc["design"]["theme"] == "sb2nov"

    def test_social_networks_copied(self):
        contact = {
            "name": "Jane",
            "social_networks": [{"network": "GitHub", "username": "janedev"}],
        }
        yaml_str = build_cover_letter_yaml(contact, ["Hi."], "classic")
        doc = yaml.safe_load(yaml_str)
        assert doc["cv"]["social_networks"] == [{"network": "GitHub", "username": "janedev"}]


# ---------------------------------------------------------------------------
# _make_renderable — repair LLM data so rendercv's strict validation passes.
# Regression guard: a single invalid field (e.g. a local-format phone) used to
# make rendercv reject the whole document, silently falling back to reportlab.
# ---------------------------------------------------------------------------


class TestMakeRenderable:
    def test_local_phone_normalized_using_location_region(self):
        # Indian local-format phone with no country code → E.164 via location hint.
        cv = {
            "name": "Nishant Singh",
            "location": "Pune, Maharashtra, India",
            "phone": "088743 50651",
            "sections": {"Summary": ["Engineer."]},
        }
        doc = yaml.safe_load(build_resume_yaml(cv, "engineeringresumes"))
        assert doc["cv"]["phone"] == "+918874350651"

    def test_unparseable_phone_dropped_not_fatal(self):
        cv = {"name": "A B", "phone": "n/a", "location": "Nowhere", "sections": {"S": ["x"]}}
        doc = yaml.safe_load(build_resume_yaml(cv, "engineeringresumes"))
        assert "phone" not in doc["cv"]

    @pytest.mark.slow
    def test_invalid_phone_document_still_renders_real_pdf(self):
        # End-to-end: the exact failure mode from production (local phone) must
        # now produce a real rendercv PDF, not raise RenderError.
        cv = {
            "name": "Nishant Singh",
            "location": "Pune, Maharashtra, India",
            "phone": "088743 50651",
            "email": "nishant@example.com",
            "sections": {"Summary": ["Senior AI/ML Engineer."]},
        }
        pdf = render_pdf(build_resume_yaml(cv, "engineeringresumes"))
        assert pdf[:5] == b"%PDF-"


# ---------------------------------------------------------------------------
# render_pdf — mocked subprocess (fast, deterministic)
# ---------------------------------------------------------------------------


class TestRenderPdfMocked:
    def _make_fake_run(self, returncode: int, write_pdf: bool = True):
        """Return a mock for subprocess.run that optionally writes a PDF file."""

        def fake_run(cmd, capture_output, timeout):
            if write_pdf:
                # The outdir is the directory passed after "-o" in cmd
                o_index = cmd.index("-o")
                outdir = Path(cmd[o_index + 1])
                pdf_path = outdir / "input.pdf"
                pdf_path.write_bytes(b"%PDF-1.4 fake content")
            result = MagicMock()
            result.returncode = returncode
            result.stderr = b""
            result.stdout = b""
            return result

        return fake_run

    def test_returns_bytes_starting_with_pdf_magic(self):
        with patch("subprocess.run", side_effect=self._make_fake_run(0, write_pdf=True)):
            yaml_str = build_resume_yaml(SAMPLE_CV, "classic")
            pdf_bytes = render_pdf(yaml_str)
        assert isinstance(pdf_bytes, bytes)
        assert pdf_bytes[:4] == b"%PDF"

    def test_nonzero_exit_raises_render_error(self):
        with patch("subprocess.run", side_effect=self._make_fake_run(1, write_pdf=False)):
            yaml_str = build_resume_yaml(SAMPLE_CV, "classic")
            with pytest.raises(RenderError, match="rendercv exited"):
                render_pdf(yaml_str)

    def test_no_pdf_produced_raises_render_error(self):
        """rendercv exits 0 but writes no PDF — should still raise RenderError."""
        with patch(
            "subprocess.run",
            side_effect=self._make_fake_run(0, write_pdf=False),
        ):
            yaml_str = build_resume_yaml(SAMPLE_CV, "classic")
            with pytest.raises(RenderError, match="no PDF"):
                render_pdf(yaml_str)

    def test_command_includes_required_flags(self):
        captured_cmd = []

        def fake_run(cmd, capture_output, timeout):
            captured_cmd.extend(cmd)
            # Write fake PDF so the function does not raise
            o_index = cmd.index("-o")
            outdir = Path(cmd[o_index + 1])
            (outdir / "out.pdf").write_bytes(b"%PDF-fake")
            result = MagicMock()
            result.returncode = 0
            result.stderr = b""
            result.stdout = b""
            return result

        with patch("subprocess.run", side_effect=fake_run):
            render_pdf("cv:\n  name: Test\ndesign:\n  theme: classic\n")

        assert "render" in captured_cmd
        assert "-nomd" in captured_cmd
        assert "-nohtml" in captured_cmd
        assert "-nopng" in captured_cmd
        assert "-o" in captured_cmd
        # -q is intentionally omitted so validation errors are not suppressed.
        assert "-q" not in captured_cmd

    def test_stderr_included_in_render_error_message(self):
        def fake_run(cmd, capture_output, timeout):
            result = MagicMock()
            result.returncode = 2
            result.stderr = b"Validation error: unknown field"
            result.stdout = b""
            return result

        with patch("subprocess.run", side_effect=fake_run):
            with pytest.raises(RenderError, match="Validation error"):
                render_pdf("bad: yaml\n")


# ---------------------------------------------------------------------------
# render_pdf — real subprocess (marked slow; skipped in fast CI)
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_render_pdf_real_subprocess_returns_pdf_bytes():
    """Shell out to rendercv for real and assert we get a valid PDF back.

    Requires rendercv[full] to be installed. Takes ~2-4 s.
    Mark with ``-m slow`` to run: ``uv run pytest -m slow``.
    """
    cv = {
        "name": "Test Candidate",
        "sections": {
            "Summary": ["A minimal resume for CI testing."],
        },
    }
    yaml_str = build_resume_yaml(cv, "engineeringresumes")
    pdf_bytes = render_pdf(yaml_str)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 0
    assert pdf_bytes[:4] == b"%PDF"


# ---------------------------------------------------------------------------
# _format_single_date
# ---------------------------------------------------------------------------


class TestFormatSingleDate:
    def test_none_returns_empty(self):
        assert _format_single_date(None) == ""

    def test_empty_string_returns_empty(self):
        assert _format_single_date("") == ""

    def test_present_lowercase(self):
        assert _format_single_date("present") == "present"

    def test_present_mixed_case(self):
        assert _format_single_date("Present") == "present"

    def test_ongoing(self):
        assert _format_single_date("ongoing") == "present"

    def test_iso_year_month(self):
        assert _format_single_date("2023-05") == "May 2023"

    def test_iso_year_month_march(self):
        assert _format_single_date("2021-03") == "Mar 2021"

    def test_iso_full_date_ignores_day(self):
        assert _format_single_date("2021-03-15") == "Mar 2021"

    def test_rendercv_month_abbreviations_june_full(self):
        assert _format_single_date("2020-06") == "June 2020"

    def test_rendercv_month_abbreviations_july_full(self):
        assert _format_single_date("2020-07") == "July 2020"

    def test_rendercv_month_abbreviations_sept(self):
        assert _format_single_date("2020-09") == "Sept 2020"

    def test_bare_year_unchanged(self):
        assert _format_single_date("2011") == "2011"

    def test_bare_year_2008(self):
        assert _format_single_date("2008") == "2008"

    def test_free_text_passthrough(self):
        assert _format_single_date("Fall 2011") == "Fall 2011"

    def test_free_text_with_trailing_space_stripped(self):
        # The trailing-space trick used in YAML is transparent to display.
        assert _format_single_date("2011 ") == "2011"


# ---------------------------------------------------------------------------
# _format_date_display
# ---------------------------------------------------------------------------


class TestFormatDateDisplay:
    def test_month_range(self):
        entry = {"start_date": "2021-03", "end_date": "2023-05"}
        assert _format_date_display(entry) == "Mar 2021 – May 2023"

    def test_year_end_only(self):
        entry = {"end_date": "2011"}
        assert _format_date_display(entry) == "2011"

    def test_year_range(self):
        entry = {"start_date": "2008", "end_date": "2011"}
        assert _format_date_display(entry) == "2008 – 2011"

    def test_start_only_shows_present(self):
        entry = {"start_date": "2022"}
        assert _format_date_display(entry) == "2022 – present"

    def test_explicit_present_end_date(self):
        entry = {"start_date": "2020-03", "end_date": "present"}
        assert _format_date_display(entry) == "Mar 2020 – present"

    def test_date_field_takes_precedence(self):
        entry = {"date": "2011 ", "start_date": "2008", "end_date": "2011"}
        # date field present → use it (trailing space stripped for display)
        assert _format_date_display(entry) == "2011"

    def test_no_dates_empty(self):
        assert _format_date_display({}) == ""


# ---------------------------------------------------------------------------
# cv_to_text — new date-rendering cases
# ---------------------------------------------------------------------------


class TestCvToTextDateRendering:
    def test_education_end_only_year_shows_bare_year(self):
        """UI diff must show "2011", not "Jan 2011"."""
        cv = {
            "sections": {
                "Education": [
                    {
                        "institution": "State University",
                        "degree": "BS",
                        "area": "Physics",
                        "end_date": "2011",
                    }
                ]
            }
        }
        text = cv_to_text(cv)
        assert "2011" in text
        assert "Jan" not in text
        assert "Jan 2011" not in text

    def test_experience_month_range(self):
        cv = {
            "sections": {
                "Experience": [
                    {
                        "company": "Acme",
                        "position": "Engineer",
                        "start_date": "2021-03",
                        "end_date": "2023-05",
                    }
                ]
            }
        }
        text = cv_to_text(cv)
        assert "Mar 2021 – May 2023" in text

    def test_year_range(self):
        cv = {
            "sections": {
                "Education": [
                    {
                        "institution": "Uni",
                        "degree": "BA",
                        "area": "History",
                        "start_date": "2008",
                        "end_date": "2011",
                    }
                ]
            }
        }
        text = cv_to_text(cv)
        assert "2008 – 2011" in text


# ---------------------------------------------------------------------------
# _normalize_entry_dates
# ---------------------------------------------------------------------------


class TestNormalizeEntryDates:
    def test_year_end_only_converted_to_date_with_trailing_space(self):
        cv = {
            "sections": {
                "Education": [
                    {
                        "institution": "MIT",
                        "degree": "BS",
                        "area": "CS",
                        "end_date": "2011",
                    }
                ]
            }
        }
        _normalize_entry_dates(cv)
        entry = cv["sections"]["Education"][0]
        assert "end_date" not in entry
        assert "start_date" not in entry
        # Trailing space trick: RenderCV renders "2011 " verbatim as "2011"
        assert entry["date"] == "2011 "

    def test_year_range_converted_to_date_en_dash(self):
        cv = {
            "sections": {
                "Education": [
                    {
                        "institution": "Uni",
                        "degree": "BA",
                        "area": "History",
                        "start_date": "2008",
                        "end_date": "2011",
                    }
                ]
            }
        }
        _normalize_entry_dates(cv)
        entry = cv["sections"]["Education"][0]
        assert "start_date" not in entry
        assert "end_date" not in entry
        assert entry["date"] == "2008 – 2011"

    def test_year_start_only_converted(self):
        cv = {
            "sections": {
                "Experience": [
                    {
                        "company": "X",
                        "position": "Dev",
                        "start_date": "2020",
                    }
                ]
            }
        }
        _normalize_entry_dates(cv)
        entry = cv["sections"]["Experience"][0]
        assert "start_date" not in entry
        assert entry["date"] == "2020 – present"

    def test_month_precision_left_untouched(self):
        cv = {
            "sections": {
                "Experience": [
                    {
                        "company": "Acme",
                        "position": "Engineer",
                        "start_date": "2021-03",
                        "end_date": "2023-05",
                    }
                ]
            }
        }
        _normalize_entry_dates(cv)
        entry = cv["sections"]["Experience"][0]
        # Month-precision: leave start_date/end_date untouched
        assert entry.get("start_date") == "2021-03"
        assert entry.get("end_date") == "2023-05"
        assert "date" not in entry

    def test_existing_date_field_not_overwritten(self):
        cv = {
            "sections": {
                "Education": [
                    {
                        "institution": "X",
                        "date": "Fall 2011",
                        "start_date": "2011",
                    }
                ]
            }
        }
        _normalize_entry_dates(cv)
        entry = cv["sections"]["Education"][0]
        assert entry["date"] == "Fall 2011"

    def test_no_dates_entry_unmodified(self):
        cv = {"sections": {"Skills": [{"label": "Python", "details": "Expert"}]}}
        _normalize_entry_dates(cv)
        entry = cv["sections"]["Skills"][0]
        assert "date" not in entry


# ---------------------------------------------------------------------------
# build_resume_yaml — year-only date normalization integration
# ---------------------------------------------------------------------------


class TestBuildResumeYamlDateNormalization:
    def test_education_end_only_year_gets_trailing_space_date(self):
        """build_resume_yaml must run _normalize_entry_dates so RenderCV YAML
        has the trailing-space trick instead of a bare year."""
        cv = {
            "name": "Alice",
            "sections": {
                "Education": [
                    {
                        "institution": "State U",
                        "degree": "BS",
                        "area": "Math",
                        "end_date": "2011",
                    }
                ]
            },
        }
        yaml_str = build_resume_yaml(cv, "classic")
        doc = yaml.safe_load(yaml_str)
        edu_entry = doc["cv"]["sections"]["Education"][0]
        assert "end_date" not in edu_entry
        # Trailing space preserved in YAML
        assert edu_entry.get("date", "").startswith("2011")
        assert edu_entry["date"] == "2011 "

    def test_experience_month_precision_kept_as_start_end(self):
        cv = {
            "name": "Bob",
            "sections": {
                "Experience": [
                    {
                        "company": "Acme",
                        "position": "Dev",
                        "start_date": "2021-03",
                        "end_date": "2023-05",
                    }
                ]
            },
        }
        yaml_str = build_resume_yaml(cv, "classic")
        doc = yaml.safe_load(yaml_str)
        exp_entry = doc["cv"]["sections"]["Experience"][0]
        assert exp_entry.get("start_date") == "2021-03"
        assert exp_entry.get("end_date") == "2023-05"
        assert "date" not in exp_entry


# ---------------------------------------------------------------------------
# render_pdf — slow real-subprocess tests for year-only date handling
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_render_pdf_education_year_only_end_date_no_jan():
    """End-to-end: a year-only end_date must appear as bare year in the
    rendered Typst source, NOT as "Jan YYYY".

    Shells out to rendercv and greps the generated .typ file.
    """
    import subprocess
    import sys
    import tempfile
    from pathlib import Path

    cv = {
        "name": "Test Candidate Year",
        "sections": {
            "Education": [
                {
                    "institution": "Example University",
                    "degree": "BS",
                    "area": "Computer Science",
                    "end_date": "2011",
                }
            ]
        },
    }
    yaml_str = build_resume_yaml(cv, "engineeringresumes")

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
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=120)
        assert result.returncode == 0, result.stderr.decode(errors="replace")

        # Confirm PDF produced
        pdf_files = list(outdir.glob("*.pdf"))
        assert pdf_files, "No PDF produced"
        pdf_bytes = pdf_files[0].read_bytes()
        assert pdf_bytes[:4] == b"%PDF"

        # Check Typst source does not contain "Jan 2011"
        typ_files = list(outdir.glob("**/*.typ"))
        if typ_files:
            typ_text = typ_files[0].read_text(encoding="utf-8")
            assert "Jan 2011" not in typ_text, (
                "RenderCV invented a month: found 'Jan 2011' in Typst source"
            )
            # "2011" should appear somewhere (the trailing space is trimmed by Typst)
            assert "2011" in typ_text
