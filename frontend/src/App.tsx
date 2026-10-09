
import { useEffect, useState } from "react";
import "./App.css";

const API = "http://127.0.0.1:8000";

type Finding = {
  finding_id?: string;
  category?: string;
  type?: string;
  severity?: string;
  page?: number;
  message?: string;
  confidence?: number;
  evidence?: {
    x?: number;
    y?: number;
    width?: number;
    height?: number;
    details?: Record<string, unknown>;
  };
};

type AnalysisResult = {
  findings?: Finding[];
  risk_score?: number;
  score?: number;
  risk_level?: string;
  summary?: string;
  document_id?: string;
  heatmap_base64?: string;
  [key: string]: unknown;
};

function App() {
  const [backendStatus, setBackendStatus] = useState("Checking...");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [risk, setRisk] = useState<AnalysisResult | null>(null);
  const [previewUrl, setPreviewUrl] = useState("");

  useEffect(() => {
    fetch(`${API}/api/health`)
      .then((response) => {
        if (!response.ok) throw new Error("Backend unavailable");
        return response.json();
      })
      .then((data) => setBackendStatus(data.status ?? "Connected"))
      .catch(() => setBackendStatus("Disconnected"));
  }, []);

  useEffect(() => {
    if (!file) {
      setPreviewUrl("");
      return;
    }

    const url = URL.createObjectURL(file);
    setPreviewUrl(url);

    return () => URL.revokeObjectURL(url);
  }, [file]);

  function chooseFile(selected: File | null) {
    setFile(selected);
    setResult(null);
    setRisk(null);
    setMessage("");
  }

  async function analyseDocument() {
    if (!file) {
      setMessage("Please choose a PDF or image first.");
      return;
    }

    const isPdf =
      file.type === "application/pdf" ||
      file.name.toLowerCase().endsWith(".pdf");

    const isImage = [
      "image/png",
      "image/jpeg",
      "image/webp",
      "image/tiff",
    ].includes(file.type);

    if (!isPdf && !isImage) {
      setMessage("Please select a PDF, PNG, JPEG, WebP, or TIFF file.");
      return;
    }

    setLoading(true);
    setResult(null);
    setRisk(null);
    setMessage("Uploading file and analysing…");

    try {
      const body = new FormData();
      body.append("file", file);

      const endpoint = isPdf
        ? `${API}/api/pdf-analysis`
        : `${API}/api/visual-analysis`;

      const response = await fetch(endpoint, {
        method: "POST",
        body,
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          typeof data.detail === "string"
            ? data.detail
            : "The server could not analyse this file."
        );
      }

      setResult(data);

      const findings: Finding[] = Array.isArray(data.findings)
        ? data.findings
        : [];

      if (findings.length > 0) {
        try {
          const riskResponse = await fetch(`${API}/api/risk-score`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ findings }),
          });

          if (riskResponse.ok) {
            setRisk(await riskResponse.json());
          }
        } catch {
          // The analysis is still available even if risk scoring fails.
        }
      }

      setMessage(
        findings.length > 0
          ? `Analysis complete. ${findings.length} finding(s) returned.`
          : "Analysis complete. No findings were returned by this analysis."
      );
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "Analysis failed. Check the backend server."
      );
    } finally {
      setLoading(false);
    }
  }

  const findings = Array.isArray(result?.findings)
    ? result.findings
    : [];

  const riskScore =
    risk?.risk_score ?? risk?.score ?? result?.risk_score ?? result?.score;

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon">D</div>
          <div>
            <h2>DocShield AI</h2>
            <p>Document Intelligence</p>
          </div>
        </div>

        <p className="nav-label">WORKSPACE</p>

        <button
          className="nav-item active"
          type="button"
          onClick={() => document.getElementById("overview")?.scrollIntoView()}
        >
          ◈ Overview
        </button>

        <button
          className="nav-item"
          type="button"
          onClick={() => document.getElementById("upload")?.scrollIntoView()}
        >
          ＋ Analyse Document
        </button>

        <button
          className="nav-item"
          type="button"
          onClick={() => window.open(`${API}/api/history`, "_blank")}
        >
          ▤ Analysis History
        </button>

        <button
          className="nav-item"
          type="button"
          onClick={() => window.open(`${API}/docs`, "_blank")}
        >
          ⌘ API Documentation
        </button>

        <div className="sidebar-bottom">
          <div className="status-dot" />
          <span>Forensic Workspace</span>
        </div>
      </aside>

      <main className="main" id="overview">
        <header className="topbar">
          <div>
            <p className="eyebrow">DOCUMENT SECURITY PLATFORM</p>
            <h1>Overview</h1>
          </div>

          <div className="backend-pill">
            <span
              className={
                backendStatus === "Disconnected" ? "dot red" : "dot"
              }
            />
            Backend: {backendStatus}
          </div>
        </header>

        <section className="welcome">
          <div className="welcome-content">
            <p className="eyebrow light">AI-POWERED DOCUMENT FORENSICS</p>
            <h2>
              Trust documents.
              <br />
              Verify the evidence.
            </h2>
            <p>
              Examine PDF structure and visual patterns, review suspicious
              findings, and assess document risk in one workspace.
            </p>

            <button
              className="primary-button"
              type="button"
              onClick={() =>
                document.getElementById("upload")?.scrollIntoView({
                  behavior: "smooth",
                })
              }
            >
              Analyse a document <span>→</span>
            </button>
          </div>

          <div className="shield-art" aria-hidden="true">
            <div className="shield-ring">
              <span>✓</span>
            </div>
            <div className="orbit orbit-one" />
            <div className="orbit orbit-two" />
          </div>
        </section>

        <div className="section-heading">
          <div>
            <h2>Workspace summary</h2>
            <p>Your current analysis workspace.</p>
          </div>
        </div>

        <section className="stats-grid">
          <article className="stat-card">
            <span className="stat-icon blue">▤</span>
            <p>Selected document</p>
            <h3>{file ? "1" : "0"}</h3>
            <span className="stat-note">
              {file ? file.name : "No document selected"}
            </span>
          </article>

          <article className="stat-card">
            <span className="stat-icon purple">◎</span>
            <p>Risk score</p>
            <h3>
              {typeof riskScore === "number" ? `${riskScore}/100` : "—"}
            </h3>
            <span className="stat-note">
              {risk?.risk_level
                ? String(risk.risk_level)
                : "Available after analysis"}
            </span>
          </article>

          <article className="stat-card">
            <span className="stat-icon green">✓</span>
            <p>Findings</p>
            <h3>{result ? findings.length : "—"}</h3>
            <span className="stat-note">Returned by the analysis endpoint</span>
          </article>
        </section>

        <section className="panel upload-panel" id="upload">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">START AN ANALYSIS</p>
              <h2>Upload your document</h2>
              <p>Choose a PDF or supported image to begin forensic checks.</p>
            </div>
          </div>

          <label className="upload-zone">
            <span className="upload-symbol">↑</span>
            <strong>{file ? file.name : "Choose a document"}</strong>
            <span>
              {file
                ? `${(file.size / 1024 / 1024).toFixed(2)} MB · Click to change`
                : "PDF, PNG, JPEG, WebP or TIFF"}
            </span>
            <input
              type="file"
              accept=".pdf,.png,.jpg,.jpeg,.webp,.tif,.tiff,application/pdf,image/png,image/jpeg,image/webp,image/tiff"
              onChange={(event) =>
                chooseFile(event.target.files?.[0] ?? null)
              }
            />
          </label>

          {file && (
            <div className="selected-file">
              <span className="action-symbol">▤</span>
              <div>
                <strong>{file.name}</strong>
                <small>
                  {file.type || "Document"} ·{" "}
                  {(file.size / 1024 / 1024).toFixed(2)} MB
                </small>
              </div>
              <button
                className="remove-file"
                type="button"
                onClick={() => chooseFile(null)}
              >
                Remove
              </button>
            </div>
          )}

          <button
            className="primary-button analyse-button"
            type="button"
            onClick={analyseDocument}
            disabled={loading || !file}
          >
            {loading ? "Analysing…" : "Run forensic analysis"} <span>→</span>
          </button>

          {message && (
            <div className="message" role="status">
              {message}
            </div>
          )}
        </section>

        {result && (
          <section className="panel results-panel">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">ANALYSIS OUTPUT</p>
                <h2>Findings and evidence</h2>
                <p>
                  Results are indicators for review, not proof of fraud.
                </p>
              </div>
            </div>

            {typeof riskScore === "number" && (
              <div className="risk-banner">
                <div>
                  <span className="risk-label">Calculated risk score</span>
                  <strong>{riskScore} / 100</strong>
                </div>
                <span className="risk-level">
                  {String(risk?.risk_level ?? "Scored")}
                </span>
              </div>
            )}

            {previewUrl && file?.type.startsWith("image/") && (
              <div className="preview-container">
                <h3>Image preview</h3>
                <img
                  className="document-preview"
                  src={previewUrl}
                  alt="Selected document preview"
                />
              </div>
            )}

            {result.heatmap_base64 && (
              <div className="preview-container">
                <h3>Visual analysis heatmap</h3>
                <img
                  className="document-preview"
                  src={`data:image/png;base64,${result.heatmap_base64}`}
                  alt="Visual anomaly heatmap generated by the analysis"
                />
              </div>
            )}

            {findings.length === 0 ? (
              <p className="empty-findings">
                No findings were returned. This does not guarantee that the
                document is authentic.
              </p>
            ) : (
              <div className="findings-list">
                {findings.map((finding, index) => (
                  <article
                    className="finding-card"
                    key={finding.finding_id ?? `${finding.type}-${index}`}
                  >
                    <div className="finding-topline">
                      <span className="finding-category">
                        {finding.category ?? "General"}
                      </span>
                      <span
                        className={`severity severity-${(
                          finding.severity ?? "unknown"
                        ).toLowerCase()}`}
                      >
                        {finding.severity ?? "Unspecified"}
                      </span>
                    </div>

                    <h3>{finding.type ?? "Analysis finding"}</h3>
                    <p>{finding.message ?? "No additional description."}</p>

                    <div className="finding-meta">
                      {finding.page != null && (
                        <span>Page {finding.page}</span>
                      )}
                      {finding.confidence != null && (
                        <span>
                          Confidence:{" "}
                          {(finding.confidence * 100).toFixed(0)}%
                        </span>
                      )}
                      {finding.evidence?.x != null && (
                        <span>
                          Position: ({finding.evidence.x},{" "}
                          {finding.evidence.y ?? 0})
                        </span>
                      )}
                    </div>
                  </article>
                ))}
              </div>
            )}

            <details className="raw-details">
              <summary>View complete technical response</summary>
              <pre>{JSON.stringify(result, null, 2)}</pre>
            </details>

            <p className="disclaimer">
              AI-assisted forensic analysis does not establish that a document
              is fraudulent. Official verification with the issuing
              organization should be performed when authenticity is critical.
            </p>
          </section>
        )}

        <footer>
          <span>DocShield AI · Development workspace</span>
          <span>AI-assisted results require human verification.</span>
        </footer>
      </main>
    </div>
  );
}

export default App;