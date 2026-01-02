'use client'

import { useState } from 'react'
import { Plus, Trash2, Info, Settings, HelpCircle, Play } from 'lucide-react'
import { calculateLongTermEV, formatCurrency, formatPercentage } from '@/lib/calculators/calculations'
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

function LongTermEVContent() {
  // Input state - use strings for controlled inputs
  const [numBetsStr, setNumBetsStr] = useState<string>('100')
  const [stakeStr, setStakeStr] = useState<string>('50')
  const [overroundStr, setOverroundStr] = useState<string>('5')
  const [bonusRetentionStr, setBonusRetentionStr] = useState<string>('70')
  const [anyLegFail, setAnyLegFail] = useState<boolean>(false)
  const [isSGM, setIsSGM] = useState<boolean>(false)
  const [showAdvanced, setShowAdvanced] = useState<boolean>(false)
  const [isSimulating, setIsSimulating] = useState<boolean>(false)
  const [legs, setLegs] = useState<LegEntry[]>([
    { id: 1, oddsStr: '1.5' }
  ])
  const [nextId, setNextId] = useState(2)

  // Parsed values
  const numBets = Math.max(1, Math.round(parseNumericInput(numBetsStr, 100)))
  const stake = parseNumericInput(stakeStr, 50)
  const overround = parseNumericInput(overroundStr, 5)
  const bonusRetention = parseNumericInput(bonusRetentionStr, 70)

  // Calculated results
  const [result, setResult] = useState<ReturnType<typeof calculateLongTermEV> | null>(null)

  const runSimulation = () => {
    setIsSimulating(true)

    // Use setTimeout to allow UI to update
    setTimeout(() => {
      const legData = legs.map(l => ({ odds: parseNumericInput(l.oddsStr, 1.5) }))
      const newResult = calculateLongTermEV(
        numBets,
        stake,
        legData,
        overround,
        bonusRetention,
        anyLegFail,
        isSGM,
        1000 // 1000 Monte Carlo simulations
      )
      setResult(newResult)
      setIsSimulating(false)
    }, 100)
  }

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
        <h1 className="text-3xl font-bold text-foreground">Long Term EV Calculator</h1>
        <p className="text-muted-foreground mt-2">Simulate expected value over many bets</p>
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

      {/* Number of Bets */}
      <div className="bg-secondary rounded-xl p-4 border border-[var(--accent-soft)]">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Label className="text-[var(--brand)] font-medium">Number of bets</Label>
            <button className="text-primary/70 hover:text-primary">
              <HelpCircle className="w-4 h-4" />
            </button>
          </div>
          <input
            type="text"
            inputMode="numeric"
            value={numBetsStr}
            onChange={(e) => setNumBetsStr(e.target.value)}
            className="w-32 px-3 py-2 border border-input rounded-lg text-center font-semibold focus:ring-2 focus:ring-primary/30 focus:border-primary"
          />
        </div>
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
      <div className="bg-[var(--accent-soft)] rounded-xl p-4 border border-[var(--accent-soft)]">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Label className="text-[var(--brand)] font-medium">Stake</Label>
            <button className="text-[var(--brand)] hover:text-[var(--brand)]">
              <HelpCircle className="w-4 h-4" />
            </button>
          </div>
          <input
            type="text"
            inputMode="decimal"
            value={stakeStr}
            onChange={(e) => setStakeStr(e.target.value)}
            className="w-32 px-3 py-2 border border-[var(--accent-soft)] rounded-lg text-center font-semibold focus:ring-2 focus:ring-primary/30 focus:border-primary"
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

          <div className="bg-[var(--highlight-soft)] rounded-xl p-4 border border-[var(--highlight-border)]">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Label className="text-[var(--highlight)] font-medium">Bonus bet retention</Label>
                <button className="text-[var(--highlight)] hover:text-[var(--highlight)]">
                  <HelpCircle className="w-4 h-4" />
                </button>
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  inputMode="decimal"
                  value={bonusRetentionStr}
                  onChange={(e) => setBonusRetentionStr(e.target.value)}
                  className="w-20 px-3 py-2 border border-[var(--highlight-border)] rounded-lg text-center font-semibold focus:ring-2 focus:ring-[var(--highlight)]/30 focus:border-[var(--highlight)]"
                />
                <span className="bg-[var(--highlight-soft)] text-[var(--highlight)] px-3 py-2 rounded-lg font-medium">%</span>
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

      {/* Simulate Button */}
      <button
        onClick={runSimulation}
        disabled={isSimulating}
        className="w-full py-4 bg-primary hover:bg-primary/90 disabled:bg-primary/60 text-white rounded-xl font-medium text-lg transition-colors flex items-center justify-center gap-2"
      >
        {isSimulating ? (
          <>
            <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
            Simulating...
          </>
        ) : (
          <>
            <Play className="w-5 h-5" />
            Simulate EV
          </>
        )}
      </button>

      {/* Results */}
      {result && (
        <>
          {/* Summary Stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-card rounded-xl border border-border p-4 text-center">
              <div className="text-sm text-muted-foreground">Expected Profit</div>
              <div className={`text-xl font-bold ${
                result.expectedProfit >= 0 ? 'text-[var(--profit)]' : 'text-destructive'
              }`}>
                {formatCurrency(result.expectedProfit)}
              </div>
            </div>
            <div className="bg-card rounded-xl border border-border p-4 text-center">
              <div className="text-sm text-muted-foreground">Per Bet</div>
              <div className={`text-xl font-bold ${
                result.expectedProfitPerBet >= 0 ? 'text-[var(--profit)]' : 'text-destructive'
              }`}>
                {formatCurrency(result.expectedProfitPerBet)}
              </div>
            </div>
            <div className="bg-card rounded-xl border border-border p-4 text-center">
              <div className="text-sm text-muted-foreground">Std Deviation</div>
              <div className="text-xl font-bold text-foreground">
                {formatCurrency(result.standardDeviation)}
              </div>
            </div>
            <div className="bg-card rounded-xl border border-border p-4 text-center">
              <div className="text-sm text-muted-foreground">Profit Probability</div>
              <div className={`text-xl font-bold ${
                result.probabilityOfProfit >= 50 ? 'text-[var(--profit)]' : 'text-[var(--highlight)]'
              }`}>
                {formatPercentage(result.probabilityOfProfit, false)}
              </div>
            </div>
          </div>

          {/* Range */}
          <div className="bg-muted rounded-xl border border-border p-4">
            <div className="text-sm text-muted-foreground mb-2">90% Confidence Interval</div>
            <div className="flex items-center justify-between">
              <div>
                <span className="text-sm text-muted-foreground">Worst (5%)</span>
                <div className={`text-lg font-bold ${
                  result.worstCase >= 0 ? 'text-[var(--profit)]' : 'text-destructive'
                }`}>
                  {formatCurrency(result.worstCase)}
                </div>
              </div>
              <div className="flex-1 mx-4 h-2 bg-gradient-to-r from-[var(--danger-soft)] via-[var(--highlight-soft)] to-[var(--profit-soft)] rounded-full"></div>
              <div className="text-right">
                <span className="text-sm text-muted-foreground">Best (95%)</span>
                <div className="text-lg font-bold text-[var(--profit)]">
                  {formatCurrency(result.bestCase)}
                </div>
              </div>
            </div>
          </div>
        </>
      )}

      {/* Info Box */}
      <div className="bg-secondary border border-input rounded-xl p-4">
        <div className="flex gap-3">
          <Info className="w-5 h-5 text-primary flex-shrink-0 mt-0.5" />
          <div className="text-sm text-[var(--brand)]">
            <strong>Long-Term EV</strong> uses Monte Carlo simulation to estimate outcomes over many bets.
            <ul className="mt-2 space-y-1 list-disc list-inside text-primary/90">
              <li>Results based on 1,000 simulated scenarios</li>
              <li>Standard deviation shows variance/risk</li>
              <li>90% confidence interval shows likely outcome range</li>
              <li>Higher number of bets = more predictable results</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}

export default function LongTermEVPage() {
  return (
    <PremiumLock feature="long_term_ev">
      <LongTermEVContent />
    </PremiumLock>
  )
}
