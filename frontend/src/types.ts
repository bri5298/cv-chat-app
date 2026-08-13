export type Source = {
  id: string;
  title: string;
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