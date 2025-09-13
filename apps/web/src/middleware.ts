import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";

const isProtectedRoute = createRouteMatcher([
  "/dashboard(.*)",
  "/account(.*)",
]);

export default clerkMiddleware(async (auth, req) => {
  const { userId, redirectToSignIn } = await auth();
  if (!userId && isProtectedRoute(req)) {
    return redirectToSignIn();
  }
  return NextResponse.next();
});

// Don't intercept Next internals or static assets or our /healthz probe
export const config = {
  matcher: ["/((?!_next|.*\\..*|favicon.ico|healthz).*)"],
};
