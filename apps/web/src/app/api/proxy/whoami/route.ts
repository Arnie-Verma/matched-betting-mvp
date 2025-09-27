// apps/web/src/app/api/proxy/whoami/route.ts
import { callApi } from "@/lib/serverApi"; // ✅ not "@/app/lib/..."

export const runtime = "nodejs";

export async function GET() {
  // ✅ callApi will automatically handle authentication
  return callApi("/whoami", { method: "GET" });
}
