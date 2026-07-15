from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

# Traditional Chinese CID font bundled with reportlab itself — no font file
# to ship, relies on the PDF viewer's own CJK font substitution (the
# standard, dependency-free way to get CJK text into a reportlab PDF).
FONT_NAME = "MSung-Light"
_font_registered = False


def _ensure_font_registered() -> None:
    global _font_registered
    if not _font_registered:
        pdfmetrics.registerFont(UnicodeCIDFont(FONT_NAME))
        _font_registered = True


def build_pdf(display_name: str, chapters: list[tuple[str, str]]) -> bytes:
    """chapters: [(chapter_display, text_zh), ...], already sorted by the
    caller. Returns the combined PDF as bytes, one page break per chapter.
    """
    _ensure_font_registered()

    title_style = ParagraphStyle(
        "title", fontName=FONT_NAME, fontSize=18, leading=24, spaceAfter=12
    )
    heading_style = ParagraphStyle(
        "heading", fontName=FONT_NAME, fontSize=14, leading=20, spaceAfter=10
    )
    body_style = ParagraphStyle(
        "body", fontName=FONT_NAME, fontSize=11, leading=17, spaceAfter=6
    )

    story = [Paragraph(escape(display_name), title_style), Spacer(1, 12 * mm)]

    for idx, (chapter_display, text_zh) in enumerate(chapters):
        if idx > 0:
            story.append(PageBreak())
        story.append(Paragraph(f"第 {escape(chapter_display)} 話", heading_style))
        for line in text_zh.split("\n"):
            line = line.strip()
            if line:
                story.append(Paragraph(escape(line), body_style))

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4)
    doc.build(story)
    return buf.getvalue()
