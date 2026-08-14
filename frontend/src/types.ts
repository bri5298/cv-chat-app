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