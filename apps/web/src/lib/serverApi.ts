// apps/web/src/lib/serverApi.ts
import "server-only";
import { getAuth } from "@clerk/nextjs/server";
import type { NextRequest } from "next/server";

const API_BASE =
  process.env.INTERNAL_API_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8000";

const TEMPLATE = process.env.CLERK_JWT_TEMPLATE || "mb-api";
const NO_AUTH_PATHS = new Set<string>(["/health"]);

export async function callApi(path: string, init: RequestInit, req: NextRequest) {
  const headers = new Headers(init?.headers);
  if (!headers.has("content-type")) headers.set("content-type", "application/json");

  if (!NO_AUTH_PATHS.has(path)) {
    try {
      const { getToken } = getAuth(req);
      const token = await getToken({ template: TEMPLATE });
      // 🔎 TEMP DEBUG
      console.log("[serverApi] path:", path, "mintedToken?", !!token);
      if (token) {
        headers.set("authorization", `Bearer ${token}`);
        // 🔎 TEMP DEBUG (short preview)
        console.log(
          "[serverApi] auth hdr:",
          headers.get("authorization")?.slice(0, 30) + "..."
        );
      }
    } catch (e) {
      console.warn("[serverApi] getToken error:", e);
    }
  } else {
    console.log("[serverApi] path:", path, "(no-auth passthrough)");
  }

  const url = `${API_BASE}${path}`;
  console.log("[serverApi] fetch →", url);
  return fetch(url, { ...init, headers, cache: "no-store" });
}
