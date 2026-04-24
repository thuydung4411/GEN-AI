import { redirect } from "next/navigation";
import { createSupabaseServerClient } from "../../../lib/supabase/server";
import ChatView from "./chat-view";

export const dynamic = "force-dynamic";

export default async function ChatPage() {
  const supabase = await createSupabaseServerClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    redirect("/login");
  }

  // Khung chứa toàn màn hình không giới hạn bởi page-shell
  return (
    <div style={{ height: "100vh", width: "100vw", margin: 0, padding: 0 }}>
      <ChatView />
    </div>
  );
}
