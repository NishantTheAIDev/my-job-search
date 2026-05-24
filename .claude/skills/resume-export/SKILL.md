---
name: resume-export
description: "Generate the final tailored resume as a downloadable, ATS-safe file (.docx by default, PDF when a posting requires it). Use after a resume has been tailored and the content is ready to be turned into a polished document the candidate can submit. Handles formatting constraints that keep the document parseable by Applicant Tracking Systems and delegates the actual file creation to the built-in docx/pdf skills."
---

# Resume Export

Turn finalized resume content (typically the output of the `resume-tailoring` skill) into a clean document file the candidate can submit. The priority is a file that both reads well to a human and parses correctly through ATS software.

## Format choice

- **Default to `.docx`.** It is the most reliably parsed format across ATS platforms.
- **Produce a PDF only when the posting asks for one** (or the user requests it). When you do, generate a text-based PDF, never an image/scanned one, so the text remains selectable and machine-readable.
- Use the built-in document skills to generate the file: the **docx** skill for Word output and the **pdf** skill for PDF output. Read the relevant SKILL.md and follow it for the actual generation step rather than hand-rolling document XML.

## ATS-safe constraints (enforce regardless of format)

- **Single column.** No multi-column layouts — they parse out of order.
- **No tables, text boxes, headers/footers, images, logos, icons, or shapes.** Keep all content in the normal document body; text trapped in these elements is frequently dropped.
- **Standard section headings**: Summary, Experience / Work Experience, Education, Skills.
- **Standard fonts** (Arial, Calibri, Times New Roman, Helvetica), conventional sizes (10–12pt body, slightly larger name/headings), normal weights.
- **Simple bullets and plain text dates.** Avoid decorative glyphs, dividers, and special characters.
- **Contact details in the body**, not in a header/footer region.
- Consistent, generous whitespace and clear hierarchy so it's also pleasant for a human reviewer.

## Workflow

1. Confirm the content is final (tailoring done, candidate-approved if applicable).
2. Pick the format (`.docx` unless a PDF is required).
3. Read the matching built-in skill (docx or pdf) and generate the file under the ATS constraints above.
4. Name the file clearly and professionally — e.g. `FirstName_LastName_Resume_RoleOrCompany.docx`.
5. Present the file for download and note the format chosen and why.

## Optional resources

- `assets/resume-template.docx` — an ATS-safe base template to populate, if you maintain one.
