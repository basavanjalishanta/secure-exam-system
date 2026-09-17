"""University-style question paper + answer key PDF generation with ReportLab."""
import io

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

_styles = getSampleStyleSheet()
_H = ParagraphStyle("clg", parent=_styles["Title"], fontSize=15, spaceAfter=2)
_SUB = ParagraphStyle("sub", parent=_styles["Normal"], alignment=TA_CENTER, fontSize=10)
_SEC = ParagraphStyle("sec", parent=_styles["Heading2"], fontSize=12, spaceBefore=10, spaceAfter=4)
_Q = ParagraphStyle("q", parent=_styles["Normal"], fontSize=10.5, spaceAfter=6, alignment=TA_JUSTIFY)
_A = ParagraphStyle("a", parent=_styles["Normal"], fontSize=10, spaceAfter=8, leftIndent=12,
                    alignment=TA_JUSTIFY)


def _header(meta: dict):
    elems = [
        Paragraph(meta.get("college_name", "University College of Engineering"), _H),
        Paragraph(meta.get("exam_name", "End Semester Examination"), _SUB),
        Paragraph(
            f"Semester: {meta.get('semester', '-')} &nbsp;&nbsp; "
            f"Subject: {meta.get('subject_name', '-')} ({meta.get('subject_code', '-')})",
            _SUB,
        ),
        Paragraph(
            f"Date: {meta.get('date', '-')} &nbsp;&nbsp; "
            f"Time: {meta.get('time', '3 Hours')} &nbsp;&nbsp; "
            f"Max Marks: {meta.get('max_marks', 100)}",
            _SUB,
        ),
        Spacer(1, 6),
        HRFlowable(width="100%", color=colors.black),
        Spacer(1, 6),
    ]
    instructions = meta.get("instructions") or [
        "Answer ALL questions.",
        "Figures to the right indicate full marks.",
        "Assume suitable data if necessary and state it clearly.",
    ]
    elems.append(Paragraph("<b>Instructions:</b>", _Q))
    for ins in instructions:
        elems.append(Paragraph(f"• {ins}", _Q))
    elems.append(Spacer(1, 4))
    return elems


def _questions_by_section(questions: list[dict]):
    grouped: dict[str, list[dict]] = {}
    for q in questions:
        grouped.setdefault(q.get("section", "A"), []).append(q)
    return grouped


def build_question_paper_pdf(meta: dict, questions: list[dict]) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=1.5 * cm, bottomMargin=1.5 * cm,
                            leftMargin=1.8 * cm, rightMargin=1.8 * cm,
                            title="Question Paper")
    elems = _header(meta)
    grouped = _questions_by_section(questions)
    for section in sorted(grouped):
        qs = grouped[section]
        marks_each = qs[0].get("marks", "")
        elems.append(
            Paragraph(f"SECTION {section} &nbsp; ({len(qs)} × {marks_each} = "
                      f"{sum(q.get('marks', 0) for q in qs)} marks)", _SEC)
        )
        for n, q in enumerate(qs, 1):
            rows = [[
                Paragraph(f"<b>{n}.</b> {q['question']}", _Q),
                Paragraph(f"<b>[{q.get('marks', '')}]</b>", _Q),
            ]]
            t = Table(rows, colWidths=[15.2 * cm, 1.6 * cm])
            t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                                   ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
            elems.append(t)
            meta_line = (f"<font size=8 color='grey'>Unit {q.get('unit', '-')} | "
                         f"{q.get('topic', '-')} | {q.get('difficulty', '-')} | "
                         f"Bloom: {q.get('bloom_level', '-')} | {q.get('question_type', '-')}</font>")
            elems.append(Paragraph(meta_line, _Q))
        elems.append(Spacer(1, 6))
    elems.append(HRFlowable(width="100%", color=colors.grey))
    elems.append(Paragraph("<font size=8 color='grey'>--- End of Question Paper ---</font>",
                           ParagraphStyle("end", parent=_SUB, fontSize=8)))
    doc.build(elems)
    return buf.getvalue()


def build_answer_key_pdf(meta: dict, questions: list[dict]) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=1.5 * cm, bottomMargin=1.5 * cm,
                            leftMargin=1.8 * cm, rightMargin=1.8 * cm, title="Answer Key")
    elems = [
        Paragraph(meta.get("college_name", "University College of Engineering"), _H),
        Paragraph("ANSWER KEY (CONFIDENTIAL)", _SUB),
        Paragraph(f"{meta.get('subject_name', '-')} ({meta.get('subject_code', '-')})", _SUB),
        Spacer(1, 6),
        HRFlowable(width="100%", color=colors.black),
        Spacer(1, 8),
    ]
    grouped = _questions_by_section(questions)
    for section in sorted(grouped):
        elems.append(Paragraph(f"SECTION {section}", _SEC))
        for n, q in enumerate(grouped[section], 1):
            elems.append(Paragraph(f"<b>Q{n}. ({q.get('marks', '')} marks)</b> {q['question']}", _Q))
            answer = (q.get("answer") or "Answer not generated.").replace("\n", "<br/>")
            elems.append(Paragraph(answer, _A))
    doc.build(elems)
    return buf.getvalue()
