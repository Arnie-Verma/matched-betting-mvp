// apps/web/src/app/api/proxy/debug/route.ts
import { NextResponse, type NextRequest } from "next/server";
import { getAuth } from "@clerk/nextjs/server";

export const runtime = "nodejs";

export async function GET(req: NextRequest) {
  const { userId, sessionId, getToken } = getAuth(req);

  let token: string | null = null;
  let tokenErr: string | null = null;

  try {
    token = await getToken({ template: process.env.CLERK_JWT_TEMPLATE || "mb-api" });
  } catch (e: any) {
    tokenErr = e?.message ?? String(e);
  }

  return NextResponse.json({
    path: "/api/proxy/debug",
    userId,
    sessionId,
    hasToken: Boolean(token),
    tokenPreview: token ? token.slice(0, 24) + "..." : null,
    tokenErr,
  });
}
