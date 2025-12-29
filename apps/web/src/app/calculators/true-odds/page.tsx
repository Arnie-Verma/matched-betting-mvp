'use client'

import { useState, useEffect } from 'react'
import { Plus, Trash2, Info } from 'lucide-react'
import { calculateTrueOdds, formatPercentage } from '@/lib/calculators/calculations'
import { Label } from '@/components/ui/label'

// Helper to parse numeric input
const parseNumericInput = (value: string, fallback: number = 0): number => {
  if (value === '' || value === '-') return fallback
  const parsed = parseFloat(value)
  return isNaN(parsed) ? fallback : parsed
}

interface OddsEntry {
  id: number
  oddsStr: string
}

export default function TrueOddsCalculatorPage() {
  // Input state - use strings for controlled inputs
  const [entries, setEntries] = useState<OddsEntry[]>([
    { id: 1, oddsStr: '2' },
    { id: 2, oddsStr: '2' }
  ])
  const [nextId, setNextId] = useState(3)

  // Calculated results
  const [result, setResult] = useState(() =>
    calculateTrueOdds([2, 2])
  )

  // Recalculate when inputs change
  useEffect(() => {
    const odds = entries.map(e => parseNumericInput(e.oddsStr, 1.01))
    const newResult = calculateTrueOdds(odds)
    setResult(newResult)
  }, [entries.map(e => e.oddsStr).join(',')])

  const addOutcome = () => {
    setEntries(prev => [
      ...prev,
      { id: nextId, oddsStr: '2' }
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

  // Display overround as absolute value (matching Outmatched style)
  const displayOverround = Math.abs(result.overround)
  const isUnderround = result.overround < 0

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="text-center">
        <h1 className="text-3xl font-bold text-gray-900">True Odds Calculator</h1>
        <p className="text-gray-600 mt-2">Remove bookmaker margin to find fair odds</p>
      </div>

      {/* Outcome Entries */}
      <div className="space-y-3">
        {entries.map((entry, index) => (
          <div
            key={entry.id}
            className="bg-white rounded-xl border border-gray-200 p-4 flex items-center gap-4"
          >
            <div className="flex-1">
              <Label className="text-sm text-gray-600">Outcome {index + 1}</Label>
              <input
                type="text"
                inputMode="decimal"
                value={entry.oddsStr}
                onChange={(e) => updateOdds(entry.id, e.target.value)}
                className="w-full mt-1 px-4 py-3 border border-gray-200 rounded-lg text-lg font-semibold focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
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
        ))}
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
              <th className="text-right py-3 px-4 font-medium text-gray-700">True Odds</th>
            </tr>
          </thead>
          <tbody>
            {result.trueOdds.map((trueOdd, index) => (
              <tr key={index} className="border-b border-gray-100 last:border-0">
                <td className="py-3 px-4 font-medium">Odd {index + 1}</td>
                <td className="text-right py-3 px-4 font-semibold">
                  {trueOdd.toFixed(2)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Overround Info */}
      <div className={`rounded-xl p-4 border ${
        isUnderround
          ? 'bg-green-50 border-green-200'
          : displayOverround <= 5
          ? 'bg-amber-50 border-amber-200'
          : 'bg-red-50 border-red-200'
      }`}>
        <div className="flex items-center justify-between">
          <span className={`font-medium ${
            isUnderround ? 'text-green-800' :
            displayOverround <= 5 ? 'text-amber-800' : 'text-red-800'
          }`}>
            Average Overround
          </span>
          <span className={`text-xl font-bold ${
            isUnderround ? 'text-green-600' :
            displayOverround <= 5 ? 'text-amber-600' : 'text-red-600'
          }`}>
            {formatPercentage(displayOverround, false)}
          </span>
        </div>
      </div>

      {/* Info Box */}
      <div className="bg-blue-50 border border-blue-200 rounded-xl p-4">
        <div className="flex gap-3">
          <Info className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
          <div className="text-sm text-blue-800">
            <strong>True Odds</strong> are fair odds after removing the bookmaker's margin.
            {isUnderround ? (
              <span className="block mt-1 text-green-700">
                <strong>Under-round detected!</strong> This could indicate missing outcomes or arbitrage potential.
              </span>
            ) : (
              <span className="block mt-1">
                The overround ({formatPercentage(displayOverround, false)}) is the bookmaker's built-in profit margin.
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
