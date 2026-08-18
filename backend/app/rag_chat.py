import json
import logging
import os
import re
from pathlib import Path
from typing import Any

import groq
from fastapi import HTTPException
from groq import Groq

from backend.app.models import ChatMessage, Source
from backend.app.constants import (
    FALLBACK_MODEL_IDS,
    FALLBACK_ERROR_TERMS,
    TEMPERATURE,
    ANSWER_MAX_TOKENS,
    MAX_HISTORY_USER_MESSAGES
)


KNOWLEDGE_PATH = os.path.join(Path(__file__).parent, "data", "knowledge.json")
SYSTEM_PROMPT_PATH = Path(__file__).parent / "prompts" / "system.md"
SYSTEM_MESSAGE = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8").strip()
logger = logging.getLogger(__name__)
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


def create_history_context(history: list[ChatMessage], current_message: str) -> str:
    current_message = current_message.strip()
    user_messages = [
        item.content.strip()
        for item in history
        if item.role == "user" and item.content.strip()
    ]

    previous_user_messages = user_messages[:-1]

    numbered_user_messages = list(enumerate(previous_user_messages, start=1))
    recent_messages = numbered_user_messages[-MAX_HISTORY_USER_MESSAGES:]

    if not recent_messages:
        return ""

    lines = "\n".join(
        f"Question {question_number}: {message}"
        for question_number, message in recent_messages
    )
    first_question_number = recent_messages[0][0]
    last_question_number = recent_messages[-1][0]
    total_question_count = len(previous_user_messages)
    return (
        f"Recent user questions {first_question_number}-{last_question_number} "
        f"of {total_question_count}; earlier questions are omitted because only last {MAX_HISTORY_USER_MESSAGES} are shown:\n{lines}"
    )


def create_user_prompt(message: str, records: list[dict[str, Any]], history: list[ChatMessage]) -> str:
    parts = [
        f"Knowledge base context:\n{create_model_context(records)}",
    ]
    history_context = create_history_context(history, message)
    if history_context:
        parts.append(history_context)
    parts.append(f"Current question:\n{message}")
    return "\n\n".join(parts)


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


def groq_error_text(error: Exception) -> str:
    body = getattr(error, "body", None)
    if isinstance(body, dict):
        error_data = body.get("error")
        if isinstance(error_data, dict):
            return str(error_data.get("message") or error_data.get("code") or error_data)
        return str(body)

    return str(getattr(error, "message", "") or error)


def groq_error_status_code(error: Exception) -> int:
    if isinstance(error, groq.AuthenticationError):
        return 500
    if isinstance(error, groq.RateLimitError):
        return 429
    if isinstance(error, groq.APIConnectionError | groq.APITimeoutError | groq.InternalServerError):
        return 503
    if isinstance(error, groq.APIStatusError) and error.status_code == 413:
        return 413

    return 502


def groq_error_detail(error: Exception) -> str:
    error_text = groq_error_text(error)
    normalized_error = error_text.lower()
    model_issue_message = "The assistant hit a model issue. The site owner will need to fix it."

    if isinstance(error, groq.AuthenticationError):
        return model_issue_message

    if isinstance(error, groq.PermissionDeniedError):
        return model_issue_message

    if isinstance(error, groq.NotFoundError) or "model_not_found" in normalized_error or "does not exist" in normalized_error:
        return model_issue_message

    if isinstance(error, groq.RateLimitError):
        return "The assistant is receiving too many requests right now. Wait a bit and try again."

    if isinstance(error, groq.APIConnectionError | groq.APITimeoutError):
        return "The assistant could not reach the model provider. Try again in a moment."

    if isinstance(error, groq.InternalServerError):
        return "The model provider returned a server error. Try again in a moment."

    if "request entity too large" in normalized_error or "request_too_large" in normalized_error:
        return "The request is too large. Clear the conversation history and try again."

    if any(term in normalized_error for term in ("context", "token", "maximum", "too large", "limit")):
        return "The request is too large for the model. Clear the conversation history and try again."

    if "response_format" in normalized_error or "json" in normalized_error:
        return model_issue_message

    if "unsupported" in normalized_error or "invalid" in normalized_error:
        return model_issue_message

    return model_issue_message


def groq_error_reportable(error: Exception) -> bool:
    error_text = groq_error_text(error)
    normalized_error = error_text.lower()

    if isinstance(error, groq.AuthenticationError | groq.PermissionDeniedError | groq.NotFoundError):
        return True

    if isinstance(error, groq.RateLimitError | groq.APIConnectionError | groq.APITimeoutError | groq.InternalServerError):
        return False

    if isinstance(error, groq.APIStatusError) and error.status_code == 413:
        return False

    if "request entity too large" in normalized_error or "request_too_large" in normalized_error:
        return False

    if any(term in normalized_error for term in ("context", "token", "maximum", "too large", "limit")):
        return False

    if "model_not_found" in normalized_error or "does not exist" in normalized_error:
        return True

    if "response_format" in normalized_error or "json" in normalized_error:
        return True

    if "unsupported" in normalized_error or "invalid" in normalized_error:
        return True

    return True


def chat_error_detail(message: str, reportable: bool) -> dict[str, Any]:
    return {"message": message, "reportable": reportable}


def log_groq_error(model: str, error: Exception) -> None:
    logger.warning(
        "Groq request failed: model=%s error_type=%s status_code=%s error=%s",
        model,
        type(error).__name__,
        getattr(error, "status_code", None),
        groq_error_text(error),
    )


def create_answer(message: str, records: list[dict[str, Any]], history: list[ChatMessage] | None = None) -> tuple[str, set[int]]:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail=chat_error_detail("The assistant is not configured correctly.", True),
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
            user_prompt = create_user_prompt(message, records, history or [])
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": SYSTEM_MESSAGE,
                    },
                    {
                        "role": "user",
                        "content": user_prompt,
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
            log_groq_error(model, error)
            last_error = error
        except groq.NotFoundError as error:
            log_groq_error(model, error)
            last_error = error
        except groq.BadRequestError as error:
            log_groq_error(model, error)
            if not should_try_next_model(error):
                raise HTTPException(
                    status_code=groq_error_status_code(error),
                    detail=chat_error_detail(groq_error_detail(error), groq_error_reportable(error)),
                ) from error
            last_error = error
        except (
            groq.AuthenticationError,
            groq.PermissionDeniedError,
            groq.APIConnectionError,
            groq.APITimeoutError,
            groq.InternalServerError,
            groq.APIStatusError,
        ) as error:
            log_groq_error(model, error)
            raise HTTPException(
                status_code=groq_error_status_code(error),
                detail=chat_error_detail(groq_error_detail(error), groq_error_reportable(error)),
            ) from error

    raise HTTPException(
        status_code=groq_error_status_code(last_error) if last_error else 503,
        detail=chat_error_detail(
            groq_error_detail(last_error) if last_error else "The assistant hit a model issue. Try again later.",
            groq_error_reportable(last_error) if last_error else True,
        ),
    ) from last_error