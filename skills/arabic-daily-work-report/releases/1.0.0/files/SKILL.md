---
name: arabic-daily-work-report
description: Create polished Arabic RTL daily work reports in Word from incrementally supplied notes. Use when the user wants to log operational updates first and generate the final management report only after a direct command.
metadata:
  short-description: Build verified Arabic daily work reports
---

# Arabic Daily Work Report

Use this skill for an Arabic management report that records the day’s workflow, decisions, implemented actions, proposals, changes, problems, observations, and follow-up items.

## Conversation protocol

1. When the skill is invoked, enter collection mode. Acknowledge each new fact briefly and add it to an internal ledger. Do not draft, summarize, classify publicly, create a file, or take external action while collection mode is active.
2. Keep the wording and status supplied by the user. Preserve the distinction between an implemented decision or action, a proposal awaiting approval, an observation or problem, and a follow-up item. Do not turn a proposal into a decision.
3. If the user corrects a fact, replace the earlier version in the ledger. Preserve names, group names, dates, times, schedules, and constraints exactly as supplied.
4. Leave collection mode only when the user gives a direct command such as “أعد التقرير” or clearly requests the final report. If the command is ambiguous, continue collecting.
5. Before generating, organize the ledger into these sections when applicable: introductory scope, decisions and implemented actions, proposals and responsibility changes, performance and attendance observations, teacher-recorded problems, follow-up points, and a concise conclusion. Omit empty sections.
6. Use the current client date in the report metadata unless the user provides a different reporting date. Do not invent an author, institution, metrics, or outcomes.

## Word deliverable

Create one editable `.docx` in Arabic with a polished management-report layout:

- Letter portrait, generous margins, and a thin dark-blue page border on all four sides.
- Arabic RTL direction at paragraph, table, and run level. Set paragraph alignment explicitly. Narrative paragraphs and list items are right aligned. Title and subtitle are centered. Table cells use intentional right or centered alignment.
- Use an Arabic-capable readable font such as Arial. Use black body text and headings, dark blue for list markers and the frame, and a restrained gold accent for section markers and metadata labels.
- Title: `تقرير سير العمل اليومي`. Subtitle: `القرارات المتخذة والمقترحات والإجراءات التنظيمية`.
- Include a compact metadata table with date, recipient or جهة, subject, and scope. Use light-gold labels and visible light-gray borders.
- Use clear numbered lists for scannable actions. Number markers must be on the right and use Arabic-Indic digits. Add right-to-left marks around markers when needed so Word and LibreOffice do not move numbers to the left.
- Convert dates and list numbers to Arabic-Indic digits. Apply `w:bidi` to paragraphs and `w:rtl` to every run, including runs containing numbers. This is required to prevent mixed-direction defects.
- Use a footer with the report title, Arabic-Indic date, and a PAGE field. Keep the footer readable and inside the page border.
- Avoid decorative horizontal rules under the title or headings. Use whitespace, typography, and a small gold diamond section marker.
- Keep tables limited to metadata or genuinely comparable information. Avoid putting long narrative paragraphs into table cells.

## Generation and verification

1. Use the bundled workspace Python runtime and `python-docx`. Load workspace dependencies before running a builder.
2. Generate the `.docx` through the supporting script `scripts/build_report.py`, passing a UTF-8 JSON payload containing the normalized ledger and report date. The script applies the design and RTL hardening above.
3. Render the document with the documents skill’s `render_docx.py` and the bundled or available LibreOffice renderer. Produce page PNGs in a work or temporary folder.
4. Inspect every rendered page at 100 percent. Check that Arabic text is readable, paragraphs and tables are right-to-left, numbers sit on the right, no text is clipped or overlapped, the border and footer are intact, and page breaks are natural.
5. If any issue appears, repair the builder or input, regenerate, render again, and re-inspect all pages. Do not deliver until the latest render passes.
6. Deliver only the final `.docx` unless the user asks for PDF or QA images. In the final reply, link the output file exactly once and mention any assumption that materially affected the result.

## Supporting resource

- `scripts/build_report.py` is the deterministic Word builder. Read or run it when generating the document.
