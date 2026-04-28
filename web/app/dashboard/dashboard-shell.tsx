"use client";

import { type FormEvent, useEffect, useState } from "react";

import {
  deleteAsset,
  getAssetPreview,
  getAssetProfile,
  getJob,
  listAssets,
  uploadAsset,
  type AssetListItem,
  type AssetPreviewResponse,
  type AssetProfileResponse,
  type UploadAssetResponse,
} from "../../lib/api/client";
import { createSupabaseBrowserClient } from "../../lib/supabase/browser";

type DashboardShellProps = {
  userEmail: string;
};

type InspectionMode = "preview" | "profile";

type InspectionState = {
  asset: AssetListItem;
  mode: InspectionMode;
  payload: AssetPreviewResponse | AssetProfileResponse;
};

const ACCEPTED_ASSET_EXTENSIONS = ".csv,.xlsx,.xls,.pdf,.docx,.txt,.md";

export function DashboardShell({ userEmail }: DashboardShellProps) {
  const [assets, setAssets] = useState<AssetListItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [inspectionLoading, setInspectionLoading] = useState<string | null>(
    null,
  );
  const [recentJob, setRecentJob] = useState<UploadAssetResponse | null>(null);
  const [inspection, setInspection] = useState<InspectionState | null>(null);

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
          : "Unable to load assets.",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refreshData();
  }, []);

  async function handleUpload(event: FormEvent<HTMLFormElement>) {
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
      setInfo(
        `Queued ${response.kind} asset. Job ${response.job_id} is ${response.status}.`,
      );
      form.reset();
      await refreshData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setUploading(false);
    }
  }

  async function handleDelete(asset: AssetListItem) {
    if (!confirm(`Delete "${asset.title}" permanently?`)) {
      return;
    }

    try {
      await deleteAsset(asset.id);
      if (inspection?.asset.id === asset.id) {
        setInspection(null);
      }
      setInfo(`Deleted asset "${asset.title}".`);
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
      await refreshData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Job refresh failed.");
    }
  }

  async function inspectAsset(asset: AssetListItem, mode: InspectionMode) {
    setError(null);
    setInfo(null);
    setInspectionLoading(`${asset.id}:${mode}`);
    try {
      const payload =
        mode === "profile"
          ? await getAssetProfile(asset.id)
          : await getAssetPreview(asset.id);
      setInspection({ asset, mode, payload });
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to inspect this asset yet.",
      );
    } finally {
      setInspectionLoading(null);
    }
  }

  async function signOut() {
    const supabase = createSupabaseBrowserClient();
    await supabase.auth.signOut();
    window.location.href = "/login";
  }

  const datasetCount = assets.filter((asset) => asset.kind === "dataset").length;
  const knowledgeCount = assets.filter(
    (asset) => asset.kind === "knowledge",
  ).length;
  const activeJobCount = assets.filter((asset) =>
    ["pending", "processing"].includes(asset.status),
  ).length;

  return (
    <main className="page-shell dashboard-page">
      <header className="card dashboard-hero">
        <div>
          <p className="eyebrow">Hybrid Asset Ops</p>
          <h1>ChatJVB Control Center</h1>
          <p className="muted">
            Signed in as {userEmail}. Upload one asset, let the backend choose
            the lane.
          </p>
        </div>
        <div className="hero-actions">
          <a href="/dashboard/chat" className="button">
            Open ChatJVB
          </a>
          <button className="button secondary" onClick={() => void signOut()}>
            Sign out
          </button>
        </div>
      </header>

      {error && <div className="error-banner">{error}</div>}
      {info && <div className="success-banner">{info}</div>}

      <section className="asset-grid">
        <div className="card asset-upload-card">
          <div>
            <p className="eyebrow">Unified Upload</p>
            <h2 className="section-title">Asset Management</h2>
            <p className="section-subtitle">
              Dataset files go to the structured lane. Knowledge files go to
              the RAG lane.
            </p>
          </div>

          <form onSubmit={handleUpload} className="upload-form">
            <div className="field">
              <label>Asset file</label>
              <input
                name="file"
                type="file"
                accept={ACCEPTED_ASSET_EXTENSIONS}
              />
            </div>
            <button className="button" disabled={uploading}>
              {uploading ? "Uploading..." : "Upload Asset"}
            </button>
          </form>

          <div className="asset-kind-guide">
            <div>
              <strong>Dataset lane</strong>
              <span>.csv, .xlsx, .xls for preview/profile and SQL tools.</span>
            </div>
            <div>
              <strong>Knowledge lane</strong>
              <span>.pdf, .docx, .txt, .md for chunking and RAG.</span>
            </div>
          </div>
        </div>

        <div className="card dashboard-stats">
          <MetricCard label="Total assets" value={assets.length} />
          <MetricCard label="Datasets" value={datasetCount} />
          <MetricCard label="Knowledge" value={knowledgeCount} />
          <MetricCard label="Active jobs" value={activeJobCount} />
        </div>
      </section>

      {recentJob && (
        <section className="card recent-job">
          <div>
            <p className="muted">Recent Job</p>
            <strong>{recentJob.job_id}</strong>
          </div>
          <span className={`status-chip ${recentJob.status}`}>
            {recentJob.status}
          </span>
          <button
            className="button secondary small"
            onClick={() => void refreshRecentJob()}
          >
            Refresh Status
          </button>
        </section>
      )}

      <section className="card asset-list-card">
        <div className="section-heading">
          <div>
            <h2 className="section-title">All Assets</h2>
            <p className="section-subtitle">
              One inventory, lane-specific actions kept explicit for debugging.
            </p>
          </div>
          <button className="button secondary small" onClick={() => void refreshData()}>
            Refresh
          </button>
        </div>

        {loading ? (
          <p className="muted">Loading assets...</p>
        ) : assets.length === 0 ? (
          <div className="empty-state">
            <strong>No assets uploaded yet.</strong>
            <span>Upload a CSV, Excel, PDF, DOCX, TXT, or MD file above.</span>
          </div>
        ) : (
          <div className="asset-table">
            {assets.map((asset) => (
              <AssetRow
                key={asset.id}
                asset={asset}
                inspectionLoading={inspectionLoading}
                onDelete={handleDelete}
                onInspect={inspectAsset}
              />
            ))}
          </div>
        )}
      </section>

      {inspection && (
        <section className="card inspection-panel">
          <div className="section-heading">
            <div>
              <p className="eyebrow">{inspection.mode}</p>
              <h2 className="section-title">{inspection.asset.title}</h2>
              <p className="section-subtitle">
                {inspection.asset.kind} asset inspection via /v1/assets.
              </p>
            </div>
            <button
              className="button secondary small"
              onClick={() => setInspection(null)}
            >
              Close
            </button>
          </div>
          <InspectionPayload inspection={inspection} />
        </section>
      )}

      <style jsx global>{`
        .dashboard-page {
          display: grid;
          gap: 24px;
        }

        .dashboard-hero,
        .section-heading,
        .recent-job {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 18px;
        }

        .dashboard-hero {
          padding: 28px;
        }

        .dashboard-hero h1 {
          margin: 8px 0 6px;
          font-size: clamp(1.8rem, 4vw, 2.35rem);
        }

        .eyebrow {
          margin: 0;
          color: var(--accent);
          font-size: 0.78rem;
          font-weight: 800;
          letter-spacing: 0.12em;
          text-transform: uppercase;
        }

        .hero-actions {
          display: flex;
          gap: 12px;
          flex-wrap: wrap;
          justify-content: flex-end;
        }

        .success-banner {
          border-radius: 14px;
          border: 1px solid #bbf7d0;
          background: #ecfdf3;
          color: #166534;
          padding: 12px 14px;
        }

        .asset-grid {
          display: grid;
          grid-template-columns: minmax(0, 1.6fr) minmax(280px, 0.8fr);
          gap: 24px;
        }

        .asset-upload-card,
        .asset-list-card,
        .inspection-panel {
          padding: 28px;
          display: grid;
          gap: 24px;
        }

        .upload-form {
          display: grid;
          grid-template-columns: minmax(220px, 1fr) auto;
          align-items: end;
          gap: 14px;
        }

        .asset-kind-guide {
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 12px;
        }

        .asset-kind-guide div,
        .metric-card,
        .empty-state {
          border: 1px solid var(--line);
          border-radius: 16px;
          background: var(--surface-muted);
          padding: 14px;
        }

        .asset-kind-guide strong,
        .asset-kind-guide span {
          display: block;
        }

        .asset-kind-guide span {
          margin-top: 4px;
          color: var(--text-muted);
          font-size: 0.86rem;
          line-height: 1.45;
        }

        .dashboard-stats {
          padding: 18px;
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 12px;
        }

        .metric-card {
          background: #f8fafc;
        }

        .metric-card span,
        .empty-state span {
          display: block;
          color: var(--text-muted);
          font-size: 0.86rem;
        }

        .metric-card strong {
          display: block;
          margin-top: 6px;
          font-size: 1.8rem;
        }

        .recent-job {
          padding: 18px 22px;
        }

        .recent-job p {
          margin: 0 0 4px;
        }

        .asset-table {
          display: grid;
          gap: 10px;
        }

        .asset-row {
          display: grid;
          grid-template-columns: minmax(0, 1fr) auto;
          gap: 16px;
          align-items: center;
          padding: 14px;
          border: 1px solid var(--line);
          border-radius: 16px;
          background: var(--surface);
        }

        .asset-main {
          min-width: 0;
          display: grid;
          gap: 8px;
        }

        .asset-title-line,
        .asset-meta,
        .asset-actions {
          display: flex;
          align-items: center;
          flex-wrap: wrap;
          gap: 8px;
        }

        .asset-title-line strong {
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .kind-chip {
          display: inline-flex;
          align-items: center;
          border-radius: 999px;
          background: #e0f2fe;
          color: #075985;
          padding: 4px 9px;
          font-size: 0.72rem;
          font-weight: 800;
          text-transform: uppercase;
        }

        .kind-chip.knowledge {
          background: #ecfdf3;
          color: #166534;
        }

        .asset-actions {
          justify-content: flex-end;
        }

        .button.small {
          padding: 8px 12px;
          font-size: 0.82rem;
        }

        .danger-button {
          border: 1px solid #fecdd3;
          border-radius: 999px;
          background: #fff1f2;
          color: #be123c;
          cursor: pointer;
          font-size: 0.82rem;
          font-weight: 800;
          padding: 8px 12px;
        }

        .danger-button:hover {
          background: #ffe4e6;
        }

        .empty-state {
          display: grid;
          gap: 4px;
          padding: 28px;
          text-align: center;
        }

        .inspection-list {
          display: grid;
          gap: 10px;
        }

        .inspection-item {
          border: 1px solid var(--line);
          border-radius: 14px;
          background: #f8fafc;
          padding: 12px;
          overflow-x: auto;
        }

        .inspection-item pre,
        .profile-json {
          margin: 0;
          white-space: pre-wrap;
          word-break: break-word;
          color: #334155;
          font-size: 0.86rem;
          line-height: 1.5;
        }

        @media (max-width: 860px) {
          .dashboard-hero,
          .section-heading,
          .recent-job,
          .asset-row {
            align-items: stretch;
            flex-direction: column;
          }

          .asset-grid,
          .upload-form,
          .asset-kind-guide {
            grid-template-columns: 1fr;
          }

          .asset-row {
            grid-template-columns: 1fr;
          }

          .asset-actions {
            justify-content: flex-start;
          }
        }
      `}</style>
    </main>
  );
}

function AssetRow({
  asset,
  inspectionLoading,
  onDelete,
  onInspect,
}: {
  asset: AssetListItem;
  inspectionLoading: string | null;
  onDelete: (asset: AssetListItem) => Promise<void>;
  onInspect: (asset: AssetListItem, mode: InspectionMode) => Promise<void>;
}) {
  const isReady = asset.status === "ready";
  const previewLoading = inspectionLoading === `${asset.id}:preview`;
  const profileLoading = inspectionLoading === `${asset.id}:profile`;
  const latestJob = asset.latest_job;

  return (
    <article className="asset-row">
      <div className="asset-main">
        <div className="asset-title-line">
          <span className={`kind-chip ${asset.kind}`}>{asset.kind}</span>
          <strong>{asset.title}</strong>
          <span className={`status-chip small ${asset.status}`}>
            {asset.status}
          </span>
        </div>
        <div className="asset-meta muted">
          <span>{asset.original_filename}</span>
          <span>Created {new Date(asset.created_at).toLocaleDateString()}</span>
          {latestJob && <span>Job {latestJob.status}</span>}
          {latestJob?.error_message && <span>{latestJob.error_message}</span>}
        </div>
      </div>

      <div className="asset-actions">
        <button
          className="button secondary small"
          disabled={!isReady || previewLoading}
          onClick={() => void onInspect(asset, "preview")}
          title={isReady ? "Inspect asset preview" : "Available when ready"}
        >
          {previewLoading ? "Loading..." : "Preview"}
        </button>
        {asset.kind === "dataset" && (
          <button
            className="button secondary small"
            disabled={!isReady || profileLoading}
            onClick={() => void onInspect(asset, "profile")}
            title={isReady ? "Inspect dataset profile" : "Available when ready"}
          >
            {profileLoading ? "Loading..." : "Profile"}
          </button>
        )}
        <button className="danger-button" onClick={() => void onDelete(asset)}>
          Delete
        </button>
      </div>
    </article>
  );
}

function MetricCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="metric-card">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function InspectionPayload({ inspection }: { inspection: InspectionState }) {
  if (inspection.mode === "profile") {
    const payload = inspection.payload as AssetProfileResponse;
    return (
      <pre className="profile-json">
        {JSON.stringify(payload.profile_data, null, 2)}
      </pre>
    );
  }

  const payload = inspection.payload as AssetPreviewResponse;
  if (payload.preview_data.length === 0) {
    return <p className="muted">No preview data available yet.</p>;
  }

  return (
    <div className="inspection-list">
      {payload.preview_data.map((item, index) => (
        <div className="inspection-item" key={index}>
          <pre>{JSON.stringify(item, null, 2)}</pre>
        </div>
      ))}
    </div>
  );
}
