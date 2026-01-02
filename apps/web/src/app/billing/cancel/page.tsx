// apps/web/src/app/billing/cancel/page.tsx
'use client'

import Link from 'next/link'

export default function BillingCancelPage() {
  return (
    <div className="min-h-screen bg-background flex items-center justify-center">
      <div className="max-w-md mx-auto text-center bg-card rounded-lg shadow-lg p-8">
        <div className="w-16 h-16 bg-[var(--highlight-soft)] rounded-full flex items-center justify-center mx-auto mb-6">
          <svg
            className="w-8 h-8 text-[var(--highlight)]"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.966-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z"
            />
          </svg>
        </div>

        <h1 className="text-2xl font-bold text-foreground mb-4">
          Subscription Cancelled
        </h1>

        <p className="text-muted-foreground mb-6">
          Your subscription process was cancelled. No charges have been made to your account.
        </p>

        <div className="space-y-3">
          <Link
            href="/billing"
            className="block w-full bg-primary text-white py-3 px-4 rounded-lg font-medium hover:bg-primary/90 transition-colors"
          >
            Try Again
          </Link>

          <Link
            href="/dashboard"
            className="block w-full bg-muted text-foreground/80 py-3 px-4 rounded-lg font-medium hover:bg-muted/80 transition-colors"
          >
            Return to Dashboard
          </Link>
        </div>

        <div className="mt-8 pt-6 border-t border-border">
          <p className="text-sm text-muted-foreground mb-3">
            Need help choosing the right plan?
          </p>
          <Link
            href="mailto:support@matchedbetting.com"
            className="text-primary hover:underline text-sm"
          >
            Contact our support team
          </Link>
        </div>
      </div>
    </div>
  )
}
