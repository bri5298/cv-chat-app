import argparse
import json
import re
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET
from zipfile import ZipFile

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CV_PATH = ROOT_DIR / "app" / "data" / "Brielle Johnston CV EN.docx"
DEFAULT_OUTPUT_PATH = ROOT_DIR / "app" / "data" / "knowledge.json"
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
    }


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
    args = parser.parse_args()

    paragraphs = extract_docx_paragraphs(args.cv)
    records = build_knowledge(paragraphs)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(records, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(records)} records to {args.output}")


if __name__ == "__main__":
    main()
