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
        <h1 className="text-3xl font-bold text-gray-900">Back/Lay</h1>
        <p className="text-gray-600 mt-2">Calculate lay stakes for matched betting</p>
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

      {/* Bet Type Toggle */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="grid grid-cols-2">
          <button
            onClick={() => setBetType('normal')}
            className={`py-3 px-4 text-center font-medium transition-colors ${
              betType === 'normal'
                ? 'bg-white text-gray-900 border-b-2 border-blue-600'
                : 'bg-gray-50 text-gray-500 hover:bg-gray-100'
            }`}
          >
            Normal
          </button>
          <button
            onClick={() => setBetType('bonus')}
            className={`py-3 px-4 text-center font-medium transition-colors ${
              betType === 'bonus'
                ? 'bg-white text-gray-900 border-b-2 border-blue-600'
                : 'bg-gray-50 text-gray-500 hover:bg-gray-100'
            }`}
          >
            Bonus
          </button>
        </div>
      </div>

      {/* Commission (Advanced) */}
      {showAdvanced && (
        <div className="bg-pink-50 rounded-xl p-4 border border-pink-100">
          <div className="flex items-center justify-between">
            <Label className="text-pink-800 font-medium">Commission</Label>
            <div className="flex items-center gap-2">
              <input
                type="text"
                inputMode="decimal"
                value={commissionStr}
                onChange={(e) => setCommissionStr(e.target.value)}
                className="w-20 px-3 py-2 border border-pink-200 rounded-lg text-center font-semibold focus:ring-2 focus:ring-pink-500 focus:border-pink-500"
              />
              <span className="bg-pink-200 text-pink-800 px-3 py-2 rounded-lg font-medium">%</span>
            </div>
          </div>
        </div>
      )}

      {/* Input Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Bookie Card */}
        <div className="bg-blue-50 border border-blue-100 rounded-xl p-5">
          <h3 className="text-blue-800 font-semibold mb-4">Bookie</h3>
          <div className="space-y-4">
            <div>
              <Label className="text-sm text-gray-600">Odds</Label>
              <input
                type="text"
                inputMode="decimal"
                value={backOddsStr}
                onChange={(e) => setBackOddsStr(e.target.value)}
                className="w-full mt-1 px-4 py-3 border border-blue-200 rounded-lg text-lg font-semibold focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>
            <div>
              <Label className="text-sm text-gray-600">Stake</Label>
              <input
                type="text"
                inputMode="decimal"
                value={backStakeStr}
                onChange={(e) => setBackStakeStr(e.target.value)}
                className="w-full mt-1 px-4 py-3 border border-blue-200 rounded-lg text-lg font-semibold focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>
          </div>
        </div>

        {/* Betfair Card */}
        <div className="bg-rose-50 border border-rose-100 rounded-xl p-5">
          <h3 className="text-rose-800 font-semibold mb-4">Betfair</h3>
          <div className="space-y-4">
            <div>
              <Label className="text-sm text-gray-600">Odds</Label>
              <input
                type="text"
                inputMode="decimal"
                value={layOddsStr}
                onChange={(e) => setLayOddsStr(e.target.value)}
                className="w-full mt-1 px-4 py-3 border border-rose-200 rounded-lg text-lg font-semibold focus:ring-2 focus:ring-rose-500 focus:border-rose-500"
              />
            </div>
            <div className="bg-white border border-rose-200 rounded-lg p-4">
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-sm text-gray-500">Stake</div>
                  <div className="text-2xl font-bold text-rose-800">
                    {formatCurrency(result.layStake)}
                  </div>
                </div>
                <button
                  onClick={copyLayStake}
                  className="p-2 bg-rose-100 hover:bg-rose-200 rounded-lg transition-colors"
                  title="Copy lay stake"
                >
                  {copiedStake ? (
                    <Check className="w-5 h-5 text-green-600" />
                  ) : (
                    <Copy className="w-5 h-5 text-rose-600" />
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
          ? 'bg-green-50 border-green-200'
          : 'bg-red-50 border-red-200'
      }`}>
        <div className="flex items-center justify-between">
          <span className={`font-medium ${
            result.qualifyingLoss >= 0 ? 'text-green-800' : 'text-red-800'
          }`}>
            {result.qualifyingLoss >= 0 ? 'Profit' : 'Loss'}
          </span>
          <span className={`text-xl font-bold ${
            result.qualifyingLoss >= 0 ? 'text-green-600' : 'text-red-600'
          }`}>
            {formatCurrency(Math.abs(result.qualifyingLoss))}
          </span>
        </div>
      </div>

      {/* Scenario Table */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              <th className="text-left py-3 px-4 font-medium text-gray-700">Winner</th>
              <th className="text-right py-3 px-4 font-medium text-gray-700">Bookie</th>
              <th className="text-right py-3 px-4 font-medium text-gray-700">Betfair</th>
              <th className="text-right py-3 px-4 font-medium text-gray-700">Avail</th>
            </tr>
          </thead>
          <tbody>
            <tr className="border-b border-gray-100">
              <td className="py-3 px-4 font-medium">Bookie</td>
              <td className="text-right py-3 px-4 text-green-600 font-semibold">
                +{formatCurrency(betType === 'bonus'
                  ? backStake * (backOdds - 1)
                  : backStake * (backOdds - 1)
                )}
              </td>
              <td className="text-right py-3 px-4 text-red-600 font-semibold">
                -{formatCurrency(result.layLiability)}
              </td>
              <td className={`text-right py-3 px-4 font-bold ${
                result.profitIfBackWins >= 0 ? 'text-green-600' : 'text-red-600'
              }`}>
                {formatCurrency(result.profitIfBackWins)}
              </td>
            </tr>
            <tr>
              <td className="py-3 px-4 font-medium">Betfair</td>
              <td className="text-right py-3 px-4 text-red-600 font-semibold">
                {betType === 'bonus' ? formatCurrency(0) : `-${formatCurrency(backStake)}`}
              </td>
              <td className="text-right py-3 px-4 text-green-600 font-semibold">
                +{formatCurrency(result.layStake * (1 - commission / 100))}
              </td>
              <td className={`text-right py-3 px-4 font-bold ${
                result.profitIfLayWins >= 0 ? 'text-green-600' : 'text-red-600'
              }`}>
                {formatCurrency(result.profitIfLayWins)}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      {/* Info Box */}
      {betType === 'normal' && result.qualifyingLoss < 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
          <div className="flex gap-3">
            <Info className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
            <div className="text-sm text-amber-800">
              <strong>Qualifying Loss:</strong> This small loss unlocks bonus bets worth much more.
              A {formatPercentage(result.pnlPercentage)} qualifying loss is normal for matched betting.
            </div>
          </div>
        </div>
      )}

      {betType === 'bonus' && (
        <div className="bg-green-50 border border-green-200 rounded-xl p-4">
          <div className="flex gap-3">
            <Info className="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" />
            <div className="text-sm text-green-800">
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
