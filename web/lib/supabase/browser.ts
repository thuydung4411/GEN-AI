import { createBrowserClient } from "@supabase/ssr";

import { assertWebEnv, webEnv } from "../config";

let browserClient: ReturnType<typeof createBrowserClient> | null = null;

export function createSupabaseBrowserClient() {
  assertWebEnv();

  if (!browserClient) {
    browserClient = createBrowserClient(webEnv.supabaseUrl, webEnv.supabaseAnonKey);
  }

  return browserClient;
}
