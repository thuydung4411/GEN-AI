"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  createChatSession,
  getAuthToken,
  getChatSession,
  listChatSessions,
  type ChatMessage,
  type ChatSession,
} from "../../../lib/api/client";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

const MODELS = [
  { id: "llama3.2:1b", name: "Llama 3.2 (1B)" },
  { id: "gemma3:4b", name: "Gemma 3 (4B)" },
  { id: "gemini-1.5-flash-latest", name: "Gemini 1.5 Flash" },
];

export default function ChatView() {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [currentSession, setCurrentSession] = useState<ChatSession | null>(
    null,
  );
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [model, setModel] = useState(MODELS[0].id);
  const [loading, setLoading] = useState(false);
  const [streamingToken, setStreamingToken] = useState("");
  const [citations, setCitations] = useState<any[]>([]);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, streamingToken]);

  useEffect(() => {
    void loadSessions();
  }, []);

  async function loadSessions() {
    try {
      const data = await listChatSessions();
      setSessions(data);
    } catch (err) {
      console.error("Failed to load sessions", err);
    }
  }

  async function handleCreateSession() {
    const title = prompt("Tên phiên chat mới:");
    if (!title) return;
    try {
      const session = await createChatSession(title);
      setSessions([session, ...sessions]);
      void selectSession(session.id);
    } catch (err) {
      alert("Lỗi khi tạo phiên chat");
    }
  }

  async function selectSession(id: string) {
    try {
      const session = await getChatSession(id);
      setCurrentSession(session);
      setMessages(session.messages || []);
      setStreamingToken("");
      setCitations([]);
    } catch (err) {
      alert("Lỗi khi tải phiên chat");
    }
  }

  async function sendMessage(e: React.FormEvent) {
    e.preventDefault();
    if (!input.trim() || !currentSession || loading) return;

    const userMessage: ChatMessage = {
      id: Math.random().toString(),
      role: "user",
      content: input,
      status: "completed",
      metadata_json: null,
      created_at: new Date().toISOString(),
    };

    setMessages([...messages, userMessage]);
    setInput("");
    setLoading(true);
    setStreamingToken("");
    setCitations([]);

    try {
      const token = await getAuthToken();
      const response = await fetch(
        `${API_BASE_URL}/v1/chat/sessions/${currentSession.id}/messages`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            content: input,
            model_choice: model,
          }),
        },
      );

      if (!response.ok) throw new Error("Stream failed");

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let accumulatedText = "";

      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const chunk = decoder.decode(value);
          const lines = chunk.split("\n");

          for (const line of lines) {
            if (line.startsWith("data: ")) {
              try {
                const data = JSON.parse(line.slice(6));
                if (chunk.includes("event: token")) {
                  accumulatedText += data;
                  setStreamingToken(accumulatedText);
                } else if (chunk.includes("event: end")) {
                  setCitations(data.citations || []);
                } else if (chunk.includes("event: error")) {
                  alert("Lỗi: " + data);
                }
              } catch (e) {
                // Ignore partial JSON
              }
            }
          }
        }
      }

      void selectSession(currentSession.id);
    } catch (err) {
      alert("Lỗi khi gửi tin nhắn");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="chatjvb-layout">
      {/* Sidebar */}
      <div className="chatjvb-sidebar">
        <div className="chatjvb-sidebar-header">
          <button className="chatjvb-new-btn" onClick={handleCreateSession}>
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M12 5v14M5 12h14" />
            </svg>
            New Chat
          </button>
        </div>
        <div
          style={{
            flex: 1,
            overflowY: "auto",
            padding: "0 12px",
            display: "flex",
            flexDirection: "column",
            gap: "4px",
          }}
        >
          {sessions.map((s) => (
            <button
              key={s.id}
              onClick={() => void selectSession(s.id)}
              className={`chatjvb-session-btn ${currentSession?.id === s.id ? "active" : ""}`}
            >
              {s.title}
            </button>
          ))}
        </div>
        <div className="chatjvb-bottom-nav">
          <Link href="/dashboard" className="chatjvb-bottom-link">
            📊 Dataset Ops Dashboard
          </Link>
        </div>
      </div>

      {/* Main View */}
      <div className="chatjvb-main">
        {/* Top Header */}
        <div className="chatjvb-header">
          {currentSession && (
            <select
              className="chatjvb-model-select"
              value={model}
              onChange={(e) => setModel(e.target.value)}
            >
              {MODELS.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name}
                </option>
              ))}
            </select>
          )}
        </div>

        {currentSession ? (
          <>
            <div className="chatjvb-messages">
              {messages.map((m) => (
                <div key={m.id} className="chatjvb-msg-row">
                  <div
                    className="chatjvb-msg-content"
                    style={{
                      justifyContent:
                        m.role === "user" ? "flex-end" : "flex-start",
                    }}
                  >
                    {m.role === "user" ? (
                      <div className="chatjvb-user-msg">{m.content}</div>
                    ) : (
                      <div className="chatjvb-assistant-msg">
                        <div className="chatjvb-avatar ai">
                          <svg
                            width="18"
                            height="18"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="2"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          >
                            <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path>
                            <polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline>
                            <line x1="12" y1="22.08" x2="12" y2="12"></line>
                          </svg>
                        </div>
                        <div style={{ flex: 1 }}>
                          {m.content}
                          {m.metadata_json?.citations?.length > 0 && (
                            <div className="chatjvb-citations">
                              {m.metadata_json.citations.map(
                                (c: any, i: number) => (
                                  <div
                                    key={i}
                                    className="chatjvb-badge"
                                    title={c.quote}
                                  >
                                    📄 {c.original_filename}{" "}
                                    {c.source_page
                                      ? `(p.${c.source_page})`
                                      : ""}
                                  </div>
                                ),
                              )}
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ))}

              {streamingToken && (
                <div className="chatjvb-msg-row">
                  <div className="chatjvb-msg-content">
                    <div className="chatjvb-assistant-msg">
                      <div className="chatjvb-avatar ai">
                        <svg
                          width="18"
                          height="18"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="2"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        >
                          <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path>
                          <polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline>
                          <line x1="12" y1="22.08" x2="12" y2="12"></line>
                        </svg>
                      </div>
                      <div style={{ flex: 1 }}>
                        {streamingToken}
                        {citations.length > 0 && (
                          <div className="chatjvb-citations">
                            {citations.map((c: any, i: number) => (
                              <div
                                key={i}
                                className="chatjvb-badge"
                                title={c.quote}
                              >
                                📄 {c.original_filename}{" "}
                                {c.source_page ? `(p.${c.source_page})` : ""}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              )}
              {loading && !streamingToken && (
                <div className="chatjvb-msg-row">
                  <div className="chatjvb-msg-content">
                    <div
                      className="chatjvb-assistant-msg"
                      style={{ opacity: 0.5 }}
                    >
                      <div className="chatjvb-avatar ai">
                        <svg
                          width="18"
                          height="18"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="2"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        >
                          <circle cx="12" cy="12" r="10"></circle>
                          <line x1="12" y1="8" x2="12" y2="12"></line>
                          <line x1="12" y1="16" x2="12.01" y2="16"></line>
                        </svg>
                      </div>
                      <div>...</div>
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            <div className="chatjvb-input-wrapper">
              <form className="chatjvb-input-box" onSubmit={sendMessage}>
                <svg
                  width="20"
                  height="20"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="#999"
                  strokeWidth="2"
                  style={{ marginLeft: 4 }}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"></path>
                </svg>
                <input
                  type="text"
                  placeholder="Message ChatJVB..."
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                />
                <button
                  className="chatjvb-submit-btn"
                  type="submit"
                  disabled={loading || !input.trim()}
                  style={{ background: input.trim() ? "black" : "#e5e5e5" }}
                >
                  <svg
                    width="14"
                    height="14"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke={input.trim() ? "white" : "#a3a3a3"}
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <line x1="12" y1="19" x2="12" y2="5"></line>
                    <polyline points="5 12 12 5 19 12"></polyline>
                  </svg>
                </button>
              </form>
            </div>
          </>
        ) : (
          <div className="chatjvb-empty">ChatJVB</div>
        )}
      </div>
    </div>
  );
}
