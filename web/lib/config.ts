export const webEnv = {
  apiBaseUrl: process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000",
  supabaseAnonKey: process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "",
  supabaseUrl: process.env.NEXT_PUBLIC_SUPABASE_URL ?? ""
};

export function hasSupabaseEnv() {
  return Boolean(webEnv.supabaseUrl && webEnv.supabaseAnonKey);
}

export function assertWebEnv() {
  if (!hasSupabaseEnv()) {
    throw new Error("Supabase environment variables are missing.");
  }

  if (!webEnv.apiBaseUrl) {
    throw new Error("NEXT_PUBLIC_API_BASE_URL is missing.");
  }
}
