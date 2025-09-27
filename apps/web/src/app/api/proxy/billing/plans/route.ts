// apps/web/src/app/api/proxy/billing/plans/route.ts
import { callApi } from "@/lib/serverApi";

export const runtime = "nodejs";

export async function GET() {
  return callApi("/billing/plans", { method: "GET" });
}