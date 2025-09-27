
import { auth, currentUser } from "@clerk/nextjs/server";
import Link from 'next/link';

export default async function DashboardPage() {
  const { userId, sessionId } = await auth();   // <-- await is required
  const user = await currentUser();

  return (
    <main className="max-w-4xl mx-auto py-12 space-y-8">
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold">Dashboard</h1>
        <Link
          href="/billing"
          className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors"
        >
          Manage Billing
        </Link>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* User Info */}
        <div className="bg-white rounded-xl border shadow-sm p-6">
          <h2 className="text-xl font-semibold mb-4">Account Information</h2>
          <div className="space-y-2">
            <div><strong>User ID:</strong> {userId}</div>
            <div><strong>Session ID:</strong> {sessionId}</div>
            <div><strong>Email:</strong> {user?.emailAddresses?.[0]?.emailAddress}</div>
            <div><strong>Email verified:</strong> {String(user?.emailAddresses?.[0]?.verification?.status === "verified")}</div>
          </div>
        </div>

        {/* Quick Actions */}
        <div className="bg-white rounded-xl border shadow-sm p-6">
          <h2 className="text-xl font-semibold mb-4">Quick Actions</h2>
          <div className="space-y-3">
            <Link
              href="/billing"
              className="block w-full text-left bg-gray-50 hover:bg-gray-100 p-3 rounded-lg transition-colors"
            >
              <div className="font-medium">Manage Subscription</div>
              <div className="text-sm text-gray-600">View plans and billing details</div>
            </Link>
            <Link
              href="/api/proxy/echo-auth"
              className="block w-full text-left bg-gray-50 hover:bg-gray-100 p-3 rounded-lg transition-colors"
            >
              <div className="font-medium">Test API Authentication</div>
              <div className="text-sm text-gray-600">Verify your API access</div>
            </Link>
          </div>
        </div>
      </div>

      {/* Coming Soon Features */}
      <div className="bg-white rounded-xl border shadow-sm p-6">
        <h2 className="text-xl font-semibold mb-4">Coming Soon</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="text-center p-4 bg-gray-50 rounded-lg">
            <div className="text-2xl mb-2">🏆</div>
            <div className="font-medium">Bookmaker Management</div>
            <div className="text-sm text-gray-600">Add and track your bookmaker accounts</div>
          </div>
          <div className="text-center p-4 bg-gray-50 rounded-lg">
            <div className="text-2xl mb-2">📊</div>
            <div className="font-medium">Bet Tracking</div>
            <div className="text-sm text-gray-600">Monitor your matched betting performance</div>
          </div>
          <div className="text-center p-4 bg-gray-50 rounded-lg">
            <div className="text-2xl mb-2">🔔</div>
            <div className="font-medium">Profit Alerts</div>
            <div className="text-sm text-gray-600">Get notified of profitable opportunities</div>
          </div>
        </div>
      </div>
    </main>
  );
}
