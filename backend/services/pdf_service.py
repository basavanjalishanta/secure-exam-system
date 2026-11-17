"""University-style question paper + answer key PDF generation with ReportLab.

Formats strictly according to the VTU / Autonomous Institution standards
(e.g., Siddaganga Institute of Technology):
- USN 10-box grid and Course Code header
- Institutional banner and examination details
- Numbered full questions (Q1 to Q10) with sub-questions a), b), c)
- Outcome Box (BL, CO, PO, PSO) aligned under each sub-question
- Right-aligned mark indicators
- Confidential Answer Key styling with mark-scaled answer keys
"""
from __future__ import annotations

import io
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
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
_H = ParagraphStyle("clg", parent=_styles["Title"], fontSize=13, leading=15, spaceAfter=2, alignment=TA_CENTER)
_SUB = ParagraphStyle("sub", parent=_styles["Normal"], alignment=TA_CENTER, fontSize=8.5, leading=11)
_EXAM = ParagraphStyle("exam", parent=_styles["Normal"], alignment=TA_CENTER, fontSize=10, leading=12, fontName="Helvetica-Bold")
_COURSE = ParagraphStyle("course", parent=_styles["Title"], alignment=TA_CENTER, fontSize=12, leading=14, spaceBefore=3, spaceAfter=3)
_NOTE = ParagraphStyle("note", parent=_styles["Normal"], fontSize=8.5, leading=11, fontName="Helvetica-Bold")
_Q_TEXT = ParagraphStyle("q_text", parent=_styles["Normal"], fontSize=9, leading=12, alignment=TA_JUSTIFY)
_Q_MARK = ParagraphStyle("q_mark", parent=_styles["Normal"], fontSize=9.5, leading=12, alignment=TA_RIGHT, fontName="Helvetica-Bold")
_OUTCOME_CELL = ParagraphStyle("out_cell", parent=_styles["Normal"], fontSize=7, leading=8.5, alignment=TA_CENTER)
_OUTCOME_LABEL = ParagraphStyle("out_lbl", parent=_styles["Normal"], fontSize=7, leading=8.5, fontName="Helvetica-Bold")
_UNIT_HDR = ParagraphStyle("unit_hdr", parent=_styles["Normal"], fontSize=11, leading=14, fontName="Helvetica-Bold", alignment=TA_CENTER)
_OR_DIVIDER = ParagraphStyle("or_div", parent=_styles["Normal"], fontSize=10, leading=13, fontName="Helvetica-Bold", alignment=TA_CENTER)
_A = ParagraphStyle("a", parent=_styles["Normal"], fontSize=8.5, leading=11.5, spaceAfter=6, leftIndent=10, alignment=TA_JUSTIFY)


def _usn_and_code_header(meta: dict):
    """Draws the top row: USN boxes on the left, Course code on the right."""
    row = [
        Paragraph("<b>USN</b>", ParagraphStyle("usn_lbl", parent=_styles["Normal"], fontSize=9, fontName="Helvetica-Bold")),
        Paragraph("<b>1</b>", _OUTCOME_CELL),
        Paragraph("<b>S</b>", _OUTCOME_CELL),
        Paragraph("<b>I</b>", _OUTCOME_CELL),
        Paragraph("", _OUTCOME_CELL),
        Paragraph("", _OUTCOME_CELL),
        Paragraph("", _OUTCOME_CELL),
        Paragraph("", _OUTCOME_CELL),
        Paragraph("", _OUTCOME_CELL),
        Paragraph("", _OUTCOME_CELL),
        Paragraph("", _OUTCOME_CELL),
        Paragraph(f"<b>{meta.get('subject_code', '3RCS02')}</b>", ParagraphStyle("code_lbl", parent=_styles["Normal"], fontSize=10, alignment=TA_RIGHT, fontName="Helvetica-Bold")),
    ]
    col_w = [1.2 * cm] + [0.42 * cm] * 10 + [12.1 * cm]
    t = Table([row], colWidths=col_w, rowHeights=[0.45 * cm])
    t.setStyle(TableStyle([
        ("GRID", (1, 0), (10, 0), 0.5, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 0), (10, 0), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    return t


def _build_outcome_box(q: dict) -> Table:
    """Builds the Bloom Level, CO, PO, PSO outcome box below each sub-question."""
    bl = q.get("bl") or 2
    co = q.get("co") or min(5, max(1, q.get("unit", 1)))
    po = q.get("po") or 3
    pso = q.get("pso", "")

    cells = [
        Paragraph("<b>BL:</b>", _OUTCOME_LABEL),
        Paragraph(str(bl), _OUTCOME_CELL),
        Paragraph("<b>CO:</b>", _OUTCOME_LABEL),
        Paragraph(str(co), _OUTCOME_CELL),
        Paragraph("<b>PO:</b>", _OUTCOME_LABEL),
        Paragraph(str(po), _OUTCOME_CELL),
        Paragraph("<b>PSO:</b>", _OUTCOME_LABEL),
        Paragraph(str(pso) if pso else "", _OUTCOME_CELL),
    ]
    t = Table([cells], colWidths=[0.8 * cm, 0.7 * cm, 0.8 * cm, 0.7 * cm, 0.8 * cm, 0.7 * cm, 0.9 * cm, 0.7 * cm], rowHeights=[0.38 * cm])
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BACKGROUND", (0, 0), (-1, -1), colors.whitesmoke),
        ("TOPPADDING", (0, 0), (-1, -1), 0.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 1),
        ("RIGHTPADDING", (0, 0), (-1, -1), 1),
    ]))
    return t


def build_question_paper_pdf(meta: dict, questions: list[dict]) -> bytes:
    """Renders the question paper PDF strictly adhering to institutional specifications."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        topMargin=1.0 * cm,
        bottomMargin=1.0 * cm,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        title=f"Question Paper - {meta.get('subject_code', '')}",
    )

    elems = []

    # 1. USN & Code header row
    elems.append(_usn_and_code_header(meta))
    elems.append(Spacer(1, 4))

    # 2. Institutional Title
    college = meta.get("college_name", "Siddaganga Institute of Technology, Tumakuru - 572 103")
    elems.append(Paragraph(f"<b>{college}</b>", _H))
    elems.append(Paragraph("(An Autonomous Institution affiliated to VTU, Belagavi, Approved by AICTE, New Delhi)", _SUB))
    elems.append(Spacer(1, 2))

    # 3. Exam Title & Subject Name
    max_marks = meta.get("max_marks", 100)
    default_exam_title = "Continuous Internal Evaluation (CIE)" if max_marks <= 50 else "Semester End Examinations B.E."
    exam_title = meta.get("exam_name") or default_exam_title
    elems.append(Paragraph(exam_title, _EXAM))
    elems.append(Paragraph(f"<b>{meta.get('subject_name', 'Course Examination')}</b>", _COURSE))
    elems.append(Spacer(1, 2))

    # 4. Time, Max Marks, and Note
    time_str = meta.get("time") or ("90 Minutes" if max_marks <= 50 else "3 Hours")
    info_table = Table(
        [[Paragraph(f"<b>Time: {time_str}</b>", _NOTE), Paragraph(f"<b>Max. Marks: {max_marks}</b>", ParagraphStyle("mm", parent=_NOTE, alignment=TA_RIGHT))]],
        colWidths=[8.5 * cm, 9.0 * cm],
    )
    info_table.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    elems.append(info_table)
    elems.append(Spacer(1, 2))

    default_note = "Note : Answer any two full questions from Q.No. 1 to Q.No. 4." if max_marks <= 50 else "Note : Answer any five full questions from Q.No. 1 to Q.No. 10."
    note_text = meta.get("note") or default_note
    elems.append(Paragraph(f"<b>{note_text}</b>", _NOTE))
    elems.append(Spacer(1, 4))
    elems.append(HRFlowable(width="100%", thickness=0.8, color=colors.black))
    elems.append(Spacer(1, 6))

    # 5. Group questions into Unit blocks and Full Question Groups (Q01 to Q10) with sub-questions (a, b, c)
    # Standard VTU / Autonomous Institution Examination Structure:
    # 5 Units. Each Unit has 2 full questions (e.g. Q01 OR Q02).
    # Sub-parts a), b), c) carry marks with outcome badges (BL, CO, PO, PSO).
    
    # Roman numeral mapping for units
    roman_units = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V"}
    sub_labels = ["a)", "b)", "c)", "d)", "e)"]

    # Structure by Unit -> Full Question
    # Each question object may have 'unit', 'full_question_num', 'sub_part', 'is_or'
    # If not present (e.g. legacy flat questions), we group logically:
    has_full_question_num = any("full_question_num" in q for q in questions)
    
    unit_grouped: dict[int, dict[int, list[dict]]] = {}
    
    if has_full_question_num:
        for q in questions:
            u = q.get("unit") or 1
            fq = q.get("full_question_num") or 1
            unit_grouped.setdefault(u, {}).setdefault(fq, []).append(q)
    else:
        # Check if questions have unit metadata
        has_units = any(q.get("unit") for q in questions)
        if has_units and len(questions) > 10:
            # Group by unit first
            for q in questions:
                u = q.get("unit") or 1
                unit_grouped.setdefault(u, {})
            # Inside each unit, divide into 2 questions (main and OR)
            for u in sorted(unit_grouped.keys()):
                u_qs = [q for q in questions if (q.get("unit") or 1) == u]
                fq_base = (u - 1) * 2 + 1
                half = max(1, len(u_qs) // 2)
                unit_grouped[u][fq_base] = u_qs[:half]
                unit_grouped[u][fq_base + 1] = u_qs[half:]
        elif len(questions) <= 10:
            # 1-to-1 mapping
            for idx, q in enumerate(questions, 1):
                u = ((idx - 1) // 2) + 1
                unit_grouped.setdefault(u, {}).setdefault(idx, []).append(q)
        else:
            # Divide into 10 full questions across 5 units
            slots_per_q = max(2, len(questions) // 10)
            for idx, q in enumerate(questions):
                fq_num = min(10, (idx // slots_per_q) + 1)
                u = ((fq_num - 1) // 2) + 1
                unit_grouped.setdefault(u, {}).setdefault(fq_num, []).append(q)

    # Render Unit-by-Unit
    for u in sorted(unit_grouped.keys()):
        u_label = roman_units.get(u, str(u))
        
        # Unit Header Table (Centered bold banner with light borders)
        unit_header_cell = Paragraph(f"<b>Unit - {u_label}</b>", _UNIT_HDR)
        t_unit = Table([[unit_header_cell]], colWidths=[17.5 * cm])
        t_unit.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LINEABOVE", (0, 0), (-1, -1), 0.8, colors.black),
            ("LINEBELOW", (0, 0), (-1, -1), 0.8, colors.black),
            ("BACKGROUND", (0, 0), (-1, -1), colors.whitesmoke),
        ]))
        elems.append(Spacer(1, 4))
        elems.append(t_unit)
        elems.append(Spacer(1, 6))

        fq_dict = unit_grouped[u]
        fq_nums = sorted(fq_dict.keys())

        for fq_idx, fq_num in enumerate(fq_nums):
            sub_list = fq_dict[fq_num]
            two_digit_num = f"{fq_num:02d}"

            for sub_idx, q in enumerate(sub_list):
                # Sub-part label (a), b), c) or explicit q['sub_part']
                sub_label = q.get("sub_part")
                if sub_label and not sub_label.endswith(")"):
                    sub_label = f"{sub_label})"
                if not sub_label:
                    sub_label = sub_labels[sub_idx % len(sub_labels)]

                q_num_prefix = f"<b>{two_digit_num}</b>&nbsp;&nbsp;{sub_label}" if sub_idx == 0 else f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{sub_label}"

                q_row = [
                    Paragraph(q_num_prefix, ParagraphStyle("sub_lbl", parent=_styles["Normal"], fontSize=9, fontName="Helvetica-Bold")),
                    Paragraph(q.get("question", ""), _Q_TEXT),
                    Paragraph(str(q.get("marks", 6)), _Q_MARK),
                ]
                t_q = Table([q_row], colWidths=[1.1 * cm, 15.0 * cm, 1.4 * cm])
                t_q.setStyle(TableStyle([
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ]))
                elems.append(t_q)

                # Outcome Box below sub-question
                out_box = _build_outcome_box(q)
                out_box.hAlign = 'RIGHT'
                elems.append(out_box)
                elems.append(Spacer(1, 3))

            # If there's another full question in this unit, render "OR" separator
            if fq_idx < len(fq_nums) - 1:
                elems.append(Spacer(1, 3))
                or_table = Table([[Paragraph("<b>OR</b>", _OR_DIVIDER)]], colWidths=[17.5 * cm])
                or_table.setStyle(TableStyle([
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ]))
                elems.append(or_table)
                elems.append(Spacer(1, 3))

        elems.append(Spacer(1, 4))

    elems.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    elems.append(Paragraph("<font size=7 color='grey'>__________</font>", ParagraphStyle("end", parent=_SUB, fontSize=7)))

    doc.build(elems)
    return buf.getvalue()


def build_answer_key_pdf(meta: dict, questions: list[dict]) -> bytes:
    """Renders the confidential institutional Answer Key PDF."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        topMargin=1.2 * cm,
        bottomMargin=1.2 * cm,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        title="Confidential Answer Key",
    )

    elems = [
        Paragraph(f"<b>{meta.get('college_name', 'Siddaganga Institute of Technology, Tumakuru')}</b>", _H),
        Paragraph("<b>EXAMINATION ANSWER KEY & SCHEME OF VALUATION (CONFIDENTIAL)</b>", _EXAM),
        Paragraph(f"Subject: {meta.get('subject_name', '-')} ({meta.get('subject_code', '-')})", _SUB),
        Spacer(1, 4),
        HRFlowable(width="100%", thickness=1, color=colors.black),
        Spacer(1, 6),
    ]

    for idx, q in enumerate(questions, 1):
        q_header = f"<b>Q{idx}. [{q.get('marks', 6)} Marks] (Unit {q.get('unit', 1)}, BL: {q.get('bl', 2)}, CO: {q.get('co', 1)})</b>: {q.get('question', '')}"
        elems.append(Paragraph(q_header, ParagraphStyle("ak_q", parent=_styles["Normal"], fontSize=9, fontName="Helvetica-Bold", spaceBefore=4, spaceAfter=3)))

        answer_text = (q.get("answer") or "Answer model key not generated yet.").replace("\n", "<br/>")
        elems.append(Paragraph(answer_text, _A))

        if q.get("answer_support"):
            support_line = f"<font size=7 color='grey'>Supported by: {', '.join(q.get('answer_sources', ['Course Notes']))} | Support score: {q.get('answer_support')}</font>"
            elems.append(Paragraph(support_line, ParagraphStyle("ak_sup", parent=_styles["Normal"], fontSize=7, leftIndent=10)))
        elems.append(Spacer(1, 4))

    doc.build(elems)
    return buf.getvalue()
