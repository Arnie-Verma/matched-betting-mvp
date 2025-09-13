// apps/web/src/lib/apiProxy.ts
import "server-only";
import { auth } from "@clerk/nextjs/server";

const API_BASE =
  process.env.INTERNAL_API_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8000";

const TEMPLATE = process.env.CLERK_JWT_TEMPLATE || "mb-api";

/**
 * Server-side helper:
 *  - mints a short-lived JWT from Clerk (template: mb-api)
 *  - forwards the request to FastAPI with Authorization: Bearer <jwt>
 *  - keeps tokens off the client
 */
export async function callApi(
  path: string,
  init?: RequestInit & { method?: string }
) {
  // auth() is async in your setup → await it, then call getToken()
  const a = await auth();
  const token = await a.getToken({ template: TEMPLATE }); // string | null

  const headers = new Headers(init?.headers);
  if (!headers.has("content-type")) {
    headers.set("content-type", "application/json");
  }
  if (token) headers.set("authorization", `Bearer ${token}`);

  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
    cache: "no-store",
  });

  return res;
}
