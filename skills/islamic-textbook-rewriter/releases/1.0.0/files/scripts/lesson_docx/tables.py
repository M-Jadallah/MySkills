from __future__ import annotations

from docx.shared import Inches

from .styles import CREAM, GRAY, RED, WHITE, add_para, arabic_indic_digits, set_cell_text, set_table_rtl

# Matches app/docx/styles.py::setup_document(): 8.5in page width minus
# 0.5in margins on each side = 7.5in usable content width. Tables fill this
# width and split it evenly across however many columns the content
# actually needs, so a 2-column and an 8-column table both render as a
# deliberate full-width layout instead of Word's autofit guess.
USABLE_WIDTH_INCHES = 7.5


def add_styled_table(doc, title: str, headers: list[str], rows: list[list[str]]) -> None:
    """Structured study table: red header row, alternating body-row shading.

    Column and row counts are entirely content-driven (whatever shape the
    AI/schema layer provides) - this function imposes no fixed shape of its
    own, only a shared full-width column layout for visual consistency.
    Carried over from the islamic_study_summary_bot template, which is the
    stronger of the two source templates for tabular presentation.
    """
    if title:
        add_para(doc, f"◆ {title}", size=18, color=RED, bold=True, before=90, after=40, keep_next=True)
    headers = [arabic_indic_digits(h) for h in headers]
    if not headers:
        return
    table = doc.add_table(rows=1, cols=len(headers))
    set_table_rtl(table)
    table.style = "Table Grid"
    table.autofit = False
    col_width = Inches(USABLE_WIDTH_INCHES / len(headers))

    for i, header in enumerate(headers):
        set_cell_text(table.rows[0].cells[i], header, fill=RED, color=WHITE, size=18, bold=True, align="center")

    fills = [WHITE, GRAY, CREAM]
    normalized_rows = [[arabic_indic_digits(str(cell or "")) for cell in row] for row in (rows or [])]
    for r_idx, row_data in enumerate(normalized_rows):
        row = table.add_row()
        for c_idx, value in enumerate(row_data[: len(headers)]):
            set_cell_text(row.cells[c_idx], value, fill=fills[r_idx % len(fills)], color="1F1F1F", size=18, bold=False)
        for c_idx in range(len(row_data), len(headers)):
            set_cell_text(row.cells[c_idx], "", fill=fills[r_idx % len(fills)], color="1F1F1F", size=18)

    # Explicit per-cell width on every row: python-docx's table.columns[i].width
    # only reliably reaches cells that exist at assignment time, and rows above
    # were added via add_row() after the fact, so set it row-by-row instead.
    for row in table.rows:
        for cell in row.cells:
            cell.width = col_width

    add_para(doc, "", after=40)
