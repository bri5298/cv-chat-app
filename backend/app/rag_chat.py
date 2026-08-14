import json
import os
import re
from pathlib import Path
from typing import Any

import groq
from fastapi import HTTPException
from groq import Groq

from backend.app.models import Source
from backend.app.constants import (
    FALLBACK_MODEL_IDS,
    FALLBACK_ERROR_TERMS,
    TEMPERATURE,
    ANSWER_MAX_TOKENS,
)


KNOWLEDGE_PATH = os.path.join(Path(__file__).parent, "data", "knowledge.json")
SYSTEM_PROMPT_PATH = Path(__file__).parent / "prompts" / "system.md"
SYSTEM_MESSAGE = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8").strip()
CHUNK_INDEX_PATTERN = re.compile(r"<<\s*(?:chunk[-_\s]?index\s*[-=:]?\s*)?(\d+)\s*>>", re.IGNORECASE)
SOURCE_MARKER_BLOCK_PATTERN = re.compile(r"<<\s*([^<>]+?)\s*>>")
INTEGER_PATTERN = re.compile(r"\d+")

def load_knowledge() -> list[dict[str, Any]]:
    if not os.path.exists(KNOWLEDGE_PATH):
        return []

    with open(KNOWLEDGE_PATH, "r", encoding="utf-8") as file:
        data = json.load(file)

    if isinstance(data, list):
        return [record for record in data if isinstance(record, dict)]

    if isinstance(data, dict):
        records = data.get("records") or data.get("items") or data.get("data")
        if isinstance(records, list):
            return [record for record in records if isinstance(record, dict)]
        return [data]

    return []

def source_from_record(record: dict[str, Any], index: int) -> Source:
    source_ref = record.get("source_ref") if isinstance(record.get("source_ref"), dict) else {}
    return Source(
        id=str(record.get("id") or record.get("slug") or f"source-{index + 1}"),
        title=str(record.get("title") or record.get("name") or f"Source {index + 1}"),
        content=str(record.get("content") or ""),
        chunk_index=record.get("chunk_index") if isinstance(record.get("chunk_index"), int) else None,
        document_url=source_ref.get("document_url"),
        anchor=source_ref.get("anchor"),
    )


def create_model_context(records: list[dict[str, Any]]) -> str:
    return "\n\n".join(
        "\n".join(
            (
                f"chunk_index={record.get('chunk_index')}",
                f"model_content={record.get('title') or ''}\n{record.get('content') or ''}",
            )
        )
        for index, record in enumerate(records)
    )


def normalize_chunk_indexes(values: Any, valid_chunk_indexes: set[int]) -> set[int]:
    if not isinstance(values, list):
        return set()

    chunk_indexes: set[int] = set()
    for value in values:
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            chunk_index = value
        elif isinstance(value, str) and value.strip().isdigit():
            chunk_index = int(value.strip())
        else:
            continue

        if chunk_index in valid_chunk_indexes:
            chunk_indexes.add(chunk_index)

    return chunk_indexes


def clean_answer_and_chunk_indexes(
    answer: str,
    valid_chunk_indexes: set[int],
) -> tuple[str, set[int]]:
    chunk_indexes = {
        int(match)
        for match in CHUNK_INDEX_PATTERN.findall(answer)
        if int(match) in valid_chunk_indexes
    }

    for marker_content in SOURCE_MARKER_BLOCK_PATTERN.findall(answer):
        for match in INTEGER_PATTERN.findall(marker_content):
            chunk_index = int(match)
            if chunk_index in valid_chunk_indexes:
                chunk_indexes.add(chunk_index)

    clean_answer = SOURCE_MARKER_BLOCK_PATTERN.sub("", answer).strip()
    return clean_answer, chunk_indexes


def load_structured_answer(content: str) -> dict[str, Any] | None:
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        json_start = content.find("{")
        json_end = content.rfind("}")
        if json_start == -1 or json_end <= json_start:
            return None
        try:
            data = json.loads(content[json_start:json_end + 1])
        except json.JSONDecodeError:
            return None

    return data if isinstance(data, dict) else None


def parse_model_response(content: str, valid_chunk_indexes: set[int]) -> tuple[str, set[int]]:
    data = load_structured_answer(content)
    if data is None:
        return clean_answer_and_chunk_indexes(content, valid_chunk_indexes)

    answer = str(data.get("answer") or "I do not know.")
    clean_answer, fallback_chunk_indexes = clean_answer_and_chunk_indexes(answer, valid_chunk_indexes)
    chunk_indexes = normalize_chunk_indexes(data.get("chunk_indexes"), valid_chunk_indexes)
    return clean_answer or "I do not know.", chunk_indexes or fallback_chunk_indexes


def should_try_next_model(error: groq.BadRequestError) -> bool:
    error_text = str(error.body or error.message).lower()
    return any(term in error_text for term in FALLBACK_ERROR_TERMS)


def create_answer(message: str, records: list[dict[str, Any]]) -> tuple[str, set[int]]:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="The assistant is not configured correctly.",
        )

    client = Groq(api_key=api_key)
    last_error: Exception | None = None
    valid_chunk_indexes = {
        record["chunk_index"]
        for record in records
        if isinstance(record.get("chunk_index"), int)
    }

    for model in FALLBACK_MODEL_IDS:
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": SYSTEM_MESSAGE,
                    },
                    {
                        "role": "user",
                        "content": f"Knowledge base context:\n{create_model_context(records)}\n\nQuestion:\n{message}",
                    },
                ],
                response_format={"type": "json_object"},
                temperature=TEMPERATURE,
                max_tokens=ANSWER_MAX_TOKENS,
            )

            return parse_model_response(
                response.choices[0].message.content or "I do not know.",
                valid_chunk_indexes,
            )
        except groq.RateLimitError as error:
            last_error = error
        except groq.BadRequestError as error:
            if not should_try_next_model(error):
                raise HTTPException(
                    status_code=502,
                    detail="The chat model rejected the request.",
                ) from error
            last_error = error

    raise HTTPException(
        status_code=503,
        detail="All configured Groq models are currently unavailable or over limit.",
    ) from last_error