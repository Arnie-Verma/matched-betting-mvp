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
        <h1 className="text-3xl font-bold text-foreground">Multi Calculator</h1>
        <p className="text-muted-foreground mt-2">Calculate expected value for multi-leg bets</p>
      </div>

      {/* Advanced Toggle */}
      <div className="flex justify-end">
        <button
          onClick={() => setShowAdvanced(!showAdvanced)}
          className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
            showAdvanced
              ? 'bg-secondary text-primary/90'
              : 'bg-muted text-muted-foreground hover:bg-muted/80'
          }`}
        >
          <Settings className="w-4 h-4" />
          Advanced
        </button>
      </div>

      {/* Promo Options */}
      <div className="bg-card rounded-xl border border-border p-4 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="font-medium text-foreground/80">Any leg fail</span>
            <button className="text-muted-foreground/60 hover:text-muted-foreground">
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
            <div className="w-11 h-6 bg-muted/80 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary/20 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-card after:border-input after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary"></div>
          </label>
        </div>

        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="font-medium text-foreground/80">Is SGM</span>
            <button className="text-muted-foreground/60 hover:text-muted-foreground">
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
            <div className="w-11 h-6 bg-muted/80 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary/20 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-card after:border-input after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary"></div>
          </label>
        </div>
      </div>

      {/* Stake Input */}
      <div className="bg-secondary rounded-xl p-4 border border-[var(--accent-soft)]">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Label className="text-[var(--brand)] font-medium">Stake</Label>
            <button className="text-primary/70 hover:text-primary">
              <HelpCircle className="w-4 h-4" />
            </button>
          </div>
          <input
            type="text"
            inputMode="decimal"
            value={stakeStr}
            onChange={(e) => setStakeStr(e.target.value)}
            className="w-32 px-3 py-2 border border-input rounded-lg text-center font-semibold focus:ring-2 focus:ring-primary/30 focus:border-primary"
          />
        </div>
      </div>

      {/* Advanced Options */}
      {showAdvanced && (
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-[var(--highlight-soft)] rounded-xl p-4 border border-[var(--highlight-border)]">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Label className="text-[var(--highlight)] font-medium">Overround</Label>
                <button className="text-[var(--highlight)] hover:text-[var(--highlight)]">
                  <HelpCircle className="w-4 h-4" />
                </button>
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  inputMode="decimal"
                  value={overroundStr}
                  onChange={(e) => setOverroundStr(e.target.value)}
                  className="w-20 px-3 py-2 border border-[var(--highlight-border)] rounded-lg text-center font-semibold focus:ring-2 focus:ring-[var(--highlight)]/30 focus:border-[var(--highlight)]"
                />
                <span className="bg-[var(--highlight-soft)] text-[var(--highlight)] px-3 py-2 rounded-lg font-medium">%</span>
              </div>
            </div>
          </div>

          <div className="bg-[var(--accent-soft)] rounded-xl p-4 border border-[var(--accent-soft)]">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Label className="text-[var(--brand)] font-medium">Bonus bet retention</Label>
                <button className="text-[var(--brand)] hover:text-[var(--brand)]">
                  <HelpCircle className="w-4 h-4" />
                </button>
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  inputMode="decimal"
                  value={bonusRetentionStr}
                  onChange={(e) => setBonusRetentionStr(e.target.value)}
                  className="w-20 px-3 py-2 border border-[var(--accent-soft)] rounded-lg text-center font-semibold focus:ring-2 focus:ring-primary/30 focus:border-primary"
                />
                <span className="bg-[var(--accent-soft)] text-[var(--brand)] px-3 py-2 rounded-lg font-medium">%</span>
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
            className="bg-card rounded-xl border border-border p-4 flex items-center justify-between"
          >
            <span className="font-medium text-foreground/80">Leg {index + 1}</span>
            <div className="flex items-center gap-3">
              <input
                type="text"
                inputMode="decimal"
                value={leg.oddsStr}
                onChange={(e) => updateLegOdds(leg.id, e.target.value)}
                className="w-24 px-3 py-2 border border-border rounded-lg text-center font-semibold focus:ring-2 focus:ring-primary/30 focus:border-primary"
              />
              {legs.length > 1 && (
                <button
                  onClick={() => removeLeg(leg.id)}
                  className="p-2 text-muted-foreground/60 hover:text-destructive hover:bg-[var(--danger-soft)] rounded-lg transition-colors"
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
        className="w-full py-3 border-2 border-dashed border-input rounded-xl text-muted-foreground font-medium hover:border-primary hover:text-primary hover:bg-secondary transition-colors flex items-center justify-center gap-2"
      >
        <Plus className="w-5 h-5" />
        Add Leg
      </button>

      {/* Results Table */}
      <div className="bg-card rounded-xl border border-border overflow-hidden">
        <table className="w-full">
          <thead className="bg-muted border-b border-border">
            <tr>
              <th className="text-left py-3 px-4 font-medium text-foreground/80">Outcome</th>
              <th className="text-right py-3 px-4 font-medium text-foreground/80">Probability</th>
              <th className="text-right py-3 px-4 font-medium text-foreground/80">Profit/Loss</th>
            </tr>
          </thead>
          <tbody>
            {result.outcomes.map((outcome, index) => (
              <tr key={index} className="border-b border-border last:border-0">
                <td className="py-3 px-4 font-medium">{outcome.name}</td>
                <td className="text-right py-3 px-4 text-primary font-semibold">
                  {formatPercentage(outcome.probability, false)}
                </td>
                <td className={`text-right py-3 px-4 font-bold ${
                  outcome.profitLoss >= 0 ? 'text-[var(--profit)]' : 'text-destructive'
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
          ? 'bg-[var(--profit-soft)] border-[var(--profit-border)]'
          : 'bg-[var(--danger-soft)] border-[var(--danger-border)]'
      }`}>
        <div className="flex items-center justify-between">
          <span className={`font-medium ${
            result.expectedValue >= 0 ? 'text-[var(--profit)]' : 'text-destructive'
          }`}>
            Total EV
          </span>
          <span className={`text-xl font-bold ${
            result.expectedValue >= 0 ? 'text-[var(--profit)]' : 'text-destructive'
          }`}>
            {formatCurrency(result.expectedValue)}
          </span>
        </div>
      </div>

      {/* Long Term EV Link */}
      <a
        href="/calculators/ev"
        className="block w-full py-3 px-4 bg-[var(--profit)] hover:bg-[var(--profit)]/90 text-white rounded-xl font-medium text-center transition-colors flex items-center justify-center gap-2"
      >
        <span className="text-lg">📈</span>
        Estimate Long-Term EV
        <span className="ml-auto">→</span>
      </a>

      {/* Info Box */}
      <div className="bg-secondary border border-input rounded-xl p-4">
        <div className="flex gap-3">
          <Info className="w-5 h-5 text-primary flex-shrink-0 mt-0.5" />
          <div className="text-sm text-[var(--brand)]">
            <strong>Multi Calculator</strong> estimates expected value (EV) for multi-leg bets.
            <ul className="mt-2 space-y-1 list-disc list-inside text-primary/90">
              <li><strong>Any leg fail:</strong> Promo where any losing leg = bonus refund</li>
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
