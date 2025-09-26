// apps/web/src/app/api/proxy/whoami/route.ts
import type { NextRequest } from "next/server";
import { callApi } from "@/lib/serverApi"; // ✅ not "@/app/lib/..."

export const runtime = "nodejs";

export async function GET(req: NextRequest) {
  // ✅ pass req through — if you omit this, no token will be minted
  return callApi("/whoami", { method: "GET" }, req);
}
