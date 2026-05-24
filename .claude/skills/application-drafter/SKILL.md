---
name: application-drafter
description: "Draft job-application materials in the candidate's own voice — cover letters, 'why this company' / 'why you' answers, screening-question responses, and short intro messages. Use whenever an application needs written content tailored to a specific role and the candidate's background, not a generic template. Produces a ready-to-review draft the user can edit and approve before anything is sent."
---

# Application Drafter

Write application content that sounds like the candidate, speaks to the specific role, and stays strictly truthful. Inputs: the candidate's resume/background, the target role (ideally the `jd-parser` output), and the prompt being answered (a cover letter, a free-text screening question, etc.).

## Voice and honesty

- **Match the candidate's voice**, not a generic "applicant" tone. If a writing sample is available, mirror its register, sentence length, and warmth. Default to clear, professional, and human — not florid or buzzword-stuffed.
- **Never fabricate.** Every claim must trace back to the candidate's real experience. No invented metrics, employers, or skills. If the candidate is light on a requirement, address it with adjacent real experience or honest enthusiasm to learn — never with fiction.
- **Avoid AI tells**: skip stock openers ("I am writing to express my keen interest"), empty superlatives, and repetitive structure. Be specific instead — name the actual project, the actual result, the actual reason this company is interesting.

## Workflow

1. Identify what's being written and any length/format constraints (a cover letter differs from a 300-character screening box).
2. Pull the role's top 2–3 priorities from the parsed JD.
3. Select the candidate's strongest, most relevant evidence for those priorities.
4. Draft, leading with a specific hook tied to this role or company — not a generic salutation.
5. Tie the candidate's evidence to the role's needs; close with a forward-looking, low-pressure line.
6. Keep it tight: most cover letters land in 200–350 words; answer free-text questions at the length the field implies.

## Output

Provide the draft clearly labeled, followed by a one-line note on anything the candidate should verify or personalize (a name, a recent company detail) before sending. This is a **draft for human review** — never present it as final or imply it will be sent without the candidate's approval.

## Optional resources

- `assets/voice-sample.md` — a sample of the candidate's writing to mirror.
- `assets/cover-letter-template.md` — a loose structural skeleton (use as scaffolding, not a fill-in-the-blank form).
