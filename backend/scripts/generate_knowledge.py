import argparse
import html
import json
import re
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT_DIR = Path(__file__).resolve().parents[1]
WORKSPACE_DIR = ROOT_DIR.parent
DEFAULT_CV_PATH = ROOT_DIR / "app" / "data" / "Brielle Johnston CV EN.docx"
DEFAULT_OUTPUT_PATH = ROOT_DIR / "app" / "data" / "knowledge.json"
DEFAULT_HTML_OUTPUT_PATH = WORKSPACE_DIR / "frontend" / "public" / "cv.html"
DEFAULT_PDF_OUTPUT_PATH = WORKSPACE_DIR / "frontend" / "public" / "cv.pdf"
WORD_NAMESPACE = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def extract_docx_paragraphs(path: Path) -> list[str]:
    with ZipFile(path) as docx:
        document = docx.read("word/document.xml")

    root = ET.fromstring(document)
    paragraphs: list[str] = []

    for paragraph in root.findall(f".//{{{WORD_NAMESPACE}}}p"):
        parts: list[str] = []
        for node in paragraph.iter():
            if node.tag == f"{{{WORD_NAMESPACE}}}t" and node.text:
                parts.append(node.text)
            elif node.tag == f"{{{WORD_NAMESPACE}}}tab":
                parts.append("\t")
        text = "".join(parts).strip()
        if text:
            paragraphs.append(text)

    return paragraphs


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "chunk"


def make_record(
    record_id: str,
    title: str,
    category: str,
    section: str,
    chunk_index: int,
    content: str,
) -> dict[str, Any]:
    return {
        "id": record_id,
        "title": title,
        "category": category,
        "section": section,
        "chunk_index": chunk_index,
        "content": content,
                "source_ref": {
                        "document_url": "/cv.html",
                        "anchor": f"chunk-{chunk_index}",
                },
    }

def build_html_document(records: list[dict[str, Any]]) -> str:
        sections = "\n".join(build_html_section(record) for record in records)
        return f"""<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Brielle Johnston CV</title>
    <style>
        :root {{
            color: #172033;
            background: #eef2f7;
            font-family: Aptos, "Segoe UI", Arial, sans-serif;
            scroll-behavior: smooth;
        }}

        body {{
            margin: 0;
            padding: 40px 18px;
        }}

        main {{
            max-width: 860px;
            margin: 0 auto;
            padding: 48px clamp(22px, 5vw, 64px);
            background: #fff;
            border: 1px solid #d9e2ef;
            box-shadow: 0 24px 60px rgba(15, 23, 42, 0.12);
        }}

        section {{
            scroll-margin-top: 24px;
            border-radius: 6px;
            transition: background-color 160ms ease, box-shadow 160ms ease;
        }}

        section + section {{
            margin-top: 18px;
        }}

        section:target {{
            background: #f3e70b;
            box-shadow: 0 0 0 8px #f3e70b;
        }}

        h1 {{
            margin: 0 0 8px;
            font-size: clamp(32px, 5vw, 48px);
            letter-spacing: 0;
            text-transform: uppercase;
        }}

        h2 {{
            margin: 0 0 8px;
            font-family: inherit;
            font-size: 13px;
            letter-spacing: 0;
            text-transform: uppercase;
            color: #1d4ed8;
        }}

        pre {{
            margin: 0;
            white-space: pre-wrap;
            font: inherit;
            line-height: 1.55;
        }}

        p {{
            margin: 0;
            line-height: 1.55;
        }}

        ul {{
            margin: 8px 0 0;
            padding-left: 22px;
        }}

        li {{
            margin: 5px 0;
            line-height: 1.45;
        }}

        .entry-heading {{
            display: flex;
            justify-content: space-between;
            gap: 18px;
            font-weight: 700;
        }}

        .entry-role {{
            margin-top: 3px;
            font-weight: 700;
            text-transform: uppercase;
        }}

        .profile-title {{
            font-size: 20px;
            line-height: 1.3;
            margin: 0;
        }}

        .contact pre {{
            color: #475569;
        }}

        @media (max-width: 640px) {{
            body {{
                padding: 0;
                background: #fff;
            }}

            main {{
                min-height: 100vh;
                border: 0;
                box-shadow: none;
            }}
        }}
    </style>
</head>
<body>
    <main>
{sections}
    </main>
</body>
</html>
"""


def build_pdf_document(records: list[dict[str, Any]], output_path: Path) -> None:
    styles = get_pdf_styles()
    document = SimpleDocTemplate(
        str(output_path),
        pagesize=LETTER,
        rightMargin=0.65 * inch,
        leftMargin=0.65 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.55 * inch,
        title="Brielle Johnston CV",
        author="Brielle Johnston",
    )

    story: list[Any] = []

    for record in records:
        category = record.get("category")
        raw_content = str(record.get("content") or "")
        title = str(record.get("title") or "")

        if category == "profile":
            lines = [line for line in raw_content.splitlines() if line.strip()]
            if lines:
                story.append(Paragraph(html.escape(lines[0]), styles["name"]))
            if len(lines) > 1:
                story.append(Paragraph(html.escape(lines[1]), styles["profile_title"]))
            story.append(Spacer(1, 7))
            continue

        if category == "contact":
            story.append(Paragraph(html.escape(raw_content), styles["contact"]))
            story.append(Spacer(1, 10))
            continue

        story.append(Paragraph(html.escape(title.upper()), styles["section_heading"]))

        if category == "work experience":
            story.extend(build_work_experience_pdf_flowables(raw_content, styles))
        elif category == "education":
            story.extend(build_education_pdf_flowables(raw_content, styles))
        else:
            for line in visible_content_lines(raw_content, record.get("section")):
                story.append(Paragraph(format_label_line(line), styles["body"]))

        story.append(Spacer(1, 8))

    document.build(story)


def get_pdf_styles() -> dict[str, ParagraphStyle]:
    base_styles = getSampleStyleSheet()
    return {
        "name": ParagraphStyle(
            "CVName",
            parent=base_styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=25,
            textColor=colors.HexColor("#172033"),
        ),
        "profile_title": ParagraphStyle(
            "CVProfileTitle",
            parent=base_styles["Normal"],
            fontName="Helvetica",
            fontSize=12,
            leading=15,
            textColor=colors.HexColor("#172033"),
        ),
        "contact": ParagraphStyle(
            "CVContact",
            parent=base_styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#475569"),
        ),
        "section_heading": ParagraphStyle(
            "CVSectionHeading",
            parent=base_styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor("#1d4ed8"),
            spaceBefore=4,
            spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "CVBody",
            parent=base_styles["Normal"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=12.5,
            textColor=colors.HexColor("#172033"),
        ),
        "body_bold": ParagraphStyle(
            "CVBodyBold",
            parent=base_styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9.5,
            leading=12.5,
            textColor=colors.HexColor("#172033"),
        ),
        "bullet": ParagraphStyle(
            "CVBullet",
            parent=base_styles["Normal"],
            fontName="Helvetica",
            fontSize=9.2,
            leading=12.2,
            leftIndent=0,
            textColor=colors.HexColor("#172033"),
        ),
    }


def build_work_experience_pdf_flowables(raw_content: str, styles: dict[str, ParagraphStyle]) -> list[Any]:
    lines = [line for line in raw_content.splitlines() if line.strip()]
    if len(lines) < 3:
        return [Paragraph(html.escape(line), styles["body"]) for line in lines]

    employer, date = split_tabbed_line(lines[0])
    flowables: list[Any] = [build_pdf_entry_heading(employer, date, styles), Paragraph(html.escape(lines[1]), styles["body_bold"])]
    flowables.append(build_pdf_bullet_list(lines[2:], styles))
    return flowables


def build_education_pdf_flowables(raw_content: str, styles: dict[str, ParagraphStyle]) -> list[Any]:
    lines = [line for line in raw_content.splitlines() if line.strip()]
    if lines and lines[0] == "EDUCATION":
        lines = lines[1:]
    if len(lines) < 2:
        return [Paragraph(html.escape(line), styles["body"]) for line in lines]

    school, date = split_tabbed_line(lines[0])
    return [build_pdf_entry_heading(school, date, styles), build_pdf_bullet_list(lines[1:], styles)]


def build_pdf_entry_heading(left_text: str, right_text: str, styles: dict[str, ParagraphStyle]) -> Table:
    table = Table(
        [[Paragraph(html.escape(left_text), styles["body_bold"]), Paragraph(html.escape(right_text), styles["body_bold"])]],
        colWidths=[4.95 * inch, 1.25 * inch],
    )
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ]))
    return table


def build_pdf_bullet_list(lines: list[str], styles: dict[str, ParagraphStyle]) -> ListFlowable:
    return ListFlowable(
        [ListItem(Paragraph(html.escape(line), styles["bullet"]), leftIndent=10) for line in lines],
        bulletType="bullet",
        start="circle",
        leftIndent=14,
        bulletFontName="Helvetica",
        bulletFontSize=6,
    )


def visible_content_lines(raw_content: str, section: object | None = None) -> list[str]:
    lines = [line for line in raw_content.splitlines() if line.strip()]
    if lines and section and lines[0] == str(section):
        return lines[1:]
    return lines


def format_label_line(line: str) -> str:
    if ":" not in line:
        return html.escape(line)
    label, value = line.split(":", 1)
    return f"<b>{html.escape(label)}:</b>{html.escape(value)}"


def build_html_section(record: dict[str, Any]) -> str:
    chunk_index = record.get("chunk_index")
    anchor = f"chunk-{chunk_index}"
    category = html.escape(str(record.get("category") or ""), quote=True)
    title = html.escape(str(record.get("title") or ""))
    raw_content = str(record.get("content") or "")
    content = html.escape(raw_content)
    class_name = html.escape(str(record.get("category") or "document").replace(" ", "-"), quote=True)

    if chunk_index == 1:
        lines = raw_content.splitlines()
        name = html.escape(lines[0] if lines else title)
        subtitle = html.escape("\n".join(lines[1:]))
        body = f"<h1>{name}</h1>\n      <p class=\"profile-title\">{subtitle}</p>"
    elif record.get("category") == "contact":
        body = f"<pre>{content}</pre>"
    elif record.get("category") == "work experience":
        body = f"<h2>{title}</h2>\n      {build_work_experience_html(raw_content)}"
    elif record.get("category") == "education":
        body = f"<h2>{title}</h2>\n      {build_education_html(raw_content)}"
    else:
        body = f"<h2>{title}</h2>\n      {build_paragraph_html(raw_content, record.get('section'))}"

    return f"""    <section id="{anchor}" class="{class_name}" data-chunk-index="{chunk_index}" data-category="{category}">
      {body}
    </section>"""


def build_work_experience_html(raw_content: str) -> str:
    lines = [line for line in raw_content.splitlines() if line.strip()]
    if len(lines) < 3:
        return build_paragraph_html(raw_content)

    employer, date = split_tabbed_line(lines[0])
    bullets = "\n".join(f"        <li>{html.escape(line)}</li>" for line in lines[2:])
    return f"""<div class="entry-heading"><span>{html.escape(employer)}</span><span>{html.escape(date)}</span></div>
      <p class="entry-role">{html.escape(lines[1])}</p>
      <ul>
{bullets}
      </ul>"""


def build_education_html(raw_content: str) -> str:
    lines = [line for line in raw_content.splitlines() if line.strip()]
    if lines and lines[0] == "EDUCATION":
        lines = lines[1:]
    if len(lines) < 2:
        return build_paragraph_html("\n".join(lines))

    school, date = split_tabbed_line(lines[0])
    bullets = "\n".join(f"        <li>{html.escape(line)}</li>" for line in lines[1:])
    return f"""<div class="entry-heading"><span>{html.escape(school)}</span><span>{html.escape(date)}</span></div>
      <ul>
{bullets}
      </ul>"""


def build_paragraph_html(raw_content: str, section: object | None = None) -> str:
    lines = [line for line in raw_content.splitlines() if line.strip()]
    if lines and section and lines[0] == str(section):
        lines = lines[1:]
    return "\n      ".join(f"<p>{html.escape(line)}</p>" for line in lines)


def split_tabbed_line(line: str) -> tuple[str, str]:
    if "\t" not in line:
        return line, ""
    first, second = line.split("\t", 1)
    return first.strip(), second.strip()


def collect_until(paragraphs: list[str], start: int, stop_headings: set[str]) -> tuple[list[str], int]:
    values: list[str] = []
    index = start

    while index < len(paragraphs) and not is_stop_heading(paragraphs[index], stop_headings):
        values.append(paragraphs[index])
        index += 1

    return values, index


def is_stop_heading(paragraph: str, stop_headings: set[str]) -> bool:
    return paragraph in stop_headings or ("LANGUAGES" in stop_headings and paragraph.startswith("LANGUAGES:"))


def build_knowledge(paragraphs: list[str]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    chunk_index = 1
    index = 0

    if len(paragraphs) >= 2:
        content = "\n".join(paragraphs[0:2])
        records.append(make_record("cv-header-name-title", "CV Header - Name and Title", "profile", "Header", chunk_index, content))
        chunk_index += 1
        index = 2

    if index < len(paragraphs) and "@" in paragraphs[index]:
        records.append(make_record("cv-header-contact", "CV Header - Contact Information", "contact", "Header", chunk_index, paragraphs[index]))
        chunk_index += 1
        index += 1

    while index < len(paragraphs):
        paragraph = paragraphs[index]

        if paragraph == "SUMMARY":
            content_lines, index = collect_until(paragraphs, index, {"LANGUAGES", "EDUCATION", "TECHNICAL SKILLS", "WORK EXPERIENCE"})
            records.append(make_record("cv-summary", "Summary", "summary", "SUMMARY", chunk_index, "\n".join(content_lines)))
            chunk_index += 1
            continue

        if paragraph.startswith("LANGUAGES:"):
            records.append(make_record("cv-languages", "Languages", "languages", "LANGUAGES", chunk_index, paragraph))
            chunk_index += 1
            index += 1
            continue

        if paragraph == "EDUCATION":
            content_lines, index = collect_until(paragraphs, index, {"TECHNICAL SKILLS", "WORK EXPERIENCE"})
            records.append(make_record("cv-education-eastern-michigan-university", "Education - Eastern Michigan University", "education", "EDUCATION", chunk_index, "\n".join(content_lines)))
            chunk_index += 1
            continue

        if paragraph == "TECHNICAL SKILLS":
            index += 1
            while index < len(paragraphs) and paragraphs[index] != "WORK EXPERIENCE":
                line = paragraphs[index]
                label = line.split(":", 1)[0]
                if label == "Certifications":
                    category = "certifications"
                    title = "Certifications"
                    record_id = "cv-certifications"
                else:
                    category = "technical skills"
                    title = f"Technical Skills - {label}"
                    record_id = f"cv-technical-skills-{slugify(label)}"
                records.append(make_record(record_id, title, category, "TECHNICAL SKILLS", chunk_index, line))
                chunk_index += 1
                index += 1
            continue

        if paragraph == "WORK EXPERIENCE":
            index += 1
            work_records, chunk_index = build_work_experience_records(paragraphs[index:], chunk_index)
            records.extend(work_records)
            break

        index += 1

    return records


def build_work_experience_records(paragraphs: list[str], chunk_index: int) -> tuple[list[dict[str, Any]], int]:
    records: list[dict[str, Any]] = []
    index = 0

    while index < len(paragraphs):
        employer = paragraphs[index]
        if index + 1 >= len(paragraphs):
            break

        role = paragraphs[index + 1]
        index += 2
        content_lines = [employer, role]

        while index < len(paragraphs) and not is_employer_line(paragraphs[index]):
            content_lines.append(paragraphs[index])
            index += 1

        employer_name = normalize_employer_name(employer)
        record_id = f"cv-work-experience-{slugify(employer_name)}"
        title = f"Work Experience - {employer_name}"
        content = "\n".join(content_lines)
        records.append(make_record(record_id, title, "work experience", "WORK EXPERIENCE", chunk_index, content))
        chunk_index += 1

    return records, chunk_index


def is_employer_line(text: str) -> bool:
    return bool(re.search(r"\d{4}\s*[–-]\s*(?:\d{4}|Present)", text))


def normalize_employer_name(text: str) -> str:
    return re.sub(r"\s*\d{4}\s*[–-]\s*(?:\d{4}|Present).*", "", text).strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the RAG knowledge JSON from the CV docx file.")
    parser.add_argument("--cv", type=Path, default=DEFAULT_CV_PATH, help="Path to the source CV .docx file.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH, help="Path to write the generated knowledge JSON.")
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT_PATH, help="Path to write the generated CV HTML file.")
    parser.add_argument("--pdf-output", type=Path, default=DEFAULT_PDF_OUTPUT_PATH, help="Path to write the generated CV PDF file.")
    args = parser.parse_args()

    paragraphs = extract_docx_paragraphs(args.cv)
    records = build_knowledge(paragraphs)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(records, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(build_html_document(records), encoding="utf-8")
    args.pdf_output.parent.mkdir(parents=True, exist_ok=True)
    build_pdf_document(records, args.pdf_output)
    print(f"====> Wrote {len(records)} records to {args.output}")
    print(f"====> Wrote CV HTML to {args.html_output}")
    print(f"====> Wrote CV PDF to {args.pdf_output}")
    print("====> Knowledge generation complete!")


if __name__ == "__main__":
    main()
