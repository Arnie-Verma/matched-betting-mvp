import { OddsMatcherClient } from '@/components/odds-matcher/OddsMatcherClient'

export default function OddsMatcherPage() {
  return (
    <main className="max-w-7xl mx-auto py-8 px-4">
      <div className="mb-6">
        <h1 className="text-3xl font-bold mb-2">Odds Matcher</h1>
        <p className="text-gray-600">
          Find the best matched betting opportunities with real-time odds comparison
        </p>
      </div>

      <OddsMatcherClient />
    </main>
  )
}
