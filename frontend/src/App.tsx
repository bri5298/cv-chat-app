import { useEffect, useState } from "react";
import type { FormEventHandler } from "react";
import { sendChatMessage } from "./api";
import { faqItems } from "./content/faq.ts";
import { DownloadIcon } from "./icons/DownloadIcon";
import type { ChatMessage, Source } from "./types";
import "./App.css";

type ConversationMessage = ChatMessage & {
  sources?: Source[];
};

const suggestedQuestions = [
  "Has she taken AI solutions from prototype to production?",
  "What backend systems has she built for AI applications?",
  "What machine learning solutions has she built?",
];

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
  const [error, setError] = useState("");
  const [expandedSourceKey, setExpandedSourceKey] = useState<string | null>(null);
  const [selectedFaqIndex, setSelectedFaqIndex] = useState<number | null>(null);
  const [modalSource, setModalSource] = useState<Source | null>(null);

  const selectedFaqItem = selectedFaqIndex === null ? null : faqItems[selectedFaqIndex];

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

    setMessages(nextMessages);
    setInput("");
    setError("");
    setExpandedSourceKey(null);
    setModalSource(null);
    setIsLoading(true);

    try {
      const response = await sendChatMessage({
        message,
        history: nextMessages.map(({ role, content }) => ({ role, content })),
      });

      const assistantMessage: ConversationMessage = {
        role: "assistant",
        content: response.answer,
        sources: response.sources,
      };

      setMessages([...nextMessages, assistantMessage]);
    } catch {
      setError("Something went wrong while asking the CV assistant.");
      setMessages(messages);
    } finally {
      setIsLoading(false);
    }
  };

  const handleClearConversation = () => {
    setMessages([]);
    setInput("");
    setError("");
    setExpandedSourceKey(null);
    setModalSource(null);
  };

  const canClearConversation = messages.length > 0 || input.trim().length > 0 || Boolean(error);

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
              <h2>Ask about Brielle's CV</h2>
            </div>

            <button
              className="clear-conversation"
              disabled={!canClearConversation || isLoading}
              onClick={handleClearConversation}
              type="button"
            >
              Clear conversation
            </button>
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
                    className={`message message-${message.role}`}
                    key={`${message.role}-${index}`}
                  >
                    <div className="message-label">
                      {message.role === "user" ? "You" : "Assistant"}
                    </div>
                    <p>{message.content}</p>

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

          {error ? <p className="error-message">{error}</p> : null}

          <form className="composer" onSubmit={handleSubmit} autoComplete="off">
            <div className="input-wrap">
              <label className="sr-only" htmlFor="chat-message">
                Ask a question
              </label>
              <input
                id="chat-message"
                type="text"
                value={input}
                onChange={(event) => setInput(event.target.value)}
                placeholder="Ask about skills, projects, or experience"
                disabled={isLoading}
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