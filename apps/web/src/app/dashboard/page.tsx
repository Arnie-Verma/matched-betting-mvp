
import { auth, currentUser } from "@clerk/nextjs/server";

export default async function DashboardPage() {
  const { userId, sessionId } = await auth();   // <-- await is required
  const user = await currentUser();

  return (
    <main className="max-w-xl mx-auto py-12 space-y-6">
      <h1 className="text-2xl font-semibold">Dashboard (Protected)</h1>
      <div className="rounded-xl border p-4 space-y-2">
        <div><strong>User ID:</strong> {userId}</div>
        <div><strong>Session ID:</strong> {sessionId}</div>
        <div><strong>Email:</strong> {user?.emailAddresses?.[0]?.emailAddress}</div>
        <div><strong>Email verified:</strong> {String(user?.emailAddresses?.[0]?.verification?.status === "verified")}</div>
      </div>
    </main>
  );
}
