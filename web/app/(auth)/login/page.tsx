import { LoginForm } from "../../../components/login-form";

export default function LoginPage() {
  return (
    <main className="page-shell">
      <section
        className="card"
        style={{
          display: "grid",
          gridTemplateColumns: "1.1fr 0.9fr",
          overflow: "hidden"
        }}
      >
        <div
          style={{
            padding: "40px",
            background:
              "linear-gradient(155deg, rgba(15, 118, 110, 0.92), rgba(12, 74, 110, 0.96))",
            color: "white"
          }}
        >
          <p style={{ margin: 0, opacity: 0.8, letterSpacing: "0.08em", textTransform: "uppercase" }}>
            Phase 1
          </p>
          <h1 style={{ margin: "16px 0 12px", fontSize: "2.5rem", lineHeight: 1.05 }}>
            Authenticate, upload, and review the ingestion queue.
          </h1>
          <p style={{ margin: 0, maxWidth: 420, opacity: 0.88, lineHeight: 1.6 }}>
            This milestone focuses on the foundation: auth, workspace-scoped uploads, and
            pending jobs that are ready for the Phase 2 ingestion worker.
          </p>
        </div>
        <div style={{ padding: "40px" }}>
          <h2 className="section-title" style={{ fontSize: "1.7rem" }}>
            Sign in
          </h2>
          <p className="section-subtitle" style={{ marginBottom: 24 }}>
            Use a Supabase account that belongs to your pilot environment.
          </p>
          <LoginForm />
        </div>
      </section>
    </main>
  );
}
