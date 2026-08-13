import { useState } from "react";
import type { FormEventHandler } from "react";
import { sendChatMessage } from "./api";
import type { ChatMessage, Source } from "./types";
import "./App.css";

type ConversationMessage = ChatMessage & {
  sources?: Source[];
};

const suggestedQuestions = [
  "What backend projects have I built?",
  "Which technical skills are strongest?",
  "Tell me about deployment experience",
];

function App() {
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

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

  return (
    <main className="app-shell">
      <section className="workspace" aria-label="CV chat workspace">
        <aside className="profile-rail">
          <div className="brand-lockup">
            <span className="brand-mark">CV</span>
            <div>
              <p className="eyebrow">Personal RAG</p>
              <h1>CV Intelligence</h1>
            </div>
          </div>

          <p className="rail-copy">
            Ask focused questions about experience, skills, projects, and impact
            using the curated CV knowledge base.
          </p>

          <div className="rail-metrics" aria-label="Assistant qualities">
            <div>
              <span>Mode</span>
              <strong>Conversational</strong>
            </div>
            <div>
              <span>Source</span>
              <strong>Knowledge-backed</strong>
            </div>
          </div>
        </aside>

        <section className="chat-panel" aria-label="CV chat">
          <header className="chat-header">
            <div>
              <p className="eyebrow">Ask the profile</p>
              <h2>What would you like to know?</h2>
            </div>
            <div className="status-pill">Online</div>
          </header>

          <div className="message-list" aria-live="polite">
            {messages.length === 0 ? (
              <div className="empty-state">
                <span>Start with a prompt</span>
                <p>Choose a question or ask anything specific about the CV.</p>
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
              messages.map((message, index) => (
                <article
                  className={`message message-${message.role}`}
                  key={`${message.role}-${index}`}
                >
                  <div className="message-label">
                    {message.role === "user" ? "You" : "Assistant"}
                  </div>
                  <p>{message.content}</p>

                  {message.sources && message.sources.length > 0 ? (
                    <div className="sources" aria-label="Sources">
                      {message.sources.map((source) => (
                        <span className="source" key={source.id}>
                          {source.title}
                        </span>
                      ))}
                    </div>
                  ) : null}
                </article>
              ))
            )}

            {isLoading ? (
              <article className="message message-assistant">
                <div className="message-label">Assistant</div>
                <p>Thinking...</p>
              </article>
            ) : null}
          </div>

          {error ? <p className="error-message">{error}</p> : null}

          <form className="composer" onSubmit={handleSubmit}>
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
    </main>
  );
}

export default App;