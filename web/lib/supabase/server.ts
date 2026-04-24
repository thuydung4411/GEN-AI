import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";

import { assertWebEnv, webEnv } from "../config";

export async function createSupabaseServerClient() {
  assertWebEnv();

  const cookieStore = await cookies();

  return createServerClient(webEnv.supabaseUrl, webEnv.supabaseAnonKey, {
    cookies: {
      getAll() {
        return cookieStore.getAll();
      }
    }
  });
}
