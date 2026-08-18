export type Source = {
  id: string;
  title: string;
  content?: string;
  chunk_index?: number;
  document_url?: string;
  anchor?: string;
};

export type ChatRequest = {
  message: string;
  history: ChatMessage[];
};

export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

export type ChatResponse = {
  answer: string;
  sources: Source[];
};

export type ErrorReportRequest = {
  errorMessage: string;
  lastUserMessage?: string;
  recentConversation: ChatMessage[];
  pageUrl?: string;
  userAgent?: string;
  timestamp?: string;
};

export type ErrorReportResponse = {
  status: "sent";
};