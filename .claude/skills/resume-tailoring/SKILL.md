---
name: resume-tailoring
description: "Rewrite and tailor a resume to a specific job description and optimize it to pass Applicant Tracking Systems (ATS). Use this whenever the task involves adapting, tailoring, or rewriting a resume/CV for a particular role, matching a resume to a job posting, improving keyword alignment, or making a resume 'ATS-friendly' — even if the user doesn't say the word 'ATS'. Produces a tailored resume plus a summary of what changed and why."
---

# Resume Tailoring

Tailor a candidate's resume to a target job description so it reads as a strong, honest match and parses cleanly through ATS software. Work from two inputs: the candidate's current resume and the target job description (use the `jd-parser` skill's structured output if available; otherwise extract requirements first).

## Hard rule: never fabricate

Only rephrase, reframe, reorder, and emphasize experience the candidate actually has. Never invent jobs, skills, dates, metrics, or credentials. If the resume lacks something the role wants, surface it as a gap for the candidate to address — do not paper over it with fiction. This protects the candidate from misrepresentation and interview-stage embarrassment, and it's non-negotiable.

## Workflow

1. **Extract the role's signals**: required and preferred skills, the exact terminology used (tools, methodologies, titles), seniority, and the top responsibilities. The literal phrasing matters — ATS keyword matching is often exact-string.
2. **Map candidate → role**: for each requirement, find the candidate's matching experience. Note strong matches, partial matches worth reframing, and genuine gaps.
3. **Rewrite for alignment**:
   - Mirror the JD's terminology where it's truthfully equivalent (if they say "CI/CD" and the resume says "build pipelines", adopt their term).
   - Lead bullets with impact and quantify it (numbers, %, scale, time saved) — but only with real figures.
   - Front-load the most relevant experience; trim or compress what's irrelevant to this role.
   - Tailor the summary/headline to the target title and top 2–3 requirements.
4. **Apply ATS-safe formatting** (see rules below).
5. **Output**: the tailored resume, plus a short change summary — what you emphasized, which keywords you incorporated, and any gaps the candidate should be ready to speak to.

## ATS-safe formatting rules

ATS parsers are brittle; formatting that looks nice can become garbled text. Keep it simple:

- **Single-column layout.** Multi-column resumes frequently parse out of order.
- **No tables, text boxes, headers/footers, images, logos, icons, or charts.** Text inside these is often dropped. Put everything in the normal document body.
- **Standard section headings**: "Experience" / "Work Experience", "Education", "Skills", "Summary". Creative headings ("Where I've Made an Impact") can confuse parsers.
- **Standard fonts** (Arial, Calibri, Times New Roman, Helvetica), normal weights, no decorative glyphs.
- **Simple bullets** (•) and plain hyphenated dates; avoid special characters and graphical dividers.
- **Spell out then abbreviate** key terms once ("Search Engine Optimization (SEO)") so both forms match.
- **Contact info in the body**, not in a header/footer region.
- **File format**: `.docx` is the safest default for ATS; produce a clean PDF only if the posting asks for one (delegate the actual file generation to the `resume-export` skill).

## Optional resources

For a richer setup you can add, and reference from this file:
- `references/ats-rules.md` — extended ATS dos/don'ts and parser quirks.
- `references/examples.md` — before/after bullet rewrites showing keyword alignment and quantification.
