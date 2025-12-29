'use client'

import Link from 'next/link'
import { Calculator, Divide, Target, Layers, TrendingUp, Lock } from 'lucide-react'
import { useSubscription } from '@/hooks/useSubscription'

interface CalculatorCard {
  name: string
  description: string
  href: string
  icon: React.ReactNode
  isPremium: boolean
}

const calculators: CalculatorCard[] = [
  {
    name: 'Back/Lay Calculator',
    description: 'Calculate lay stakes for matched betting. Essential for converting bonus bets and placing qualifying bets.',
    href: '/calculators/back-lay',
    icon: <Calculator className="w-6 h-6" />,
    isPremium: false
  },
  {
    name: 'Dutching Calculator',
    description: 'Split stakes across multiple outcomes to guarantee equal profit regardless of result.',
    href: '/calculators/dutching',
    icon: <Divide className="w-6 h-6" />,
    isPremium: false
  },
  {
    name: 'True Odds Calculator',
    description: 'Remove bookmaker margin to find fair odds. Identify value bets by comparing to true probability.',
    href: '/calculators/true-odds',
    icon: <Target className="w-6 h-6" />,
    isPremium: false
  },
  {
    name: 'Multi Calculator',
    description: 'Calculate expected value for multi-leg bets including SGM and any-leg-fail promotions.',
    href: '/calculators/multi',
    icon: <Layers className="w-6 h-6" />,
    isPremium: true
  },
  {
    name: 'Long Term EV Calculator',
    description: 'Simulate expected value over many bets using Monte Carlo analysis. Understand variance and risk.',
    href: '/calculators/ev',
    icon: <TrendingUp className="w-6 h-6" />,
    isPremium: true
  }
]

export default function CalculatorsIndexPage() {
  const { isPremium, isLoading } = useSubscription()

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="text-center">
        <h1 className="text-3xl font-bold text-gray-900">Calculators</h1>
        <p className="text-gray-600 mt-2 max-w-2xl mx-auto">
          Professional betting calculators to help you make informed decisions and maximize your profits.
        </p>
      </div>

      {/* Calculator Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {calculators.map((calc) => {
          const isLocked = calc.isPremium && !isPremium && !isLoading

          return (
            <Link
              key={calc.href}
              href={calc.href}
              className={`block bg-white rounded-xl border border-gray-200 p-6 transition-all hover:shadow-lg hover:border-blue-300 ${
                isLocked ? 'opacity-75' : ''
              }`}
            >
              <div className="flex items-start gap-4">
                <div className={`p-3 rounded-xl ${
                  calc.isPremium
                    ? 'bg-purple-100 text-purple-600'
                    : 'bg-blue-100 text-blue-600'
                }`}>
                  {calc.icon}
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <h2 className="text-lg font-semibold text-gray-900">{calc.name}</h2>
                    {calc.isPremium && (
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${
                        isPremium
                          ? 'bg-green-100 text-green-700'
                          : 'bg-gray-100 text-gray-600'
                      }`}>
                        {isPremium ? (
                          'Premium'
                        ) : (
                          <>
                            <Lock className="w-3 h-3" />
                            Premium
                          </>
                        )}
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-gray-600 mt-1">{calc.description}</p>
                </div>
              </div>
            </Link>
          )
        })}
      </div>

      {/* Upgrade CTA for free users */}
      {!isPremium && !isLoading && (
        <div className="bg-gradient-to-r from-blue-600 to-purple-600 rounded-xl p-6 text-white text-center">
          <h3 className="text-xl font-bold mb-2">Unlock All Calculators</h3>
          <p className="text-blue-100 mb-4">
            Upgrade to Premium to access Multi Calculator and Long Term EV Calculator
          </p>
          <Link
            href="/billing"
            className="inline-block px-6 py-3 bg-white text-blue-600 rounded-xl font-medium hover:bg-blue-50 transition-colors"
          >
            View Plans
          </Link>
        </div>
      )}
    </div>
  )
}
