// apps/web/src/app/billing/success/page.tsx
'use client'

import { useEffect, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import Link from 'next/link'

export default function BillingSuccessPage() {
  const [loading, setLoading] = useState(true)
  const searchParams = useSearchParams()
  const sessionId = searchParams.get('session_id')

  useEffect(() => {
    const timer = setTimeout(() => {
      setLoading(false)
    }, 2000)
    return () => clearTimeout(timer)
  }, [])

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="max-w-md mx-auto text-center">
          <div className="animate-spin rounded-full h-16 w-16 border-b-2 border-primary mx-auto mb-4"></div>
          <h2 className="text-xl font-semibold text-foreground mb-2">
            Processing your subscription...
          </h2>
          <p className="text-muted-foreground">
            Please wait while we set up your account.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background flex items-center justify-center">
      <div className="max-w-md mx-auto text-center bg-card rounded-lg shadow-lg p-8">
        <div className="w-16 h-16 bg-[var(--profit-soft)] rounded-full flex items-center justify-center mx-auto mb-6">
          <svg
            className="w-8 h-8 text-[var(--profit)]"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M5 13l4 4L19 7"
            />
          </svg>
        </div>

        <h1 className="text-2xl font-bold text-foreground mb-4">
          Welcome to your new plan!
        </h1>

        <p className="text-muted-foreground mb-6">
          Your subscription has been successfully activated. You now have access to all the features of your selected plan.
        </p>

        <div className="space-y-3">
          <Link
            href="/dashboard"
            className="block w-full bg-primary text-white py-3 px-4 rounded-lg font-medium hover:bg-primary/90 transition-colors"
          >
            Go to Dashboard
          </Link>

          <Link
            href="/billing"
            className="block w-full bg-muted text-foreground/80 py-3 px-4 rounded-lg font-medium hover:bg-muted/80 transition-colors"
          >
            Manage Billing
          </Link>
        </div>

        {sessionId && (
          <p className="text-xs text-muted-foreground/60 mt-6">
            Session ID: {sessionId}
          </p>
        )}
      </div>
    </div>
  )
}
