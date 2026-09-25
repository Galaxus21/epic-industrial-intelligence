"""
EPIC — Page layout shared by the demo's sample PDF reports (fpdf2).

The core PDF fonts cover Latin-1 only, so every string passes through latin1Text before it is drawn. Tables wrap long
cells instead of cutting them, so no finding is lost off the edge of a column.
"""
from __future__ import annotations

from fpdf import FPDF
from fpdf.enums import XPos, YPos
from fpdf.fonts import FontFace

AMBER = (245, 158, 11)
GREEN = (16, 185, 129)
RED = (239, 68, 68)
BLUE = (59, 130, 246)
DARK = (20, 20, 30)
GREY = (110, 110, 110)
LIGHT = (240, 240, 240)
WHITE = (255, 255, 255)
BLACK = (15, 15, 15)

PAGE_WIDTH_MM = 210
MARGIN_MM = 12
TOP_MARGIN_MM = 22
BOTTOM_MARGIN_MM = 18
BAND_HEIGHT_MM = 18
FOOTER_HEIGHT_MM = 14
LINE_HEIGHT_MM = 5
FONT = "Helvetica"
# Characters the core fonts cannot draw, and what stands in for them.
NON_LATIN1_REPLACEMENTS = {"\u2014": " - ", "\u2013": " - ", "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
                           "\u2022": "*", "\u03bc": "u", "\u2265": ">=", "\u2264": "<=", "\u2192": "->"}


class DemoReportPdf(FPDF):
    """An A4 report with a dark title band on every page and a numbered footer."""

    def __init__(self, headerTitle: str, footerNote: str) -> None:
        super().__init__()
        self.headerTitle = headerTitle
        self.footerNote = footerNote
        self.set_margins(MARGIN_MM, TOP_MARGIN_MM, MARGIN_MM)
        self.set_auto_page_break(True, margin=BOTTOM_MARGIN_MM)

    def header(self) -> None:
        self.set_fill_color(*DARK)
        self.rect(0, 0, PAGE_WIDTH_MM, BAND_HEIGHT_MM, "F")
        self.set_font(FONT, "B", 9)
        self.set_text_color(*AMBER)
        self.set_xy(8, 4)
        self.cell(0, 10, latin1Text(f"EPIC  |  {self.headerTitle}"))
        self.set_xy(MARGIN_MM, TOP_MARGIN_MM)

    def footer(self) -> None:
        self.set_y(-FOOTER_HEIGHT_MM)
        self.set_fill_color(*DARK)
        self.rect(0, self.get_y(), PAGE_WIDTH_MM, FOOTER_HEIGHT_MM, "F")
        self.set_font(FONT, "", 8)
        self.set_text_color(*AMBER)
        self.cell(0, 10, latin1Text(f"{self.footerNote}  |  Page {self.page_no()}"), align="C")


def latin1Text(text: str) -> str:
    for character, replacement in NON_LATIN1_REPLACEMENTS.items():
        text = text.replace(character, replacement)
    return text.encode("latin-1", errors="replace").decode("latin-1")


def startReport(headerTitle: str, footerNote: str) -> DemoReportPdf:
    pdf = DemoReportPdf(headerTitle, footerNote)
    pdf.add_page()
    return pdf


def titleBlock(pdf: FPDF, title: str, subtitle: str) -> None:
    pdf.ln(4)
    pdf.set_font(FONT, "B", 16)
    pdf.set_text_color(*DARK)
    pdf.cell(0, 9, latin1Text(title), align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font(FONT, "", 9)
    pdf.set_text_color(*GREY)
    pdf.cell(0, LINE_HEIGHT_MM, latin1Text(subtitle), align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)
    pdf.set_draw_color(*AMBER)
    pdf.set_line_width(0.7)
    pdf.line(MARGIN_MM, pdf.get_y(), PAGE_WIDTH_MM - MARGIN_MM, pdf.get_y())
    pdf.ln(4)


def section(pdf: FPDF, title: str) -> None:
    pdf.ln(4)
    pdf.set_fill_color(*DARK)
    pdf.set_text_color(*AMBER)
    pdf.set_font(FONT, "B", 9)
    pdf.cell(0, 7, latin1Text(f"  {title}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True)
    pdf.ln(2)


def keyValues(pdf: FPDF, pairs: list[tuple[str, str]], valueColours: dict[str, tuple[int, int, int]] | None = None,
              keyWidthMm: int = 48) -> None:
    for key, value in pairs:
        pdf.set_font(FONT, "", 8)
        pdf.set_text_color(*GREY)
        pdf.cell(keyWidthMm, LINE_HEIGHT_MM, latin1Text(key), new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.set_font(FONT, "B", 8)
        pdf.set_text_color(*(valueColours or {}).get(key, BLACK))
        pdf.multi_cell(0, LINE_HEIGHT_MM, latin1Text(value), align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def paragraph(pdf: FPDF, text: str) -> None:
    pdf.set_font(FONT, "", 8)
    pdf.set_text_color(*BLACK)
    pdf.multi_cell(0, LINE_HEIGHT_MM, latin1Text(text), align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def table(pdf: FPDF, headings: tuple[str, ...], rows: list[tuple[str, ...]], columnWidths: tuple[int, ...],
          statusColours: dict[str, tuple[int, int, int]] | None = None) -> None:
    """A wrapped table; a cell whose text is a key of statusColours is drawn bold in that colour."""
    pdf.set_font(FONT, "", 7)
    pdf.set_text_color(*BLACK)
    # Rows between the shaded ones take the current fill colour, which a section band leaves dark.
    pdf.set_fill_color(*WHITE)
    headingStyle = FontFace(emphasis="BOLD", color=WHITE, fill_color=DARK)
    with pdf.table(col_widths=columnWidths, headings_style=headingStyle, line_height=LINE_HEIGHT_MM - 1,
                   text_align="LEFT", cell_fill_color=LIGHT, cell_fill_mode="ROWS", borders_layout="NONE",
                   padding=1) as drawn:
        headingRow = drawn.row()
        for heading in headings:
            headingRow.cell(latin1Text(heading))
        for values in rows:
            row = drawn.row()
            for value in values:
                colour = (statusColours or {}).get(value)
                style = FontFace(emphasis="BOLD", color=colour) if colour else None
                row.cell(latin1Text(value), style=style)


def pdfBytes(pdf: FPDF) -> bytes:
    return bytes(pdf.output())
