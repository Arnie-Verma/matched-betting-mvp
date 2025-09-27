// apps/web/src/app/api/proxy/billing/create-checkout-session/route.ts
import type { NextRequest } from "next/server";
import { callApi } from "@/lib/serverApi";

export const runtime = "nodejs";

export async function POST(req: NextRequest) {
  const body = await req.json();
  return callApi("/billing/create-checkout-session", {
    method: "POST",
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });
}