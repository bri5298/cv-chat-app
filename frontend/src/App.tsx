import { useEffect, useRef, useState } from "react";
import type { FormEventHandler } from "react";
import { ApiError, sendChatMessage, sendErrorReport } from "./api";
import { faqItems } from "./content/faq.ts";
import { DownloadIcon } from "./icons/DownloadIcon";
import type { ChatMessage, ErrorReportRequest, Source } from "./types";
import "./App.css";

type ConversationMessage = ChatMessage & {
  sources?: Source[];
  isError?: boolean;
  errorDetail?: string;
  errorReport?: ErrorReportRequest;
};

type ErrorReportStatus = "idle" | "sending" | "sent" | "failed";

const suggestedQuestions = [
  "Has she taken AI solutions from prototype to production?",
  "What backend systems has she built for AI applications?",
  "What machine learning solutions has she built?",
];

function createReportId() {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }

  return `report-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

function getSourceUrl(source: Source) {
  return `${source.document_url ?? "/cv.html"}#${source.anchor ?? `chunk-${source.chunk_index}`}`;
}

function renderCitationContent(source: Source) {
  const lines = (source.content ?? "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);

  if (lines.length === 0) {
    return <p>No citation text is available for this source.</p>;
  }

  if (lines.length === 1) {
    return <p>{lines[0]}</p>;
  }

  const metaLines = lines.length > 2 ? lines.slice(0, 2) : lines.slice(0, 1);
  const detailLines = lines.slice(metaLines.length);

  return (
    <>
      <div className="citation-meta">
        {metaLines.map((line) => (
          <p key={line}>{line}</p>
        ))}
      </div>

      {detailLines.length === 1 ? (
        <p className="citation-detail">{detailLines[0]}</p>
      ) : (
        <ul>
          {detailLines.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      )}
    </>
  );
}

function App() {
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [errorReportStatus, setErrorReportStatus] = useState<ErrorReportStatus>("idle");
  const [errorReportFeedback, setErrorReportFeedback] = useState("");
  const [expandedSourceKey, setExpandedSourceKey] = useState<string | null>(null);
  const [selectedFaqIndex, setSelectedFaqIndex] = useState<number | null>(null);
  const [modalSource, setModalSource] = useState<Source | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const selectedFaqItem = selectedFaqIndex === null ? null : faqItems[selectedFaqIndex];

  useEffect(() => {
    const inputElement = inputRef.current;

    if (!inputElement) {
      return;
    }

    inputElement.style.height = "auto";
    const maxHeight = Number.parseFloat(getComputedStyle(inputElement).maxHeight);
    const nextHeight = Number.isFinite(maxHeight)
      ? Math.min(inputElement.scrollHeight, maxHeight)
      : inputElement.scrollHeight;

    inputElement.style.height = `${nextHeight}px`;
    inputElement.style.overflowY = inputElement.scrollHeight > nextHeight ? "auto" : "hidden";
  }, [input]);

  useEffect(() => {
    if (!modalSource && !selectedFaqItem) {
      return;
    }

    const originalBodyOverflow = document.body.style.overflow;

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setModalSource(null);
        setSelectedFaqIndex(null);
      }
    };

    document.body.style.overflow = "hidden";
    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.body.style.overflow = originalBodyOverflow;
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [modalSource, selectedFaqItem]);

  const handleSubmit: FormEventHandler<HTMLFormElement> = async (event) => {
    event.preventDefault();

    const message = input.trim();

    if (!message || isLoading) {
      return;
    }

    const userMessage: ConversationMessage = {
      role: "user",
      content: message,
    };

    const nextMessages = [...messages, userMessage];
    const reportId = createReportId();

    setMessages(nextMessages);
    setInput("");
    setErrorReportStatus("idle");
    setErrorReportFeedback("");
    setExpandedSourceKey(null);
    setModalSource(null);
    setIsLoading(true);

    try {
      const response = await sendChatMessage({
        message,
        history: nextMessages.map(({ role, content }) => ({ role, content })),
        reportId,
      });

      const assistantMessage: ConversationMessage = {
        role: "assistant",
        content: response.answer,
        sources: response.sources,
      };

      setMessages([...nextMessages, assistantMessage]);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : "Something went wrong while asking the CV assistant.";
      const isReportable = error instanceof ApiError ? error.reportable : true;
      const errorReport: ErrorReportRequest | undefined = isReportable ? {
        reportId,
        reportable: isReportable,
        errorMessage,
        lastUserMessage: message,
        recentConversation: nextMessages.slice(-6).map(({ role, content }) => ({ role, content })),
        pageUrl: window.location.href,
        userAgent: navigator.userAgent,
        timestamp: new Date().toISOString(),
      } : undefined;
      const assistantErrorMessage: ConversationMessage = {
        role: "assistant",
        content: isReportable
          ? "I could not get a response from the CV assistant. You can try again, or send Brielle the details so she can look into it."
          : "I could not get a response from the CV assistant. Try the suggested step below, then ask again.",
        isError: true,
        errorDetail: errorMessage,
        errorReport,
      };

      setErrorReportStatus("idle");
      setErrorReportFeedback("");
      setMessages([...nextMessages, assistantErrorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSendErrorReport = async (errorReport: ErrorReportRequest) => {
    if (errorReportStatus === "sending" || errorReportStatus === "sent") {
      return;
    }

    setErrorReportStatus("sending");
    setErrorReportFeedback("");

    try {
      await sendErrorReport(errorReport);
      setErrorReportStatus("sent");
      setErrorReportFeedback("Thank you, Brielle has been sent the details.");
    } catch (error) {
      setErrorReportStatus("failed");
      setErrorReportFeedback(error instanceof Error ? error.message : "The report could not be sent right now.");
    }
  };

  const handleClearConversation = () => {
    setMessages([]);
    setInput("");
    setErrorReportStatus("idle");
    setErrorReportFeedback("");
    setExpandedSourceKey(null);
    setModalSource(null);
  };

  const canClearConversation = messages.length > 0 || input.trim().length > 0;

  return (
    <main className="app-shell">
      <section className="workspace" aria-label="CV chat workspace">
        <aside className="profile-rail">
          <div className="brand-lockup">
            <div>
              <h1 className="rail-title">Brielle's CV Assistant</h1>
            </div>
          </div>

          <p className="rail-copy">
            Is Brielle a good fit for your team? <br />
            Ask about her experience, skills, projects, and accomplishments. Answers are drawn directly from her CV.
          </p>

          <section className="rail-faq" aria-label="CV assistant FAQ">
            <p className="rail-faq-label">FAQ</p>
            {faqItems.map((item, index) => {
              return (
                <div className="rail-faq-item" key={item.question}>
                  <button
                    aria-haspopup="dialog"
                    className="rail-faq-trigger"
                    onClick={() => setSelectedFaqIndex(index)}
                    type="button"
                  >
                    <span>{item.question}</span>
                    <span aria-hidden="true">›</span>
                  </button>
                </div>
              );
            })}
          </section>

          <a
            aria-label="Download Brielle Johnston CV"
            className="download-cv"
            href="/cv.pdf"
            download="Brielle Johnston CV.pdf"
          >
            <span className="download-cv-full">Download her CV</span>
            <span className="download-cv-mobile" aria-hidden="true">
              CV
              <DownloadIcon />
            </span>
          </a>
        </aside>

        <section className="chat-panel" aria-label="CV chat">
          <header className="chat-header">
            <div>
              <h2>Ask about Brielle's Resume</h2>
            </div>

            {canClearConversation ? (
              <button
                className="clear-conversation"
                disabled={isLoading}
                onClick={handleClearConversation}
                type="button"
              >
                Clear conversation
              </button>
            ) : null}
          </header>

          <div className="message-list" aria-live="polite">
            {messages.length === 0 ? (
              <div className="empty-state">
                <span>Start with a prompt</span>
                <p>Choose a question or ask about anything specific</p>
                <div className="suggestions">
                  {suggestedQuestions.map((question) => (
                    <button
                      key={question}
                      type="button"
                      onClick={() => setInput(question)}
                    >
                      {question}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((message, index) => {
                const expandedSource = message.sources?.find(
                  (source) => expandedSourceKey === `${index}-${source.id}`,
                );

                return (
                  <article
                    className={`message message-${message.role}${message.isError ? " message-error" : ""}`}
                    key={`${message.role}-${index}`}
                    role={message.isError ? "alert" : undefined}
                  >
                    <div className="message-label">
                      {message.role === "user" ? "You" : "Assistant"}
                    </div>

                    {message.isError ? (
                      <div className="error-report-panel">
                        <div className="error-report-copy">
                          <p className="error-report-title">Something went wrong</p>
                          <p>{message.content}</p>
                          {message.errorReport ? (
                            <>
                              <p className="error-report-detail">Details: {message.errorReport.errorMessage}</p>
                              <p className="error-report-id">Report ID: {message.errorReport.reportId}</p>
                            </>
                          ) : (
                            <p className="error-report-detail">Details: {message.errorDetail}</p>
                          )}
                        </div>
                      </div>
                    ) : (
                      <p>{message.content}</p>
                    )}

                    {message.isError && message.errorReport ? (
                      <div className="error-report-actions">
                        <button
                          disabled={errorReportStatus === "sending" || errorReportStatus === "sent"}
                          onClick={() => handleSendErrorReport(message.errorReport as ErrorReportRequest)}
                          type="button"
                        >
                          {errorReportStatus === "sending"
                            ? "Sending report"
                            : errorReportStatus === "sent"
                              ? "Report sent"
                              : "Notify Brielle"}
                        </button>

                        {errorReportFeedback ? <span>{errorReportFeedback}</span> : null}
                      </div>
                    ) : null}

                    {message.sources && message.sources.length > 0 ? (
                      <>
                        <div className="sources" aria-label="Sources">
                          {message.sources.map((source) => {
                            const sourceKey = `${index}-${source.id}`;

                            return (
                              <button
                                aria-expanded={expandedSourceKey === sourceKey}
                                className="source"
                                key={source.id}
                                onClick={() =>
                                  setExpandedSourceKey(
                                    expandedSourceKey === sourceKey ? null : sourceKey,
                                  )
                                }
                                type="button"
                              >
                                {source.title}
                              </button>
                            );
                          })}
                        </div>

                        {expandedSource ? (
                          <div className="citation-card">
                            <div className="citation-card-header">
                              <h3>{expandedSource.title}</h3>
                              <button
                                className="citation-card-action"
                                onClick={() => setModalSource(expandedSource)}
                                type="button"
                              >
                                View it in CV
                              </button>
                            </div>
                            <div className="citation-card-body">
                              {renderCitationContent(expandedSource)}
                            </div>
                          </div>
                        ) : null}
                      </>
                    ) : null}
                  </article>
                );
              })
            )}

            {isLoading ? (
              <article className="message message-assistant">
                <div className="message-label">Assistant</div>
                <p>Thinking...</p>
              </article>
            ) : null}
          </div>

          <form className="composer" onSubmit={handleSubmit} autoComplete="off">
            <div className="input-wrap">
              <label className="sr-only" htmlFor="chat-message">
                Ask a question
              </label>
              <textarea
                id="chat-message"
                ref={inputRef}
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
                    event.preventDefault();
                    event.currentTarget.form?.requestSubmit();
                  }
                }}
                placeholder="Ask about skills, projects, or experience"
                rows={1}
              />
            </div>
            <button type="submit" disabled={isLoading || !input.trim()}>
              Send
            </button>
          </form>
        </section>

      </section>

      {selectedFaqItem ? (
        <div
          className="cv-modal-backdrop"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) {
              setSelectedFaqIndex(null);
            }
          }}
        >
          <section
            aria-labelledby="faq-modal-title"
            aria-modal="true"
            className="faq-modal"
            role="dialog"
          >
            <header className="faq-modal-header">
              <p className="eyebrow">FAQ</p>
              <button type="button" onClick={() => setSelectedFaqIndex(null)}>
                Close
              </button>
            </header>
            <div className="faq-modal-body">
              <h2 id="faq-modal-title">{selectedFaqItem.question}</h2>
              {selectedFaqItem.answer.map((paragraph) => (
                <p key={paragraph}>{paragraph}</p>
              ))}
            </div>
          </section>
        </div>
      ) : null}

      {modalSource ? (
        <div
          className="cv-modal-backdrop"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) {
              setModalSource(null);
            }
          }}
        >
          <section
            aria-label={`${modalSource.title} in CV`}
            aria-modal="true"
            className="cv-modal"
            role="dialog"
          >
            <header className="cv-modal-header">
              <div>
                <p className="eyebrow">Source in CV</p>
                <h2>{modalSource.title}</h2>
              </div>
              <button type="button" onClick={() => setModalSource(null)}>
                Close
              </button>
            </header>
            <iframe
              key={getSourceUrl(modalSource)}
              src={getSourceUrl(modalSource)}
              title="CV source document"
            />
          </section>
        </div>
      ) : null}
    </main>
  );
}

export default App;