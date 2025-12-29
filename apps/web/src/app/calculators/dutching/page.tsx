'use client'

import { useState } from 'react'
import { Plus, Trash2, Info } from 'lucide-react'
import { formatCurrency } from '@/lib/calculators/calculations'
import { Label } from '@/components/ui/label'

// Helper to parse numeric input
const parseNumericInput = (value: string, fallback: number = 0): number => {
  if (value === '' || value === '-') return fallback
  const parsed = parseFloat(value)
  return isNaN(parsed) ? fallback : parsed
}

interface OutcomeEntry {
  id: number
  oddsStr: string
  stakeStr: string
}

interface DutchingResult {
  stakes: number[]
  totalStake: number
  commonReturn: number
  profit: number
  isGuaranteedProfit: boolean
  isValid: boolean
}

/**
 * Calculate dutching stakes using first outcome's stake as anchor.
 *
 * Math (Outmatched style):
 * - User enters stake for outcome 1 (s1) and odds for all outcomes
 * - Target return R = s1 * o1
 * - Each other stake: s_i = R / o_i
 * - Total stake S = sum of all stakes
 * - Profit = R - S (same for all outcomes)
 */
function calculateDutchingFromAnchor(
  anchorStake: number,
  odds: number[]
): DutchingResult {
  if (odds.length < 2 || odds.some(o => o < 1.01) || anchorStake <= 0) {
    return {
      stakes: [],
      totalStake: 0,
      commonReturn: 0,
      profit: 0,
      isGuaranteedProfit: false,
      isValid: false
    }
  }

  // Target return = anchor stake * anchor odds
  const R = anchorStake * odds[0]

  // Each stake = R / odds
  const rawStakes = odds.map(o => R / o)

  // Round to 2 decimals
  const stakes = rawStakes.map(s => Math.round(s * 100) / 100)

  // Total stake
  const totalStake = stakes.reduce((a, b) => a + b, 0)

  // Profit = Return - Total Stake
  const profit = R - totalStake

  // Guaranteed profit if sum(1/odds) < 1
  const D = odds.reduce((sum, o) => sum + (1 / o), 0)
  const isGuaranteedProfit = D < 1

  return {
    stakes,
    totalStake: Math.round(totalStake * 100) / 100,
    commonReturn: Math.round(R * 100) / 100,
    profit: Math.round(profit * 100) / 100,
    isGuaranteedProfit,
    isValid: true
  }
}

export default function DutchingCalculatorPage() {
  // Input state
  const [entries, setEntries] = useState<OutcomeEntry[]>([
    { id: 1, oddsStr: '3', stakeStr: '50' },
    { id: 2, oddsStr: '2', stakeStr: '' }
  ])
  const [nextId, setNextId] = useState(3)

  // Get anchor stake (first outcome)
  const anchorStake = parseNumericInput(entries[0]?.stakeStr || '0', 0)
  const odds = entries.map(e => parseNumericInput(e.oddsStr, 1.01))

  // Calculate result
  const result = calculateDutchingFromAnchor(anchorStake, odds)

  const addOutcome = () => {
    setEntries(prev => [
      ...prev,
      { id: nextId, oddsStr: '2', stakeStr: '' }
    ])
    setNextId(prev => prev + 1)
  }

  const removeOutcome = (id: number) => {
    if (entries.length <= 2) return
    setEntries(prev => prev.filter(e => e.id !== id))
  }

  const updateOdds = (id: number, oddsStr: string) => {
    setEntries(prev =>
      prev.map(e => e.id === id ? { ...e, oddsStr } : e)
    )
  }

  const updateStake = (id: number, stakeStr: string) => {
    // Only allow editing the first outcome's stake (anchor)
    const entry = entries.find(e => e.id === id)
    if (entry && entries.indexOf(entry) === 0) {
      setEntries(prev =>
        prev.map(e => e.id === id ? { ...e, stakeStr } : e)
      )
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="text-center">
        <h1 className="text-3xl font-bold text-gray-900">Dutching Calculator</h1>
        <p className="text-gray-600 mt-2">Split stakes across multiple outcomes for equal profit</p>
      </div>

      {/* Outcome Entries */}
      <div className="space-y-3">
        {entries.map((entry, index) => {
          const isAnchor = index === 0
          const calculatedStake = result.isValid ? result.stakes[index] : 0

          return (
            <div
              key={entry.id}
              className="bg-white rounded-xl border border-gray-200 p-4 flex items-center gap-4"
            >
              <div className="flex-1">
                <Label className="text-sm text-gray-600">Outcome {index + 1} Odds</Label>
                <input
                  type="text"
                  inputMode="decimal"
                  value={entry.oddsStr}
                  onChange={(e) => updateOdds(entry.id, e.target.value)}
                  className="w-full mt-1 px-4 py-3 border border-gray-200 rounded-lg text-lg font-semibold focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
              </div>
              <div className="flex-1">
                <Label className="text-sm text-gray-600">
                  Stake {isAnchor && <span className="text-blue-600">(enter)</span>}
                </Label>
                {isAnchor ? (
                  <input
                    type="text"
                    inputMode="decimal"
                    value={entry.stakeStr}
                    onChange={(e) => updateStake(entry.id, e.target.value)}
                    placeholder="Enter stake"
                    className="w-full mt-1 px-4 py-3 border border-blue-200 rounded-lg text-lg font-semibold focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-blue-50"
                  />
                ) : (
                  <div className="mt-1 px-4 py-3 bg-gray-50 border border-gray-200 rounded-lg text-lg font-semibold text-gray-700">
                    {result.isValid ? formatCurrency(calculatedStake) : '-'}
                  </div>
                )}
              </div>
              {entries.length > 2 && (
                <button
                  onClick={() => removeOutcome(entry.id)}
                  className="p-2 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors mt-6"
                >
                  <Trash2 className="w-5 h-5" />
                </button>
              )}
            </div>
          )
        })}
      </div>

      {/* Add Outcome Button */}
      <button
        onClick={addOutcome}
        className="w-full py-3 border-2 border-dashed border-gray-300 rounded-xl text-gray-600 font-medium hover:border-blue-400 hover:text-blue-600 hover:bg-blue-50 transition-colors flex items-center justify-center gap-2"
      >
        <Plus className="w-5 h-5" />
        Add Outcome
      </button>

      {/* Results Table */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              <th className="text-left py-3 px-4 font-medium text-gray-700">Outcome</th>
              <th className="text-right py-3 px-4 font-medium text-gray-700">Stake</th>
              <th className="text-right py-3 px-4 font-medium text-gray-700">Profit/Loss</th>
            </tr>
          </thead>
          <tbody>
            {result.isValid && entries.map((entry, index) => (
              <tr key={entry.id} className="border-b border-gray-100 last:border-0">
                <td className="py-3 px-4 font-medium">Outcome {index + 1}</td>
                <td className="text-right py-3 px-4 font-semibold">
                  {formatCurrency(result.stakes[index])}
                </td>
                <td className={`text-right py-3 px-4 font-bold ${
                  result.profit >= 0 ? 'text-green-600' : 'text-red-600'
                }`}>
                  {result.profit >= 0 ? '+' : ''}{formatCurrency(result.profit)}
                </td>
              </tr>
            ))}
            <tr className="bg-gray-50 border-t border-gray-200">
              <td className="py-3 px-4 font-bold text-gray-700">Total</td>
              <td className="text-right py-3 px-4 font-bold">
                {formatCurrency(result.totalStake)}
              </td>
              <td className={`text-right py-3 px-4 font-bold ${
                result.profit >= 0 ? 'text-green-600' : 'text-red-600'
              }`}>
                {result.profit >= 0 ? '+' : ''}{formatCurrency(result.profit)}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      {/* Profit/Loss Summary */}
      <div className={`rounded-xl p-4 border ${
        result.isGuaranteedProfit
          ? 'bg-green-50 border-green-200'
          : result.profit >= 0
          ? 'bg-green-50 border-green-200'
          : 'bg-red-50 border-red-200'
      }`}>
        <div className="flex items-center justify-between">
          <span className={`font-medium ${
            result.profit >= 0 ? 'text-green-800' : 'text-red-800'
          }`}>
            {result.isGuaranteedProfit ? 'Guaranteed Profit' : result.profit >= 0 ? 'Profit' : 'Loss'} (any outcome)
          </span>
          <span className={`text-xl font-bold ${
            result.profit >= 0 ? 'text-green-600' : 'text-red-600'
          }`}>
            {result.profit >= 0 ? '+' : ''}{formatCurrency(result.profit)}
          </span>
        </div>
      </div>

      {/* Info Box */}
      <div className="bg-blue-50 border border-blue-200 rounded-xl p-4">
        <div className="flex gap-3">
          <Info className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
          <div className="text-sm text-blue-800">
            <strong>Dutching</strong> distributes your stake across multiple outcomes so you get the same profit regardless of which outcome wins.
            Enter your stake for Outcome 1 and the calculator will determine the other stakes.
            {result.isGuaranteedProfit && (
              <span className="block mt-1 text-green-700">
                <strong>Arbitrage detected!</strong> These odds guarantee profit no matter which outcome wins.
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
