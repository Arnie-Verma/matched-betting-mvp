// apps/web/src/app/billing/page.tsx
import PricingPlans from '@/components/billing/PricingPlans'

export default function BillingPage() {
  return (
    <div className="min-h-screen bg-gray-50">
      <PricingPlans />
    </div>
  )
}