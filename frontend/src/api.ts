import type { ChatRequest, ChatResponse, ErrorReportRequest, ErrorReportResponse } from "./types";

const API_BASE_URL = "/api";

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
    throw new Error(await getApiErrorMessage(response, "Unable to get a response from the chat API."));
  }

  return response.json();
}

export async function sendErrorReport(
  request: ErrorReportRequest,
): Promise<ErrorReportResponse> {
  const response = await fetch(`${API_BASE_URL}/error-report`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      error_message: request.errorMessage,
      last_user_message: request.lastUserMessage,
      recent_conversation: request.recentConversation,
      page_url: request.pageUrl,
      user_agent: request.userAgent,
      timestamp: request.timestamp,
    }),
  });

  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, "Unable to send the error report right now."));
  }

  return response.json();
}

async function getApiErrorMessage(response: Response, fallbackMessage: string): Promise<string> {
  try {
    const data: unknown = await response.json();

    if (
      typeof data === "object" &&
      data !== null &&
      "detail" in data &&
      typeof data.detail === "string"
    ) {
      return data.detail;
    }
  } catch {
    // Fall through to the generic message.
  }

  return fallbackMessage;
}