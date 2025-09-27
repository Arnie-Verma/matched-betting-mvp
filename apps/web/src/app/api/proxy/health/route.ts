// apps/web/src/app/api/proxy/health/route.ts
import type { NextRequest } from "next/server";
import { callApi } from "@/lib/serverApi";

export const runtime = "nodejs";
export async function GET(req: NextRequest) {
  return callApi("/health", { method: "GET" }); // Health endpoint doesn't need auth
}
