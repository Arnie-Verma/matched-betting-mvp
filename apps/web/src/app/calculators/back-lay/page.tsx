'use client'

import { useState, useEffect } from 'react'
import { Copy, Check, Settings, Info } from 'lucide-react'
import { calculateBackLay, formatCurrency, formatPercentage } from '@/lib/calculators/calculations'
import { Label } from '@/components/ui/label'

// Helper to parse numeric input
const parseNumericInput = (value: string, fallback: number = 0): number => {
  if (value === '' || value === '-') return fallback
  const parsed = parseFloat(value)
  return isNaN(parsed) ? fallback : parsed
}

export default function BackLayCalculatorPage() {
  // Input state - use strings for controlled inputs
  const [backOddsStr, setBackOddsStr] = useState<string>('2')
  const [backStakeStr, setBackStakeStr] = useState<string>('100')
  const [layOddsStr, setLayOddsStr] = useState<string>('2')
  const [commissionStr, setCommissionStr] = useState<string>('6')
  const [betType, setBetType] = useState<'normal' | 'bonus'>('normal')
  const [showAdvanced, setShowAdvanced] = useState<boolean>(false)

  // Parsed numeric values
  const backOdds = parseNumericInput(backOddsStr, 1.01)
  const backStake = parseNumericInput(backStakeStr, 0)
  const layOdds = parseNumericInput(layOddsStr, 1.01)
  const commission = parseNumericInput(commissionStr, 0)

  // Calculated results
  const [result, setResult] = useState(() =>
    calculateBackLay(100, 2, 2, 0.06, false)
  )

  // Copy state
  const [copiedStake, setCopiedStake] = useState(false)

  // Recalculate when inputs change
  useEffect(() => {
    const commissionDecimal = commission / 100
    const newResult = calculateBackLay(
      backStake,
      backOdds,
      layOdds,
      commissionDecimal,
      betType === 'bonus'
    )
    setResult(newResult)
  }, [backStake, backOdds, layOdds, commission, betType])

  const copyLayStake = async () => {
    try {
      await navigator.clipboard.writeText(result.layStake.toFixed(2))
      setCopiedStake(true)
      setTimeout(() => setCopiedStake(false), 2000)
    } catch (err) {
      console.error('Failed to copy:', err)
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="text-center">
        <h1 className="text-3xl font-bold text-foreground">Back/Lay</h1>
        <p className="text-muted-foreground mt-2">Calculate lay stakes for matched betting</p>
      </div>

      {/* Advanced Toggle */}
      <div className="flex justify-end">
        <button
          onClick={() => setShowAdvanced(!showAdvanced)}
          className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
            showAdvanced
              ? 'bg-secondary text-primary'
              : 'bg-muted text-muted-foreground hover:bg-muted/80'
          }`}
        >
          <Settings className="w-4 h-4" />
          Advanced
        </button>
      </div>

      {/* Bet Type Toggle */}
      <div className="bg-card rounded-xl border border-border overflow-hidden">
        <div className="grid grid-cols-2">
          <button
            onClick={() => setBetType('normal')}
            className={`py-3 px-4 text-center font-medium transition-colors ${
              betType === 'normal'
                ? 'bg-card text-foreground border-b-2 border-primary'
                : 'bg-muted text-muted-foreground hover:bg-muted'
            }`}
          >
            Normal
          </button>
          <button
            onClick={() => setBetType('bonus')}
            className={`py-3 px-4 text-center font-medium transition-colors ${
              betType === 'bonus'
                ? 'bg-card text-foreground border-b-2 border-primary'
                : 'bg-muted text-muted-foreground hover:bg-muted'
            }`}
          >
            Bonus
          </button>
        </div>
      </div>

      {/* Commission (Advanced) */}
      {showAdvanced && (
        <div className="bg-[var(--highlight-soft)] rounded-xl p-4 border border-[var(--highlight-border)]">
          <div className="flex items-center justify-between">
            <Label className="text-[var(--highlight)] font-medium">Commission</Label>
            <div className="flex items-center gap-2">
              <input
                type="text"
                inputMode="decimal"
                value={commissionStr}
                onChange={(e) => setCommissionStr(e.target.value)}
                className="w-20 px-3 py-2 border border-[var(--highlight-border)] rounded-lg text-center font-semibold focus:ring-2 focus:ring-[var(--highlight)]/30 focus:border-[var(--highlight)]"
              />
              <span className="bg-[var(--highlight-soft)] text-[var(--highlight)] px-3 py-2 rounded-lg font-medium">%</span>
            </div>
          </div>
        </div>
      )}

      {/* Input Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Bookie Card */}
        <div className="bg-secondary border border-[var(--accent-soft)] rounded-xl p-5">
          <h3 className="text-[var(--brand)] font-semibold mb-4">Bookie</h3>
          <div className="space-y-4">
            <div>
              <Label className="text-sm text-muted-foreground">Odds</Label>
              <input
                type="text"
                inputMode="decimal"
                value={backOddsStr}
                onChange={(e) => setBackOddsStr(e.target.value)}
                className="w-full mt-1 px-4 py-3 border border-input rounded-lg text-lg font-semibold focus:ring-2 focus:ring-primary/30 focus:border-primary"
              />
            </div>
            <div>
              <Label className="text-sm text-muted-foreground">Stake</Label>
              <input
                type="text"
                inputMode="decimal"
                value={backStakeStr}
                onChange={(e) => setBackStakeStr(e.target.value)}
                className="w-full mt-1 px-4 py-3 border border-input rounded-lg text-lg font-semibold focus:ring-2 focus:ring-primary/30 focus:border-primary"
              />
            </div>
          </div>
        </div>

        {/* Betfair Card */}
        <div className="bg-[var(--profit-soft)] border border-[var(--profit-border)] rounded-xl p-5">
          <h3 className="text-[var(--profit)] font-semibold mb-4">Betfair</h3>
          <div className="space-y-4">
            <div>
              <Label className="text-sm text-muted-foreground">Odds</Label>
              <input
                type="text"
                inputMode="decimal"
                value={layOddsStr}
                onChange={(e) => setLayOddsStr(e.target.value)}
                className="w-full mt-1 px-4 py-3 border border-[var(--profit-border)] rounded-lg text-lg font-semibold focus:ring-2 focus:ring-[var(--profit)]/30 focus:border-[var(--profit)]"
              />
            </div>
            <div className="bg-card border border-[var(--profit-border)] rounded-lg p-4">
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-sm text-muted-foreground">Stake</div>
                  <div className="text-2xl font-bold text-[var(--profit)]">
                    {formatCurrency(result.layStake)}
                  </div>
                </div>
                <button
                  onClick={copyLayStake}
                  className="p-2 bg-[var(--profit-soft)] hover:bg-[var(--profit-border)] rounded-lg transition-colors"
                  title="Copy lay stake"
                >
                  {copiedStake ? (
                    <Check className="w-5 h-5 text-[var(--profit)]" />
                  ) : (
                    <Copy className="w-5 h-5 text-[var(--profit)]" />
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Result Summary */}
      <div className={`rounded-xl p-4 border ${
        result.qualifyingLoss >= 0
          ? 'bg-[var(--profit-soft)] border-[var(--profit-border)]'
          : 'bg-[var(--danger-soft)] border-[var(--danger-border)]'
      }`}>
        <div className="flex items-center justify-between">
          <span className={`font-medium ${
            result.qualifyingLoss >= 0 ? 'text-[var(--profit)]' : 'text-destructive'
          }`}>
            {result.qualifyingLoss >= 0 ? 'Profit' : 'Loss'}
          </span>
          <span className={`text-xl font-bold ${
            result.qualifyingLoss >= 0 ? 'text-[var(--profit)]' : 'text-destructive'
          }`}>
            {formatCurrency(Math.abs(result.qualifyingLoss))}
          </span>
        </div>
      </div>

      {/* Scenario Table */}
      <div className="bg-card rounded-xl border border-border overflow-hidden">
        <table className="w-full">
          <thead className="bg-muted border-b border-border">
            <tr>
              <th className="text-left py-3 px-4 font-medium text-foreground/80">Winner</th>
              <th className="text-right py-3 px-4 font-medium text-foreground/80">Bookie</th>
              <th className="text-right py-3 px-4 font-medium text-foreground/80">Betfair</th>
              <th className="text-right py-3 px-4 font-medium text-foreground/80">Avail</th>
            </tr>
          </thead>
          <tbody>
            <tr className="border-b border-border">
              <td className="py-3 px-4 font-medium">Bookie</td>
              <td className="text-right py-3 px-4 text-[var(--profit)] font-semibold">
                +{formatCurrency(betType === 'bonus'
                  ? backStake * (backOdds - 1)
                  : backStake * (backOdds - 1)
                )}
              </td>
              <td className="text-right py-3 px-4 text-destructive font-semibold">
                -{formatCurrency(result.layLiability)}
              </td>
              <td className={`text-right py-3 px-4 font-bold ${
                result.profitIfBackWins >= 0 ? 'text-[var(--profit)]' : 'text-destructive'
              }`}>
                {formatCurrency(result.profitIfBackWins)}
              </td>
            </tr>
            <tr>
              <td className="py-3 px-4 font-medium">Betfair</td>
              <td className="text-right py-3 px-4 text-destructive font-semibold">
                {betType === 'bonus' ? formatCurrency(0) : `-${formatCurrency(backStake)}`}
              </td>
              <td className="text-right py-3 px-4 text-[var(--profit)] font-semibold">
                +{formatCurrency(result.layStake * (1 - commission / 100))}
              </td>
              <td className={`text-right py-3 px-4 font-bold ${
                result.profitIfLayWins >= 0 ? 'text-[var(--profit)]' : 'text-destructive'
              }`}>
                {formatCurrency(result.profitIfLayWins)}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      {/* Info Box */}
      {betType === 'normal' && result.qualifyingLoss < 0 && (
        <div className="bg-[var(--highlight-soft)] border border-[var(--highlight-border)] rounded-xl p-4">
          <div className="flex gap-3">
            <Info className="w-5 h-5 text-[var(--highlight)] flex-shrink-0 mt-0.5" />
            <div className="text-sm text-[var(--highlight)]">
              <strong>Qualifying Loss:</strong> This small loss unlocks bonus bets worth much more.
              A {formatPercentage(result.pnlPercentage)} qualifying loss is normal for matched betting.
            </div>
          </div>
        </div>
      )}

      {betType === 'bonus' && (
        <div className="bg-[var(--profit-soft)] border border-[var(--profit-border)] rounded-xl p-4">
          <div className="flex gap-3">
            <Info className="w-5 h-5 text-[var(--profit)] flex-shrink-0 mt-0.5" />
            <div className="text-sm text-[var(--profit)]">
              <strong>Bonus Bet:</strong> With a free bet, you keep an average of{' '}
              <strong>{formatCurrency(result.qualifyingLoss)}</strong> (
              {formatPercentage((result.qualifyingLoss / backStake) * 100)} of face value) regardless of outcome.
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
