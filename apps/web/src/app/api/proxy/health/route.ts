// apps/web/src/app/api/proxy/health/route.ts
import { callApi } from "@/lib/serverApi";

export const runtime = "nodejs";
export async function GET() {
  return callApi("/health", { method: "GET" }); // Health endpoint doesn't need auth
}
