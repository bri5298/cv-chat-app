import argparse
import html
import json
import shutil
import subprocess
import re
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET
from zipfile import ZipFile

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
    sections = "\n".join(build_html_sections(records))
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

        .experience-bullet {{
            scroll-margin-top: 24px;
            border-radius: 6px;
            transition: background-color 160ms ease, box-shadow 160ms ease;
        }}

        .experience-bullet:target {{
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


def build_html_sections(records: list[dict[str, Any]]) -> list[str]:
    sections: list[str] = []
    index = 0

    while index < len(records):
        record = records[index]
        if record.get("category") != "work experience":
            sections.append(build_html_section(record))
            index += 1
            continue

        group = [record]
        group_key = work_experience_group_key(record)
        index += 1

        while (
            index < len(records)
            and records[index].get("category") == "work experience"
            and work_experience_group_key(records[index]) == group_key
        ):
            group.append(records[index])
            index += 1

        sections.append(build_work_experience_section(group))

    return sections


def convert_to_pdf(input_path: Path, output_path: Path) -> None:
    converter = find_libreoffice_executable()
    if converter is None:
        raise RuntimeError(
            "LibreOffice was not found. Install LibreOffice and make sure 'soffice' is on PATH, "
            "or install it in the default Windows/macOS application location."
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            str(converter),
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            str(output_path.parent),
            str(input_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        details = "\n".join(part for part in [result.stdout.strip(), result.stderr.strip()] if part)
        raise RuntimeError(f"LibreOffice failed to convert {input_path} to PDF.\n{details}")

    generated_path = output_path.parent / f"{input_path.stem}.pdf"
    if not generated_path.exists():
        raise RuntimeError(f"LibreOffice did not create the expected PDF: {generated_path}")

    if generated_path != output_path:
        generated_path.replace(output_path)


def find_libreoffice_executable() -> Path | None:
    for command in ("soffice", "libreoffice"):
        executable = shutil.which(command)
        if executable:
            return Path(executable)

    candidates = [
        Path(r"C:\Program Files\LibreOffice\program\soffice.exe"),
        Path(r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"),
        Path("/Applications/LibreOffice.app/Contents/MacOS/soffice"),
    ]
    return next((candidate for candidate in candidates if candidate.exists()), None)


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


def work_experience_group_key(record: dict[str, Any]) -> tuple[str, str, str]:
    lines = visible_content_lines(str(record.get("content") or ""))
    employer = lines[0] if len(lines) > 0 else ""
    role = lines[1] if len(lines) > 1 else ""
    return str(record.get("title") or ""), employer, role


def build_work_experience_section(records: list[dict[str, Any]]) -> str:
    first_record = records[0]
    first_lines = visible_content_lines(str(first_record.get("content") or ""))
    if len(first_lines) < 3:
        return build_html_section(first_record)

    chunk_index = first_record.get("chunk_index")
    category = html.escape(str(first_record.get("category") or ""), quote=True)
    title = html.escape(str(first_record.get("title") or ""))
    employer, date = split_tabbed_line(first_lines[0])
    role = first_lines[1]
    bullets: list[str] = []

    for record in records:
        lines = visible_content_lines(str(record.get("content") or ""))
        if len(lines) < 3:
            continue
        bullet = "\n".join(lines[2:])
        bullet_anchor = f"chunk-{record.get('chunk_index')}"
        bullets.append(f"        <li id=\"{bullet_anchor}\" class=\"experience-bullet\">{html.escape(bullet)}</li>")

    bullet_items = "\n".join(bullets)
    return f"""    <section class="work-experience" data-chunk-index="{chunk_index}" data-category="{category}">
      <h2>{title}</h2>
      <div class="entry-heading"><span>{html.escape(employer)}</span><span>{html.escape(date)}</span></div>
      <p class="entry-role">{html.escape(role)}</p>
      <ul>
{bullet_items}
      </ul>
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
        bullet_lines: list[str] = []

        while index < len(paragraphs) and not is_employer_line(paragraphs[index]):
            bullet_lines.append(paragraphs[index])
            index += 1

        employer_name = normalize_employer_name(employer)
        title = f"Work Experience - {employer_name}"
        if not bullet_lines:
            record_id = f"cv-work-experience-{slugify(employer_name)}"
            content = "\n".join([employer, role])
            records.append(make_record(record_id, title, "work experience", "WORK EXPERIENCE", chunk_index, content))
            chunk_index += 1
            continue

        for bullet_number, bullet in enumerate(bullet_lines, start=1):
            record_id = f"cv-work-experience-{slugify(employer_name)}-{bullet_number}"
            content = "\n".join([employer, role, bullet])
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
    convert_to_pdf(args.cv, args.pdf_output)
    print(f"====> Wrote {len(records)} records to {args.output}")
    print(f"====> Wrote CV HTML to {args.html_output}")
    print(f"====> Wrote CV PDF to {args.pdf_output}")
    print("====> Knowledge generation complete!")


if __name__ == "__main__":
    main()
