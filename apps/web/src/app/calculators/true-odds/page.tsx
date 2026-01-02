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
        <h1 className="text-3xl font-bold text-foreground">True Odds Calculator</h1>
        <p className="text-muted-foreground mt-2">Remove bookmaker margin to find fair odds</p>
      </div>

      {/* Outcome Entries */}
      <div className="space-y-3">
        {entries.map((entry, index) => (
          <div
            key={entry.id}
            className="bg-card rounded-xl border border-border p-4 flex items-center gap-4"
          >
            <div className="flex-1">
              <Label className="text-sm text-muted-foreground">Outcome {index + 1}</Label>
              <input
                type="text"
                inputMode="decimal"
                value={entry.oddsStr}
                onChange={(e) => updateOdds(entry.id, e.target.value)}
                className="w-full mt-1 px-4 py-3 border border-border rounded-lg text-lg font-semibold focus:ring-2 focus:ring-primary/30 focus:border-primary"
              />
            </div>
            {entries.length > 2 && (
              <button
                onClick={() => removeOutcome(entry.id)}
                className="p-2 text-muted-foreground/60 hover:text-destructive hover:bg-[var(--danger-soft)] rounded-lg transition-colors mt-6"
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
        className="w-full py-3 border-2 border-dashed border-input rounded-xl text-muted-foreground font-medium hover:border-primary hover:text-primary hover:bg-secondary transition-colors flex items-center justify-center gap-2"
      >
        <Plus className="w-5 h-5" />
        Add Outcome
      </button>

      {/* Results Table */}
      <div className="bg-card rounded-xl border border-border overflow-hidden">
        <table className="w-full">
          <thead className="bg-muted border-b border-border">
            <tr>
              <th className="text-left py-3 px-4 font-medium text-foreground/80">Outcome</th>
              <th className="text-right py-3 px-4 font-medium text-foreground/80">True Odds</th>
            </tr>
          </thead>
          <tbody>
            {result.trueOdds.map((trueOdd, index) => (
              <tr key={index} className="border-b border-border last:border-0">
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
          ? 'bg-[var(--profit-soft)] border-[var(--profit-border)]'
          : displayOverround <= 5
          ? 'bg-[var(--highlight-soft)] border-[var(--highlight-border)]'
          : 'bg-[var(--danger-soft)] border-[var(--danger-border)]'
      }`}>
        <div className="flex items-center justify-between">
          <span className={`font-medium ${
            isUnderround ? 'text-[var(--profit)]' :
            displayOverround <= 5 ? 'text-[var(--highlight)]' : 'text-destructive'
          }`}>
            Average Overround
          </span>
          <span className={`text-xl font-bold ${
            isUnderround ? 'text-[var(--profit)]' :
            displayOverround <= 5 ? 'text-[var(--highlight)]' : 'text-destructive'
          }`}>
            {formatPercentage(displayOverround, false)}
          </span>
        </div>
      </div>

      {/* Info Box */}
      <div className="bg-secondary border border-[var(--accent-soft)] rounded-xl p-4">
        <div className="flex gap-3">
          <Info className="w-5 h-5 text-primary flex-shrink-0 mt-0.5" />
          <div className="text-sm text-[var(--brand)]">
            <strong>True Odds</strong> are fair odds after removing the bookmaker&apos;s margin.
            {isUnderround ? (
              <span className="block mt-1 text-[var(--profit)]">
                <strong>Under-round detected!</strong> This could indicate missing outcomes or arbitrage potential.
              </span>
            ) : (
              <span className="block mt-1">
                The overround ({formatPercentage(displayOverround, false)}) is the bookmaker&apos;s built-in profit margin.
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
