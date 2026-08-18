from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    history: list[ChatMessage] = Field(default_factory=list)


class Source(BaseModel):
    id: str
    title: str
    content: str | None = None
    chunk_index: int | None = None
    document_url: str | None = None
    anchor: str | None = None


class ChatResponse(BaseModel):
    answer: str
    sources: list[Source]


class ErrorReportRequest(BaseModel):
    error_message: str
    last_user_message: str | None = None
    recent_conversation: list[ChatMessage] = Field(default_factory=list)
    page_url: str | None = None
    user_agent: str | None = None
    timestamp: str | None = None