import type { ChatRequest, ChatResponse } from "./types";

const API_BASE_URL = import.meta.env.PROD ? "/api" : "http://localhost:8000";

export async function sendChatMessage(
  request: ChatRequest,
): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE_URL}/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new Error("Unable to get a response from the chat API.");
  }

  return response.json();
}