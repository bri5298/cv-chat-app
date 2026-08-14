import json
import os
import re
from pathlib import Path
from typing import Any

import groq
from fastapi import HTTPException
from groq import Groq

from app.models import Source
from app.constants import (
    FALLBACK_MODEL_IDS,
    FALLBACK_ERROR_TERMS,
    TEMPERATURE,
    ANSWER_MAX_TOKENS,
)


KNOWLEDGE_PATH = os.path.join(Path(__file__).parent, "data", "knowledge.json")
SYSTEM_PROMPT_PATH = Path(__file__).parent / "prompts" / "system.md"
SYSTEM_MESSAGE = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8").strip()
CHUNK_INDEX_PATTERN = re.compile(r"<<\s*(?:chunk[-_\s]?index\s*[-=:]?\s*)?(\d+)\s*>>", re.IGNORECASE)

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


def clean_answer_and_chunk_indexes(answer: str) -> tuple[str, set[int]]:
    chunk_indexes = {int(match) for match in CHUNK_INDEX_PATTERN.findall(answer)}
    clean_answer = CHUNK_INDEX_PATTERN.sub("", answer).strip()
    return clean_answer, chunk_indexes


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
                temperature=TEMPERATURE,
                max_tokens=ANSWER_MAX_TOKENS,
            )

            return clean_answer_and_chunk_indexes(response.choices[0].message.content or "I do not know.")
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