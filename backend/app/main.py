import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.models import ChatRequest, ChatResponse
from backend.app.rag_chat import create_answer, load_knowledge, source_from_record

load_dotenv()

app = FastAPI(title="CV Chat API")

allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in allowed_origins if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    records = load_knowledge()

    if not records:
        return ChatResponse(answer="I do not know.", sources=[])

    answer, used_chunk_indexes = create_answer(request.message, records)
    sources = [
        source_from_record(record, index)
        for index, record in enumerate(records)
        if record.get("chunk_index") in used_chunk_indexes
    ]

    return ChatResponse(answer=answer, sources=sources)
