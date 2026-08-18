import type { ChatRequest, ChatResponse, ErrorReportRequest, ErrorReportResponse } from "./types";

const API_BASE_URL = "/api";

export class ApiError extends Error {
  reportable: boolean;

  constructor(message: string, reportable = true) {
    super(message);
    this.name = "ApiError";
    this.reportable = reportable;
  }
}

export async function sendChatMessage(
  request: ChatRequest,
): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE_URL}/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      message: request.message,
      history: request.history,
      report_id: request.reportId,
    }),
  });

  if (!response.ok) {
    throw await getApiError(response, "Unable to get a response from the chat API.");
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
      report_id: request.reportId,
      reportable: request.reportable,
      error_message: request.errorMessage,
      last_user_message: request.lastUserMessage,
      recent_conversation: request.recentConversation,
      page_url: request.pageUrl,
      user_agent: request.userAgent,
      timestamp: request.timestamp,
    }),
  });

  if (!response.ok) {
    throw await getApiError(response, "Unable to send the error report right now.");
  }

  return response.json();
}

async function getApiError(response: Response, fallbackMessage: string): Promise<ApiError> {
  try {
    const data: unknown = await response.json();

    if (
      typeof data === "object" &&
      data !== null &&
      "detail" in data
    ) {
      if (typeof data.detail === "string") {
        return new ApiError(data.detail);
      }

      if (
        typeof data.detail === "object" &&
        data.detail !== null &&
        "message" in data.detail &&
        typeof data.detail.message === "string"
      ) {
        const reportable = "reportable" in data.detail && typeof data.detail.reportable === "boolean"
          ? data.detail.reportable
          : true;

        return new ApiError(data.detail.message, reportable);
      }
    }
  } catch {
    // Fall through to the generic message.
  }

  return new ApiError(fallbackMessage);
}