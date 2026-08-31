import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import "./style.css";

const API = "http://localhost:8000/api";

function formatAnswer(text) {
  if (!text) return null;

  const parts = text.split(/(\[Source\s+\d+\])/g);

  return parts.map((part, index) => {
    if (/^\[Source\s+\d+\]$/.test(part)) {
      return (
        <span className="citation" key={index}>
          {part}
        </span>
      );
    }

    return <React.Fragment key={index}>{part}</React.Fragment>;
  });
}

function App() {
  const [docs, setDocs] = useState([]);
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState(null);
  const [busy, setBusy] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [selected, setSelected] = useState([]);
  const [error, setError] = useState("");
  const [ollama, setOllama] = useState(null);

  const readyDocs = useMemo(
    () => docs.filter((d) => d.status === "ready"),
    [docs]
  );

  const load = async () => {
    try {
      const r = await fetch(`${API}/documents`);

      if (!r.ok) {
        throw new Error("Backend is not reachable");
      }

      setDocs(await r.json());
    } catch (e) {
      setError(e.message);
    }
  };

  const check = async () => {
    try {
      const r = await fetch(`${API}/health/ollama`);
      setOllama(await r.json());
    } catch {
      setOllama({
        ok: false,
        error: "Backend is not reachable",
      });
    }
  };

  useEffect(() => {
    load();
    check();

    const timer = setInterval(() => {
      load();
      check();
    }, 5000);

    return () => clearInterval(timer);
  }, []);

  const upload = async (e) => {
    const file = e.target.files?.[0];

    if (!file) return;

    setUploading(true);
    setError("");

    const formData = new FormData();
    formData.append("file", file);

    try {
      const r = await fetch(`${API}/documents/upload`, {
        method: "POST",
        body: formData,
      });

      const data = await r.json();

      if (!r.ok) {
        throw new Error(data.detail || "Upload failed");
      }

      await load();
      await check();
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  };

  const ask = async () => {
    if (!question.trim() || busy) return;

    setBusy(true);
    setError("");
    setAnswer(null);

    try {
      const r = await fetch(`${API}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          question,
          document_ids: selected.length ? selected : null,
        }),
      });

      const data = await r.json();

      if (!r.ok) {
        throw new Error(data.detail || "Chat failed");
      }

      setAnswer(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id) => {
    try {
      const r = await fetch(`${API}/documents/${id}`, {
        method: "DELETE",
      });

      if (!r.ok) {
        throw new Error("Delete failed");
      }

      setSelected((current) =>
        current.filter((item) => item !== id)
      );

      await load();
    } catch (e) {
      setError(e.message);
    }
  };

  const toggle = (id) => {
    setSelected((current) =>
      current.includes(id)
        ? current.filter((item) => item !== id)
        : [...current, id]
    );
  };

  const useExample = (text) => {
    setQuestion(text);
  };

  return (
    <div className="app">

      {/* HEADER */}
      <header className="hero">
        <div className="hero-copy">
          <div className="eyebrow">
            AI DOCUMENT INTELLIGENCE
          </div>

          <h1>
            Ask your
            <span> documents.</span>
          </h1>

          <p>
            Upload your documents, find the information that matters,
            and get grounded answers with source citations.
          </p>
        </div>

        <label className="upload-button">
          {uploading ? "Processing..." : "+ Upload document"}

          <input
            type="file"
            accept=".pdf,.docx,.txt"
            onChange={upload}
            disabled={uploading}
          />
        </label>
      </header>

      {/* SYSTEM STATUS */}
      <div className="statusbar">

        <div className="status-item">
          <span className={`status-dot ${ollama?.ok ? "online" : ""}`} />
          <span>
            Ollama{" "}
            <strong>
              {ollama?.ok ? "Connected" : "Offline"}
            </strong>
          </span>
        </div>

        <div className="status-divider" />

        <div className="status-item">
          <span className="status-label">Embeddings</span>
          <strong>
            {ollama?.embedding_model_present
              ? "Ready"
              : "Missing"}
          </strong>
        </div>

        <div className="status-divider" />

        <div className="status-item">
          <span className="status-label">LLM</span>
          <strong>
            {ollama?.llm_model_present
              ? "Ready"
              : "Missing"}
          </strong>
        </div>

        <div className="status-divider" />

        <div className="status-item">
          <span className="status-label">Documents</span>
          <strong>{readyDocs.length}</strong>
        </div>

      </div>

      {error && (
        <div className="error">
          <strong>Something went wrong:</strong> {error}
        </div>
      )}

      {/* MAIN */}
      <main>

        {/* KNOWLEDGE BASE */}
        <aside className="sidebar">

          <div className="sidebar-header">

            <div>
              <div className="section-kicker">
                YOUR KNOWLEDGE
              </div>

              <h2>Knowledge base</h2>

              <p>
                Select documents to use as context.
              </p>
            </div>

            <div className="document-count">
              {readyDocs.length}
            </div>

          </div>

          {docs.length === 0 ? (
            <div className="empty-documents">
              <div className="empty-icon">↑</div>

              <strong>No documents yet</strong>

              <p>
                Upload a PDF, DOCX, or TXT file to
                start asking questions.
              </p>
            </div>
          ) : (
            <div className="documents-list">

              {docs.map((doc) => (
                <div className="document-card" key={doc.id}>

                  <input
                    type="checkbox"
                    disabled={doc.status !== "ready"}
                    checked={selected.includes(doc.id)}
                    onChange={() => toggle(doc.id)}
                  />

                  <div className="document-info">

                    <strong
                      title={doc.filename}
                      className="document-name"
                    >
                      {doc.filename}
                    </strong>

                    <div className="document-meta">

                      <span
                        className={`badge ${doc.status}`}
                      >
                        {doc.status}
                      </span>

                      <span>
                        {doc.chunks} chunks
                      </span>

                    </div>

                    {doc.error && (
                      <small>{doc.error}</small>
                    )}

                  </div>

                  <button
                    className="delete-button"
                    onClick={() => remove(doc.id)}
                    title="Delete document"
                  >
                    ×
                  </button>

                </div>
              ))}

            </div>
          )}

        </aside>

        {/* CHAT */}
        <section className="workspace">

          <div className="workspace-header">
            <div>
              <div className="section-kicker">
                DOCUMENT Q&A
              </div>

              <h2>Ask a question</h2>

              <p>
                Answers are generated from the selected documents.
              </p>
            </div>
          </div>

          {/* QUESTION BOX */}
          <div className="question-box">

            <textarea
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Ask something about your documents..."
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  ask();
                }
              }}
            />

            <div className="question-footer">

              <span>
                {selected.length > 0
                  ? `${selected.length} document${
                      selected.length > 1 ? "s" : ""
                    } selected`
                  : "All ready documents"}
              </span>

              <button
                className="ask-button"
                onClick={ask}
                disabled={
                  busy || readyDocs.length === 0
                }
              >
                {busy ? "Thinking..." : "Ask →"}
              </button>

            </div>

          </div>

          {/* ANSWER */}
          {answer && (
            <div className="result">

              <div className="answer-header">

                <div>
                  <div className="section-kicker">
                    AI RESPONSE
                  </div>

                  <h2>Answer</h2>
                </div>

                <button
                  className="clear-button"
                  onClick={() => setAnswer(null)}
                >
                  Clear
                </button>

              </div>

              <div className="answer-card">
                {formatAnswer(answer.answer)}
              </div>

              <div className="sources-header">

                <div>
                  <h3>Sources used</h3>

                  <p>
                    Retrieved passages used to ground the answer.
                  </p>
                </div>

                <span className="source-count">
                  {answer.sources.length}
                </span>

              </div>

              <div className="sources">

                {answer.sources.map((source, index) => (
                  <div
                    className="source-card"
                    key={source.chunk_id}
                  >

                    <div className="source-top">

                      <div className="source-title">

                        <span className="source-number">
                          {index + 1}
                        </span>

                        <div>
                          <strong>
                            {source.filename}
                          </strong>

                          <span>
                            {source.page
                              ? `Page ${source.page}`
                              : "Document source"}
                          </span>
                        </div>

                      </div>

                      <div className="similarity">
                        {source.score.toFixed(3)}
                        <small>match</small>
                      </div>

                    </div>

                    <p>
                      {source.excerpt}
                      {source.excerpt.length >= 400
                        ? "..."
                        : ""}
                    </p>

                  </div>
                ))}

              </div>

            </div>
          )}

          {/* EMPTY STATE */}
          {!answer && !busy && (
            <div className="empty-workspace">

              <div className="empty-workspace-icon">
                ✦
              </div>

              <h3>
                Your documents are ready to answer questions.
              </h3>

              <p>
                Ask something about the information contained
                in your uploaded documents.
              </p>

              <div className="example-questions">

                <button
                  onClick={() =>
                    useExample(
                      "Give me a brief introduction about this document."
                    )
                  }
                >
                  Briefly summarize this document
                </button>

                <button
                  onClick={() =>
                    useExample(
                      "What are the main requirements mentioned in the document?"
                    )
                  }
                >
                  What are the main requirements?
                </button>

                <button
                  onClick={() =>
                    useExample(
                      "What are the different user roles?"
                    )
                  }
                >
                  What are the different user roles?
                </button>

              </div>

            </div>
          )}

          {/* LOADING */}
          {busy && (
            <div className="loading">

              <div className="loading-dots">
                <span />
                <span />
                <span />
              </div>

              <div>
                <strong>Searching your documents...</strong>
                <p>
                  Retrieving relevant passages and generating an answer.
                </p>
              </div>

            </div>
          )}

        </section>

      </main>

    </div>
  );
}

createRoot(document.getElementById("root")).render(
  <App />
);