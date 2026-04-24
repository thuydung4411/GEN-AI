"use client";

import { startTransition, useEffect, useState } from "react";

import {
  getJob,
  listAssets,
  uploadAsset,
  deleteAsset,
  type AssetListItem,
  type JobSummary,
  type UploadAssetResponse,
} from "../../lib/api/client";
import { createSupabaseBrowserClient } from "../../lib/supabase/browser";

type DashboardShellProps = {
  userEmail: string;
};

export function DashboardShell({ userEmail }: DashboardShellProps) {
  const [assets, setAssets] = useState<AssetListItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [recentJob, setRecentJob] = useState<UploadAssetResponse | null>(null);

  async function refreshData() {
    setLoading(true);
    setError(null);
    try {
      const items = await listAssets();
      setAssets(items);
    } catch (fetchError) {
      setError(
        fetchError instanceof Error
          ? fetchError.message
          : "Unable to load data.",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refreshData();
  }, []);

  async function handleUpload(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    setError(null);
    setInfo(null);
    const formData = new FormData(form);
    const file = formData.get("file");
    if (!(file instanceof File) || file.size === 0) {
      setError("Choose a file before uploading.");
      return;
    }
    setUploading(true);
    try {
      const response = await uploadAsset(file);
      setRecentJob(response);
      setInfo(`Upload started: Job ${response.job_id} created.`);
      form.reset();
      await refreshData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setUploading(false);
    }
  }

  async function handleDelete(id: string) {
    if (!confirm("Are you sure you want to PERMANENTLY delete this asset?"))
      return;
    try {
      await deleteAsset(id);
      await refreshData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed.");
    }
  }

  async function refreshRecentJob() {
    if (!recentJob) return;
    try {
      const job = await getJob(recentJob.job_id);
      setRecentJob({ ...recentJob, status: job.status });
      setInfo(`Job ${job.id} is currently ${job.status}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Job refresh failed.");
    }
  }

  async function signOut() {
    const supabase = createSupabaseBrowserClient();
    await supabase.auth.signOut();
    window.location.href = "/login";
  }

  return (
    <main className="page-shell" style={{ display: "grid", gap: 24 }}>
      <header
        className="card"
        style={{
          padding: 28,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <div>
          <p
            style={{
              margin: 0,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              color: "#0f766e",
            }}
          >
            Hybrid Asset Ops
          </p>
          <h1 style={{ margin: "8px 0 6px", fontSize: "2.1rem" }}>
            ChatJVB Control Center
          </h1>
          <p className="muted" style={{ margin: 0 }}>
            Signed in as {userEmail}. Manage your datasets and knowledge base.
          </p>
        </div>
        <div style={{ display: "flex", gap: 12 }}>
          <a
            href="/dashboard/chat"
            className="button"
            style={{ background: "#065f46" }}
          >
            Open ChatJVB
          </a>
          <button className="button secondary" onClick={() => void signOut()}>
            Sign out
          </button>
        </div>
      </header>

      {error && <div className="error-banner">{error}</div>}
      {info && (
        <div style={{ borderRadius: 14, background: "#ecfdf3", padding: 14 }}>
          {info}
        </div>
      )}

      <section
        className="card"
        style={{ padding: 32, display: "grid", gap: 32 }}
      >
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-start",
          }}
        >
          <div>
            <h2 className="section-title">📦 Asset Management</h2>
            <p className="section-subtitle">
              Upload your datasets (.csv, .xlsx) or knowledge documents (.pdf,
              .docx, .md) to the unified platform.
            </p>
          </div>
          <form
            onSubmit={handleUpload}
            style={{ display: "flex", gap: 12, alignItems: "flex-end" }}
          >
            <div className="field" style={{ margin: 0 }}>
              <label style={{ fontSize: "0.8rem" }}>Upload new file</label>
              <input
                name="file"
                type="file"
                accept=".xlsx,.xls,.csv,.pdf,.docx,.txt,.md"
              />
            </div>
            <button
              className="button"
              disabled={uploading}
              style={{ height: 42 }}
            >
              {uploading ? "Processing..." : "Upload Asset"}
            </button>
          </form>
        </div>

        {recentJob && (
          <div
            style={{
              borderRadius: 18,
              padding: 16,
              background: "var(--surface-muted)",
              border: "1px solid var(--line)",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <div style={{ display: "flex", gap: 20, alignItems: "center" }}>
              <p className="muted" style={{ margin: 0 }}>
                Recent Job: <strong>{recentJob.job_id}</strong>
              </p>
              <span className={`status-chip ${recentJob.status}`}>
                {recentJob.status}
              </span>
            </div>
            <button
              className="button secondary small"
              onClick={() => void refreshRecentJob()}
            >
              Refresh Status
            </button>
          </div>
        )}

        <div style={{ display: "grid", gap: 16 }}>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <h3 style={{ fontSize: "1.1rem", margin: 0 }}>All Assets</h3>
            <span className="muted" style={{ fontSize: "0.85rem" }}>
              {assets.length} total
            </span>
          </div>

          <div style={{ display: "grid", gap: 12 }}>
            {loading ? (
              <p className="muted">Loading assets...</p>
            ) : assets.length === 0 ? (
              <div
                style={{
                  textAlign: "center",
                  padding: "40px 0",
                  color: "#64748b",
                }}
              >
                <p style={{ fontSize: "2rem", margin: "0 0 10px" }}>📥</p>
                <p>No assets uploaded yet. Start by uploading a file above.</p>
              </div>
            ) : (
              <div style={{ display: "grid", gap: 10 }}>
                {assets.map((a) => (
                  <div key={a.id} className="asset-mini-card">
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 16,
                        flex: 1,
                      }}
                    >
                      <span style={{ fontSize: "1.2rem" }}>
                        {a.kind === "dataset" ? "📊" : "🧠"}
                      </span>
                      <div style={{ display: "grid" }}>
                        <strong style={{ fontSize: "1rem" }}>{a.title}</strong>
                        <span
                          className="muted"
                          style={{
                            fontSize: "0.75rem",
                            textTransform: "uppercase",
                          }}
                        >
                          {a.kind} • Created{" "}
                          {new Date(a.created_at).toLocaleDateString()}
                        </span>
                      </div>
                      <span
                        className={`status-chip small ${a.status}`}
                        style={{ marginLeft: "auto" }}
                      >
                        {a.status}
                      </span>
                    </div>
                    <button
                      className="delete-button"
                      onClick={() => void handleDelete(a.id)}
                      style={{
                        background: "#fff1f2",
                        color: "#e11d48",
                        fontSize: "0.75rem",
                        fontWeight: 700,
                        padding: "6px 12px",
                        borderRadius: "8px",
                        marginLeft: 16,
                        border: "1px solid #fecdd3",
                      }}
                    >
                      DELETE
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </section>

      <style jsx>{`
        .asset-mini-card {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 12px;
          border-radius: 12px;
          border: 1px solid var(--line);
          background: var(--surface);
          font-size: 0.95rem;
        }
        .status-chip.small {
          padding: 2px 8px;
          font-size: 0.75rem;
        }
        .delete-button {
          background: transparent;
          border: none;
          cursor: pointer;
          font-size: 1.1rem;
          padding: 4px;
          border-radius: 6px;
          opacity: 0.5;
          transition: all 0.2s;
        }
        .delete-button:hover {
          opacity: 1;
          background: #fee2e2;
        }
      `}</style>
    </main>
  );
}
