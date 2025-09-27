// apps/web/src/app/api/proxy/whoami/route.ts
import type { NextRequest } from "next/server";
import { callApi } from "@/lib/serverApi"; // ✅ not "@/app/lib/..."

export const runtime = "nodejs";

export async function GET(req: NextRequest) {
  // ✅ callApi will automatically handle authentication
  return callApi("/whoami", { method: "GET" });
}
