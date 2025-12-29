'use client'

import { useState, useEffect } from 'react'
import { useUser, useAuth } from '@clerk/nextjs'

interface SubscriptionData {
  current_plan: string
  plan_status: string
  features: Record<string, unknown>
}

interface UseSubscriptionResult {
  plan: string
  isLoading: boolean
  isPremium: boolean
  isDiamond: boolean
  canAccessFeature: (feature: string) => boolean
}

// Define which features are available per plan
const PLAN_FEATURES: Record<string, string[]> = {
  free: ['back_lay', 'dutching', 'true_odds', 'odds_matcher'],
  premium: ['back_lay', 'dutching', 'true_odds', 'multi', 'long_term_ev', 'odds_matcher', 'all_tools'],
  diamond: ['back_lay', 'dutching', 'true_odds', 'multi', 'long_term_ev', 'odds_matcher', 'all_tools', 'api_access'],
  platinum: ['back_lay', 'dutching', 'true_odds', 'multi', 'long_term_ev', 'odds_matcher', 'all_tools', 'api_access']
}

export function useSubscription(): UseSubscriptionResult {
  const { user, isLoaded } = useUser()
  const { getToken } = useAuth()
  const [plan, setPlan] = useState<string>('free')
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    async function fetchSubscription() {
      if (!isLoaded || !user) {
        setIsLoading(false)
        return
      }

      try {
        const token = await getToken()
        // Use the proxy route to avoid CORS issues
        const response = await fetch('/api/proxy/billing/subscription', {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          },
          credentials: 'include'
        })

        if (response.ok) {
          const data: SubscriptionData = await response.json()
          setPlan(data.current_plan?.toLowerCase() || 'free')
        } else {
          // Default to free plan if API call fails
          console.warn('Subscription API returned non-OK status:', response.status)
          setPlan('free')
        }
      } catch (error) {
        console.error('Failed to fetch subscription:', error)
        setPlan('free')
      } finally {
        setIsLoading(false)
      }
    }

    fetchSubscription()
  }, [user, isLoaded, getToken])

  const isPremium = ['premium', 'diamond', 'platinum'].includes(plan)
  const isDiamond = ['diamond', 'platinum'].includes(plan)

  const canAccessFeature = (feature: string): boolean => {
    const features = PLAN_FEATURES[plan] || PLAN_FEATURES.free
    return features.includes(feature)
  }

  return {
    plan,
    isLoading,
    isPremium,
    isDiamond,
    canAccessFeature
  }
}

// Premium lock component for premium-only features
export function PremiumLock({ feature, children }: { feature: string; children: React.ReactNode }) {
  const { canAccessFeature, isLoading, plan } = useSubscription()

  if (isLoading) {
    return (
      <div className="min-h-[400px] flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    )
  }

  if (!canAccessFeature(feature)) {
    return (
      <div className="min-h-[400px] flex flex-col items-center justify-center text-center px-4">
        <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mb-4">
          <svg className="w-8 h-8 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
          </svg>
        </div>
        <h2 className="text-xl font-bold text-gray-900 mb-2">Premium Feature</h2>
        <p className="text-gray-600 mb-6 max-w-md">
          This calculator is available on Premium and Diamond plans. Upgrade to unlock all calculators and tools.
        </p>
        <a
          href="/billing"
          className="px-6 py-3 bg-blue-600 text-white rounded-xl font-medium hover:bg-blue-700 transition-colors"
        >
          Upgrade Now
        </a>
        <p className="text-sm text-gray-500 mt-4">
          Current plan: <span className="font-medium capitalize">{plan}</span>
        </p>
      </div>
    )
  }

  return <>{children}</>
}
