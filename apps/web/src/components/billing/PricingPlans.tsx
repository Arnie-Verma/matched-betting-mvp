// apps/web/src/components/billing/PricingPlans.tsx
'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useUser } from '@clerk/nextjs'
import { clientApi } from '@/lib/clientApi'

interface Plan {
  id: number
  name: string
  display_name: string
  description: string
  price_monthly_cents: number | null
  price_yearly_cents: number | null
  stripe_price_monthly_id: string | null
  stripe_price_yearly_id: string | null
  features: Record<string, unknown>
  sort_order: number
}


interface SubscriptionDetails {
  id: number
  stripe_subscription_id: string
  status: string
  billing_cycle: string
  current_period_start: string | null
  current_period_end: string | null
  trial_end: string | null
  amount_cents: number
  currency: string
  is_active: boolean
  is_trial: boolean
}

interface SubscriptionStatus {
  user_id: number
  current_plan: string
  plan_status: string
  features: Record<string, unknown>
  subscription: SubscriptionDetails | null
}

interface PlansResponse {
  plans: Plan[]
}

interface CheckoutResponse {
  checkout_url: string
  session_id: string
}

interface PortalResponse {
  portal_url: string
}

export default function PricingPlans() {
  const [plans, setPlans] = useState<Plan[]>([])
  const [subscriptionStatus, setSubscriptionStatus] = useState<SubscriptionStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const billingCycle = 'monthly' // Only monthly billing
  const [creatingCheckout, setCreatingCheckout] = useState<string | null>(null)
  const { user } = useUser()
  const router = useRouter()

  useEffect(() => {
    const fetchData = async () => {
      try {
        // Always fetch plans for all users (including unauthenticated)
        const plansRes = await clientApi.get('/billing/plans')
        setPlans((plansRes as PlansResponse).plans)

        // Only fetch subscription status if user is authenticated
        if (user) {
          try {
            const statusRes = await clientApi.get('/billing/subscription')
            setSubscriptionStatus(statusRes as SubscriptionStatus)
          } catch (error) {
            console.error('Error fetching subscription status:', error)
          }
        }
      } catch (error) {
        console.error('Error fetching billing data:', error)
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [user])

  const formatPrice = (cents: number | null) => {
    if (!cents) return '$0'
    return `$${(cents / 100).toFixed(0)}`
  }

  const getFeatureList = (plan: Plan): string[] => {
    // Use the feature_list from features JSON
    if (plan.features.feature_list && Array.isArray(plan.features.feature_list)) {
      return plan.features.feature_list as string[]
    }
    return []
  }

  const handleSubscribe = async (plan: Plan) => {
    if (!user) {
      router.push('/sign-in')
      return
    }

    // Handle free tier - no Stripe involvement
    if (plan.name === 'free') {
      // User is already authenticated, just redirect to dashboard
      router.push('/dashboard')
      return
    }

    const priceId = billingCycle === 'monthly'
      ? plan.stripe_price_monthly_id
      : plan.stripe_price_yearly_id

    if (!priceId) {
      alert('Price not available for this plan')
      return
    }

    setCreatingCheckout(plan.name)

    try {
      const response = await clientApi.post('/billing/create-checkout-session', {
        price_id: priceId,
        success_url: `${window.location.origin}/billing/success?session_id={CHECKOUT_SESSION_ID}`,
        cancel_url: `${window.location.origin}/billing/cancel`,
        // No trial periods
      }) as CheckoutResponse

      if (response.checkout_url) {
        window.location.href = response.checkout_url
      } else {
        throw new Error('No checkout URL received')
      }
    } catch (error) {
      console.error('Error creating checkout session:', error)
      alert('Failed to create checkout session. Please try again.')
    } finally {
      setCreatingCheckout(null)
    }
  }

  const handleManageBilling = async () => {
    try {
      const response = await clientApi.post('/billing/create-portal-session', {
        return_url: window.location.origin + '/billing'
      }) as PortalResponse

      if (response.portal_url) {
        window.location.href = response.portal_url
      } else {
        throw new Error('No portal URL received')
      }
    } catch (error) {
      console.error('Error creating portal session:', error)
      alert('Failed to open billing portal. Please try again.')
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center items-center min-h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    )
  }

  const isCurrentPlan = (planName: string) => {
    return subscriptionStatus?.current_plan === planName
  }

  const hasActiveSubscription = subscriptionStatus?.subscription?.is_active

  return (
    <div className="max-w-6xl mx-auto px-4 py-12">
      <div className="text-center mb-12">
        <h1 className="text-4xl font-bold text-gray-900 mb-4">
          Choose Your Plan
        </h1>
        <p className="text-xl text-gray-600 mb-8">
          Scale your matched betting with the right plan for you
        </p>
      </div>

      {/* Current Subscription Status */}
      {subscriptionStatus && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-6 mb-8">
          <div className="flex justify-between items-center">
            <div>
              <h3 className="text-lg font-semibold text-blue-900">
                Current Plan: {subscriptionStatus.current_plan.charAt(0).toUpperCase() + subscriptionStatus.current_plan.slice(1)}
              </h3>
              <p className="text-blue-700">
                Status: {subscriptionStatus.plan_status}
                {subscriptionStatus.subscription?.is_trial && ' (Trial)'}
              </p>
              {subscriptionStatus.subscription?.current_period_end && (
                <p className="text-sm text-blue-600">
                  {subscriptionStatus.subscription.is_active
                    ? `Renews on ${new Date(subscriptionStatus.subscription.current_period_end).toLocaleDateString()}`
                    : `Ended on ${new Date(subscriptionStatus.subscription.current_period_end).toLocaleDateString()}`
                  }
                </p>
              )}
            </div>
            {hasActiveSubscription && (
              <button
                onClick={handleManageBilling}
                className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors"
              >
                Manage Billing
              </button>
            )}
          </div>
        </div>
      )}

      {/* Plans Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
        {plans.map((plan) => {
          const price = plan.price_monthly_cents // Only monthly pricing
          const isPopular = plan.name === 'premium'
          const isCurrent = isCurrentPlan(plan.name)

          return (
            <div
              key={plan.id}
              className={`relative bg-white rounded-2xl shadow-lg border-2 transition-all hover:shadow-xl ${
                isPopular ? 'border-blue-500' : 'border-gray-200'
              } ${isCurrent ? 'ring-2 ring-green-500' : ''}`}
            >
              {isPopular && (
                <div className="absolute top-0 left-1/2 transform -translate-x-1/2 -translate-y-1/2">
                  <span className="bg-blue-500 text-white px-4 py-1 rounded-full text-sm font-medium">
                    Most Popular
                  </span>
                </div>
              )}

              {isCurrent && (
                <div className="absolute top-4 right-4">
                  <span className="bg-green-500 text-white px-3 py-1 rounded-full text-sm font-medium">
                    Current Plan
                  </span>
                </div>
              )}

              <div className="p-8">
                <h3 className="text-2xl font-bold text-gray-900 mb-2">
                  {plan.display_name}
                </h3>

                <div className="mb-4">
                  <span className="text-4xl font-bold text-gray-900">
                    {formatPrice(price)}
                  </span>
                  <span className="text-gray-600 ml-1">/month</span>
                </div>

                <p className="text-gray-600 text-sm mb-6">{plan.description}</p>

                <div className="mb-6">
                  <p className="font-semibold text-gray-900 mb-3">
                    {plan.display_name} includes:
                  </p>
                  <ul className="space-y-2">
                    {getFeatureList(plan).map((feature, index) => (
                      <li key={index} className="text-sm text-gray-700">
                        {feature}
                      </li>
                    ))}
                  </ul>
                </div>

                <button
                  onClick={() => {
                    if (isCurrent) {
                      handleManageBilling()
                    } else {
                      handleSubscribe(plan)
                    }
                  }}
                  disabled={creatingCheckout === plan.name}
                  className={`w-full py-3 px-4 rounded-lg font-medium transition-colors ${
                    isCurrent
                      ? 'bg-blue-600 text-white hover:bg-blue-700'
                      : plan.name === 'free'
                      ? 'bg-gray-900 text-white hover:bg-gray-800'
                      : isPopular
                      ? 'bg-blue-600 text-white hover:bg-blue-700'
                      : 'bg-gray-900 text-white hover:bg-gray-800'
                  } ${creatingCheckout === plan.name ? 'opacity-50 cursor-not-allowed' : ''}`}
                >
                  {creatingCheckout === plan.name ? (
                    <span className="flex items-center justify-center">
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                      Loading...
                    </span>
                  ) : isCurrent ? (
                    'Manage subscription'
                  ) : plan.name === 'free' ? (
                    'Try for free'
                  ) : (
                    'Select this plan'
                  )}
                </button>

                {plan.name !== 'free' && !isCurrent && (
                  <p className="text-xs text-gray-500 text-center mt-3">
                    Cancel anytime
                  </p>
                )}
              </div>
            </div>
          )
        })}
      </div>

      {/* FAQ or Additional Info */}
      <div className="mt-16 text-center">
        <p className="text-gray-600">
          All plans include GST. Need help choosing? {' '}
          <a href="mailto:support@matchedbetting.com" className="text-blue-600 hover:underline">
            Contact our team
          </a>
        </p>
      </div>
    </div>
  )
}
