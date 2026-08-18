import os
import logging
import json
import urllib.error
import urllib.request

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.app.models import ChatMessage, ChatRequest, ChatResponse, ErrorReportRequest
from backend.app.rag_chat import create_answer, load_knowledge, source_from_record

load_dotenv()

logger = logging.getLogger(__name__)

MAX_ERROR_TEXT_LENGTH = 2_000
MAX_CONTEXT_TEXT_LENGTH = 1_000
MAX_REPORT_CONVERSATION_MESSAGES = 6
RESEND_EMAILS_URL = "https://api.resend.com/emails"

app = FastAPI(title="CV Chat API")

allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in allowed_origins if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def truncate_text(value: str | None, max_length: int) -> str:
    if not value:
        return ""

    value = value.strip()
    if len(value) <= max_length:
        return value

    return f"{value[:max_length].rstrip()}..."


def format_conversation(messages: list[ChatMessage]) -> str:
    recent_messages = messages[-MAX_REPORT_CONVERSATION_MESSAGES:]
    if not recent_messages:
        return "No conversation context was provided."

    return "\n\n".join(
        f"{message.role}: {truncate_text(message.content, MAX_CONTEXT_TEXT_LENGTH)}"
        for message in recent_messages
    )


def create_error_report_email(request: ErrorReportRequest) -> str:
    return "\n\n".join(
        [
            "A CV Assistant user submitted an error report.",
            f"Error:\n{truncate_text(request.error_message, MAX_ERROR_TEXT_LENGTH)}",
            f"Last user message:\n{truncate_text(request.last_user_message, MAX_CONTEXT_TEXT_LENGTH) or 'Not provided.'}",
            f"Recent conversation:\n{format_conversation(request.recent_conversation)}",
            f"Page URL:\n{truncate_text(request.page_url, MAX_CONTEXT_TEXT_LENGTH) or 'Not provided.'}",
            f"Timestamp:\n{truncate_text(request.timestamp, 120) or 'Not provided.'}",
            f"User agent:\n{truncate_text(request.user_agent, MAX_CONTEXT_TEXT_LENGTH) or 'Not provided.'}",
        ]
    )


def send_error_report_email(api_key: str, from_email: str, to_email: str, body: str) -> None:
    payload = json.dumps(
        {
            "from": from_email,
            "to": [to_email],
            "subject": "CV chat app Vercel error reported!",
            "text": body,
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        RESEND_EMAILS_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "cv-chat-app/1.0",
        },
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=10) as response:
        if response.status >= 400:
            raise RuntimeError(f"Resend returned status {response.status}.")


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    records = load_knowledge()

    if not records:
        return ChatResponse(answer="I do not know.", sources=[])

    answer, used_chunk_indexes = create_answer(request.message, records, request.history)
    sources = [
        source_from_record(record, index)
        for index, record in enumerate(records)
        if record.get("chunk_index") in used_chunk_indexes
    ]

    return ChatResponse(answer=answer, sources=sources)


@app.post("/api/error-report")
def report_error(request: ErrorReportRequest) -> dict[str, str]:
    if not request.error_message.strip():
        raise HTTPException(status_code=400, detail="An error message is required.")

    api_key = os.getenv("RESEND_API_KEY", "").strip()
    from_email = os.getenv("ERROR_REPORT_FROM_EMAIL", "").strip()
    to_email = os.getenv("ERROR_REPORT_TO_EMAIL", "").strip()

    if not api_key or not from_email or not to_email:
        logger.error("Error report email is not configured.")
        raise HTTPException(status_code=500, detail="Error reporting is not configured.")

    try:
        send_error_report_email(api_key, from_email, to_email, create_error_report_email(request))
    except (urllib.error.URLError, TimeoutError, RuntimeError) as error:
        logger.exception("Failed to send error report email.")
        raise HTTPException(status_code=502, detail="Unable to send the error report right now.") from error

    return {"status": "sent"}
