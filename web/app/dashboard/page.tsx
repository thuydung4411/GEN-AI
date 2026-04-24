import { redirect } from "next/navigation";

import { DashboardShell } from "./dashboard-shell";
import { hasSupabaseEnv } from "../../lib/config";
import { createSupabaseServerClient } from "../../lib/supabase/server";

export const dynamic = "force-dynamic";

export default async function DashboardPage() {
  if (!hasSupabaseEnv()) {
    return (
      <main className="page-shell">
        <section className="card" style={{ padding: 32, display: "grid", gap: 12 }}>
          <p style={{ margin: 0, letterSpacing: "0.08em", textTransform: "uppercase", color: "#0f766e" }}>
            Setup Required
          </p>
          <h1 style={{ margin: 0 }}>Supabase environment variables are missing.</h1>
          <p className="muted" style={{ margin: 0 }}>
            Add `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY` in
            `web/.env.local`, then rebuild the app.
          </p>
        </section>
      </main>
    );
  }

  const supabase = await createSupabaseServerClient();
  const {
    data: { user }
  } = await supabase.auth.getUser();

  if (!user) {
    redirect("/login");
  }

  return <DashboardShell userEmail={user.email ?? "unknown"} />;
}
