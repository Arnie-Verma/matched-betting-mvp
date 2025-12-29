'use client'

import { useState, useEffect } from 'react'
import { Plus, Trash2, Info, Settings, HelpCircle } from 'lucide-react'
import { calculateMulti, formatCurrency, formatPercentage } from '@/lib/calculators/calculations'
import { Label } from '@/components/ui/label'
import { PremiumLock } from '@/hooks/useSubscription'

// Helper to parse numeric input
const parseNumericInput = (value: string, fallback: number = 0): number => {
  if (value === '' || value === '-') return fallback
  const parsed = parseFloat(value)
  return isNaN(parsed) ? fallback : parsed
}

interface LegEntry {
  id: number
  oddsStr: string
}

function MultiCalculatorContent() {
  // Input state - use strings for controlled inputs
  const [stakeStr, setStakeStr] = useState<string>('50')
  const [overroundStr, setOverroundStr] = useState<string>('5')
  const [bonusRetentionStr, setBonusRetentionStr] = useState<string>('70')
  const [anyLegFail, setAnyLegFail] = useState<boolean>(false)
  const [isSGM, setIsSGM] = useState<boolean>(false)
  const [showAdvanced, setShowAdvanced] = useState<boolean>(false)
  const [legs, setLegs] = useState<LegEntry[]>([
    { id: 1, oddsStr: '1.5' }
  ])
  const [nextId, setNextId] = useState(2)

  // Parsed values
  const stake = parseNumericInput(stakeStr, 50)
  const overround = parseNumericInput(overroundStr, 5)
  const bonusRetention = parseNumericInput(bonusRetentionStr, 70)

  // Calculated results
  const [result, setResult] = useState(() =>
    calculateMulti(50, [{ odds: 1.5 }], 5, 70, false, false)
  )

  // Recalculate when inputs change
  useEffect(() => {
    const legData = legs.map(l => ({ odds: parseNumericInput(l.oddsStr, 1.5) }))
    const newResult = calculateMulti(
      stake,
      legData,
      overround,
      bonusRetention,
      anyLegFail,
      isSGM
    )
    setResult(newResult)
  }, [stake, legs.map(l => l.oddsStr).join(','), overround, bonusRetention, anyLegFail, isSGM])

  const addLeg = () => {
    setLegs(prev => [
      ...prev,
      { id: nextId, oddsStr: '1.5' }
    ])
    setNextId(prev => prev + 1)
  }

  const removeLeg = (id: number) => {
    if (legs.length <= 1) return
    setLegs(prev => prev.filter(l => l.id !== id))
  }

  const updateLegOdds = (id: number, oddsStr: string) => {
    setLegs(prev =>
      prev.map(l => l.id === id ? { ...l, oddsStr } : l)
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="text-center">
        <h1 className="text-3xl font-bold text-gray-900">Multi Calculator</h1>
        <p className="text-gray-600 mt-2">Calculate expected value for multi-leg bets</p>
      </div>

      {/* Advanced Toggle */}
      <div className="flex justify-end">
        <button
          onClick={() => setShowAdvanced(!showAdvanced)}
          className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
            showAdvanced
              ? 'bg-blue-100 text-blue-700'
              : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
          }`}
        >
          <Settings className="w-4 h-4" />
          Advanced
        </button>
      </div>

      {/* Promo Options */}
      <div className="bg-white rounded-xl border border-gray-200 p-4 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="font-medium text-gray-700">Any leg fail</span>
            <button className="text-gray-400 hover:text-gray-600">
              <HelpCircle className="w-4 h-4" />
            </button>
          </div>
          <label className="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              checked={anyLegFail}
              onChange={(e) => setAnyLegFail(e.target.checked)}
              className="sr-only peer"
            />
            <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-100 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
          </label>
        </div>

        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="font-medium text-gray-700">Is SGM</span>
            <button className="text-gray-400 hover:text-gray-600">
              <HelpCircle className="w-4 h-4" />
            </button>
          </div>
          <label className="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              checked={isSGM}
              onChange={(e) => setIsSGM(e.target.checked)}
              className="sr-only peer"
            />
            <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-100 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
          </label>
        </div>
      </div>

      {/* Stake Input */}
      <div className="bg-blue-50 rounded-xl p-4 border border-blue-100">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Label className="text-blue-800 font-medium">Stake</Label>
            <button className="text-blue-400 hover:text-blue-600">
              <HelpCircle className="w-4 h-4" />
            </button>
          </div>
          <input
            type="text"
            inputMode="decimal"
            value={stakeStr}
            onChange={(e) => setStakeStr(e.target.value)}
            className="w-32 px-3 py-2 border border-blue-200 rounded-lg text-center font-semibold focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
        </div>
      </div>

      {/* Advanced Options */}
      {showAdvanced && (
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-pink-50 rounded-xl p-4 border border-pink-100">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Label className="text-pink-800 font-medium">Overround</Label>
                <button className="text-pink-400 hover:text-pink-600">
                  <HelpCircle className="w-4 h-4" />
                </button>
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  inputMode="decimal"
                  value={overroundStr}
                  onChange={(e) => setOverroundStr(e.target.value)}
                  className="w-20 px-3 py-2 border border-pink-200 rounded-lg text-center font-semibold focus:ring-2 focus:ring-pink-500 focus:border-pink-500"
                />
                <span className="bg-pink-200 text-pink-800 px-3 py-2 rounded-lg font-medium">%</span>
              </div>
            </div>
          </div>

          <div className="bg-purple-50 rounded-xl p-4 border border-purple-100">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Label className="text-purple-800 font-medium">Bonus bet retention</Label>
                <button className="text-purple-400 hover:text-purple-600">
                  <HelpCircle className="w-4 h-4" />
                </button>
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  min="0"
                  max="100"
                  step="5"
                  value={bonusRetention}
                  onChange={(e) => setBonusRetention(parseFloat(e.target.value) || 0)}
                  className="w-20 px-3 py-2 border border-purple-200 rounded-lg text-center font-semibold focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
                />
                <span className="bg-purple-200 text-purple-800 px-3 py-2 rounded-lg font-medium">%</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Leg Entries */}
      <div className="space-y-3">
        {legs.map((leg, index) => (
          <div
            key={leg.id}
            className="bg-white rounded-xl border border-gray-200 p-4 flex items-center justify-between"
          >
            <span className="font-medium text-gray-700">Leg {index + 1}</span>
            <div className="flex items-center gap-3">
              <input
                type="text"
                inputMode="decimal"
                value={leg.oddsStr}
                onChange={(e) => updateLegOdds(leg.id, e.target.value)}
                className="w-24 px-3 py-2 border border-gray-200 rounded-lg text-center font-semibold focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
              {legs.length > 1 && (
                <button
                  onClick={() => removeLeg(leg.id)}
                  className="p-2 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
                >
                  <Trash2 className="w-5 h-5" />
                </button>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Add Leg Button */}
      <button
        onClick={addLeg}
        className="w-full py-3 border-2 border-dashed border-gray-300 rounded-xl text-gray-600 font-medium hover:border-blue-400 hover:text-blue-600 hover:bg-blue-50 transition-colors flex items-center justify-center gap-2"
      >
        <Plus className="w-5 h-5" />
        Add Leg
      </button>

      {/* Results Table */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              <th className="text-left py-3 px-4 font-medium text-gray-700">Outcome</th>
              <th className="text-right py-3 px-4 font-medium text-gray-700">Probability</th>
              <th className="text-right py-3 px-4 font-medium text-gray-700">Profit/Loss</th>
            </tr>
          </thead>
          <tbody>
            {result.outcomes.map((outcome, index) => (
              <tr key={index} className="border-b border-gray-100 last:border-0">
                <td className="py-3 px-4 font-medium">{outcome.name}</td>
                <td className="text-right py-3 px-4 text-blue-600 font-semibold">
                  {formatPercentage(outcome.probability, false)}
                </td>
                <td className={`text-right py-3 px-4 font-bold ${
                  outcome.profitLoss >= 0 ? 'text-green-600' : 'text-red-600'
                }`}>
                  {outcome.profitLoss >= 0 ? '+' : ''}{formatCurrency(outcome.profitLoss)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Total EV */}
      <div className={`rounded-xl p-4 border ${
        result.expectedValue >= 0
          ? 'bg-green-50 border-green-200'
          : 'bg-red-50 border-red-200'
      }`}>
        <div className="flex items-center justify-between">
          <span className={`font-medium ${
            result.expectedValue >= 0 ? 'text-green-800' : 'text-red-800'
          }`}>
            Total EV
          </span>
          <span className={`text-xl font-bold ${
            result.expectedValue >= 0 ? 'text-green-600' : 'text-red-600'
          }`}>
            {formatCurrency(result.expectedValue)}
          </span>
        </div>
      </div>

      {/* Long Term EV Link */}
      <a
        href="/calculators/ev"
        className="block w-full py-3 px-4 bg-emerald-500 hover:bg-emerald-600 text-white rounded-xl font-medium text-center transition-colors flex items-center justify-center gap-2"
      >
        <span className="text-lg">📈</span>
        Estimate Long-Term EV
        <span className="ml-auto">→</span>
      </a>

      {/* Info Box */}
      <div className="bg-blue-50 border border-blue-200 rounded-xl p-4">
        <div className="flex gap-3">
          <Info className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
          <div className="text-sm text-blue-800">
            <strong>Multi Calculator</strong> estimates expected value (EV) for multi-leg bets.
            <ul className="mt-2 space-y-1 list-disc list-inside text-blue-700">
              <li><strong>Any leg fail:</strong> Promo where 1 losing leg = bonus refund</li>
              <li><strong>SGM:</strong> Same Game Multi (legs from same match)</li>
              <li><strong>Overround:</strong> Bookmaker margin to account for</li>
              <li><strong>Retention:</strong> Expected value of bonus bets (~70%)</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}

export default function MultiCalculatorPage() {
  return (
    <PremiumLock feature="multi">
      <MultiCalculatorContent />
    </PremiumLock>
  )
}
