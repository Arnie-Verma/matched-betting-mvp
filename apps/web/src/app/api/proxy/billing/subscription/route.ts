// apps/web/src/app/api/proxy/billing/subscription/route.ts
import { callApi } from "@/lib/serverApi";

export const runtime = "nodejs";

export async function GET() {
  return callApi("/billing/subscription", { method: "GET" });
}