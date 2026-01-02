// apps/web/src/app/api/proxy/billing/subscription/route.ts
import { callApi } from "@/lib/serverApi";

export const runtime = "nodejs";

export async function GET(request: Request) {
  const authHeader = request.headers.get("authorization") || undefined;
  return callApi("/billing/subscription", {
    method: "GET",
    headers: authHeader ? { Authorization: authHeader } : undefined,
  });
}
