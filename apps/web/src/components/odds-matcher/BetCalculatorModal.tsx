'use client'

import { useState, useEffect } from 'react'
import { Calculator, Copy, Check, Settings, ExternalLink } from 'lucide-react'
import { OddsMatch } from './OddsMatcherClient'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'

interface BetCalculatorModalProps {
  odds: OddsMatch
  onClose: () => void
  onStakeChange?: (newStake: number) => void
}

interface CalculationResult {
  backStake: number
  layStake: number
  layLiability: number
  profitIfBackWins: number
  profitIfLayWins: number
  qualifyingLoss: number
  pnlPercentage: number
  rating: number
}

const BOOKMAKER_URLS: Record<string, string> = {
  tab: 'https://www.tab.com.au',
  ladbrokes: 'https://www.ladbrokes.com.au',
  neds: 'https://www.neds.com.au',
  betfair: 'https://www.betfair.com.au',
}

const getBookmakerUrl = (code: string) => {
  const key = (code || '').toLowerCase()
  return BOOKMAKER_URLS[key] || 'https://www.google.com/search?q=' + encodeURIComponent(code || 'betting site')
}

export function BetCalculatorModal({ odds, onClose, onStakeChange }: BetCalculatorModalProps) {
  // Editable values
  const [backStake, setBackStake] = useState(odds.back_stake)
  const [backOdds, setBackOdds] = useState(odds.back_odds)
  const [layOdds, setLayOdds] = useState(odds.lay_odds)
  const [commission, setCommission] = useState(odds.lay_commission)
  const [showAdvanced, setShowAdvanced] = useState(false)

  // Copy states
  const [copiedStake, setCopiedStake] = useState(false)
  const [copiedSummary, setCopiedSummary] = useState(false)

  // Calculated values
  const [calc, setCalc] = useState<CalculationResult>({
    backStake: odds.back_stake,
    layStake: odds.lay_stake,
    layLiability: odds.lay_liability,
    profitIfBackWins: odds.profit_if_back_wins,
    profitIfLayWins: odds.profit_if_lay_wins,
    qualifyingLoss: odds.qualifying_loss,
    pnlPercentage: odds.pnl_percentage,
    rating: odds.rating
  })

  // Recalculate when inputs change (skip initial identical state)
  useEffect(() => {
    if (backStake === odds.back_stake && backOdds === odds.back_odds && layOdds === odds.lay_odds && commission === odds.lay_commission) {
      return
    }
    calculateMatchedBet()
  }, [backStake, backOdds, layOdds, commission])

  const calculateMatchedBet = () => {
    const isBonus = odds.bet_type === 'bonus'

    let layStake: number
    if (isBonus) {
      layStake = (backStake * (backOdds - 1)) / (layOdds - commission)
    } else {
      layStake = (backStake * backOdds) / (layOdds - commission)
    }

    const layLiability = layStake * (layOdds - 1)

    const backWinnings = isBonus ? backStake * (backOdds - 1) : (backStake * backOdds) - backStake
    const profitIfBackWins = backWinnings - layLiability

    const layProfit = layStake - (layStake * commission)
    const backLoss = isBonus ? 0 : backStake
    const profitIfLayWins = layProfit - backLoss

    const qualifyingLoss = (profitIfBackWins + profitIfLayWins) / 2
    const pnlPercentage = (qualifyingLoss / backStake) * 100

    const rating = isBonus
      ? Math.min(100, Math.max(0, (qualifyingLoss / backStake) * 100))
      : Math.max(0, 100 - (Math.abs(pnlPercentage) * 20))

    setCalc({
      backStake,
      layStake,
      layLiability,
      profitIfBackWins,
      profitIfLayWins,
      qualifyingLoss,
      pnlPercentage,
      rating
    })
  }

  const copyLayStake = async () => {
    try {
      await navigator.clipboard.writeText(calc.layStake.toFixed(2))
      setCopiedStake(true)
      setTimeout(() => setCopiedStake(false), 2000)
    } catch (err) {
      console.error('Failed to copy:', err)
    }
  }

  const copySummary = async () => {
    try {
      const summary = `Matched Bet Summary
Event: ${odds.event_name}
Selection: ${odds.selection_name}
Stake: ${formatCurrency(backStake)}
Back Odds: ${backOdds.toFixed(2)} (${odds.back_bookmaker_name})
Lay Odds: ${layOdds.toFixed(2)} (Betfair)
Lay Stake: ${formatCurrency(calc.layStake)}
Qualifying Loss: ${formatCurrency(calc.qualifyingLoss)} (${formatPercentage(calc.pnlPercentage)})`

      await navigator.clipboard.writeText(summary)
      setCopiedSummary(true)
      setTimeout(() => setCopiedSummary(false), 2000)
    } catch (err) {
      console.error('Failed to copy:', err)
    }
  }

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-AU', {
      style: 'currency',
      currency: 'AUD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    }).format(amount)
  }

  const formatPercentage = (pct: number) => {
    return `${pct >= 0 ? '+' : ''}${pct.toFixed(2)}%`
  }

  const getSportEmoji = () => {
    const sportName = odds.sport_name.toLowerCase()
    if (sportName.includes('soccer') || sportName.includes('football')) return '⚽'
    if (sportName.includes('basketball')) return '🏀'
    if (sportName.includes('tennis')) return '🎾'
    if (sportName.includes('cricket')) return '🏏'
    if (sportName.includes('rugby')) return '🏉'
    if (sportName.includes('horse')) return '🐎'
    return '🎯'
  }

  const formatEventTime = () => {
    try {
      const date = new Date(odds.event_start_time)
      return date.toLocaleString('en-AU', {
        day: '2-digit',
        month: '2-digit',
        year: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        hour12: true
      })
    } catch {
      return ''
    }
  }

  return (
    <Dialog open={true} onOpenChange={onClose}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <DialogHeader className="pb-3">
          <div className="flex items-center justify-between">
            <DialogTitle className="flex items-center gap-2 text-lg">
              <Calculator className="w-5 h-5 pl-1" />
              Odds Matcher
            </DialogTitle>
            <button
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors flex items-center gap-1.5"
              title="Advanced Settings"
            >
              <Settings className={`w-5 h-5 ${showAdvanced ? 'text-blue-600' : 'text-gray-600'}`} />
              <span className={`text-sm font-medium ${showAdvanced ? 'text-blue-600' : 'text-gray-600'}`}>
                Advanced
              </span>
            </button>
          </div>
          <div className="text-sm text-gray-600 flex items-center gap-3 mt-2">
            <span className="text-lg">{getSportEmoji()}</span>
            <span className="font-medium text-gray-900">{odds.event_name}</span>
            <span className="text-gray-400">•</span>
            <span>{odds.competition_name}</span>
            <span className="text-gray-400">•</span>
            <span className="uppercase text-xs font-medium">{odds.market_type.replace('_', ' ')}</span>
          </div>
          <div className="text-xs text-gray-500 mt-1">
            {formatEventTime()}
          </div>
        </DialogHeader>

        <div className="space-y-4">
          {/* Outcome pill */}
          <div className="flex items-center justify-between">
            <div className="flex items-baseline gap-2">
              <span className="text-sm text-gray-600 font-semibold">Outcome:</span>
              <span className="text-lg text-gray-900">{odds.selection_name}</span>
            </div>
            <div className={`px-3 py-1 rounded-full text-sm font-medium ${odds.bet_type === 'bonus' ? 'bg-green-100 text-green-700' : 'bg-blue-100 text-blue-700'}`}>
              {odds.bet_type === 'bonus' ? 'Bonus Bet' : 'Normal Bet'}
            </div>
          </div>

          {/* Advanced Settings */}
          {showAdvanced && (
            <div className="p-4 bg-gray-50 rounded-lg border border-gray-200">
              <div className="max-w-xs">
                <Label htmlFor="commission" className="text-sm font-medium">
                  Betfair Commission (%)
                </Label>
                <input
                  id="commission"
                  type="number"
                  min="0"
                  max="100"
                  step="0.5"
                  value={commission * 100}
                  onChange={(e) => setCommission(parseFloat(e.target.value) / 100)}
                  className="w-full mt-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
                <div className="text-xs text-gray-500 mt-1">
                  Typically 5-6% (for Australian users)
                </div>
              </div>
            </div>
          )}

          {/* Two-column action cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="bg-blue-50 border border-blue-100 rounded-lg p-4">
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm font-semibold text-blue-800">Bookie</span>
                <span className="text-xs text-blue-700">{odds.back_bookmaker_name}</span>
              </div>
              <div className="space-y-3">
                <div>
                  <Label htmlFor="back-odds" className="text-xs font-medium text-gray-700">Odds</Label>
                  <input
                    id="back-odds"
                    type="number"
                    min="1.01"
                    step="0.01"
                    value={backOdds}
                    onChange={(e) => setBackOdds(parseFloat(e.target.value))}
                    className="w-full mt-1 px-3 py-2 border border-blue-200 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-lg font-semibold bg-white"
                  />
                </div>
                <div>
                  <Label htmlFor="back-stake" className="text-xs font-medium text-gray-700">Stake</Label>
                  <input
                    id="back-stake"
                    type="number"
                    min="1"
                    step="1"
                    value={backStake}
                    onChange={(e) => setBackStake(parseFloat(e.target.value))}
                    className="w-full mt-1 px-3 py-2 border border-blue-200 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-lg font-semibold bg-white"
                  />
                </div>
              </div>
            </div>

            <div className="bg-rose-50 border border-rose-100 rounded-lg p-4">
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm font-semibold text-rose-800">Betfair</span>
                <span className="text-xs text-rose-700">{(commission * 100).toFixed(1)}% commission</span>
              </div>
              <div className="space-y-3">
                <div>
                  <Label htmlFor="lay-odds" className="text-xs font-medium text-gray-700">Lay Odds</Label>
                  <input
                    id="lay-odds"
                    type="number"
                    min="1.01"
                    step="0.01"
                    value={layOdds}
                    onChange={(e) => setLayOdds(parseFloat(e.target.value))}
                    className="w-full mt-1 px-3 py-2 border border-rose-200 rounded-md focus:ring-2 focus:ring-rose-500 focus:border-rose-500 text-lg font-semibold bg-white"
                  />
                </div>
                <div className="bg-white border border-rose-200 rounded-md p-3 flex items-center justify-between">
                  <div>
                    <div className="text-xs text-gray-500">Lay Stake</div>
                    <div className="text-xl font-bold text-rose-800">{formatCurrency(calc.layStake)}</div>
                    <div className="text-xs text-gray-500">Liability: {formatCurrency(calc.layLiability)}</div>
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

          {/* Scenario table */}
          <div className="border border-gray-200 rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="text-left py-2 px-3 font-medium text-gray-700">Winner</th>
                  <th className="text-right py-2 px-3 font-medium text-gray-700">Bookie</th>
                  <th className="text-right py-2 px-3 font-medium text-gray-700">Betfair</th>
                  <th className="text-right py-2 px-3 font-medium text-gray-700">Avail</th>
                </tr>
              </thead>
              <tbody>
                <tr className="border-t bg-white">
                  <td className="py-2 px-3 font-medium">{odds.selection_name}</td>
                  <td className="text-right py-2 px-3 text-green-700 font-semibold">
                    +{formatCurrency(odds.bet_type === 'bonus' ? backStake * (backOdds - 1) : (backStake * backOdds) - backStake)}
                  </td>
                  <td className="text-right py-2 px-3 text-red-700 font-semibold">
                    -{formatCurrency(calc.layLiability)}
                  </td>
                  <td className={`text-right py-2 px-3 font-bold ${calc.profitIfBackWins >= 0 ? 'text-green-700' : 'text-red-700'}`}>
                    {formatCurrency(calc.profitIfBackWins)}
                  </td>
                </tr>
                <tr className="border-t bg-white">
                  <td className="py-2 px-3 font-medium">Other outcome</td>
                  <td className="text-right py-2 px-3 text-red-700 font-semibold">
                    {odds.bet_type === 'bonus' ? formatCurrency(0) : `-${formatCurrency(backStake)}`}
                  </td>
                  <td className="text-right py-2 px-3 text-green-700 font-semibold">
                    +{formatCurrency(calc.layStake - (calc.layStake * commission))}
                  </td>
                  <td className={`text-right py-2 px-3 font-bold ${calc.profitIfLayWins >= 0 ? 'text-green-700' : 'text-red-700'}`}>
                    {formatCurrency(calc.profitIfLayWins)}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          {/* Info + copy summary (moved here) */}
          <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 flex items-start justify-between gap-4">
            <div>
              <div className={`text-lg font-bold ${calc.qualifyingLoss >= 0 ? 'text-green-700' : 'text-red-700'}`}>
                {calc.qualifyingLoss >= 0 ? 'Profit' : 'Loss'} {formatCurrency(Math.abs(calc.qualifyingLoss))}
              </div>
              <div className="text-sm text-gray-600 mt-1">
                {calc.pnlPercentage >= 0 ? 'PnL' : 'Qualifying Loss'} {formatPercentage(calc.pnlPercentage)}
              </div>
              {odds.bet_type === 'normal' && calc.qualifyingLoss < 0 && (
                <div className="mt-3 p-3 bg-yellow-50 rounded-lg border border-yellow-200">
                  <div className="flex items-start gap-2 text-xs text-yellow-900">
                    <span className="text-base leading-none mt-0.5">⚠️</span>
                    <span>
                      You'll lose about <strong>{formatCurrency(Math.abs(calc.qualifyingLoss))}</strong> ({formatPercentage(calc.pnlPercentage)}) to unlock bonus bets worth much more.
                    </span>
                  </div>
                </div>
              )}
              {odds.bet_type === 'bonus' && (
                <div className="mt-3 p-3 bg-green-50 rounded-lg border border-green-200">
                  <div className="flex items-start gap-2 text-xs text-green-900">
                    <span className="text-base leading-none mt-0.5">🎁</span>
                    <span>
                      <strong>Bonus Bet:</strong> Free bet with average profit of <strong>{formatCurrency(calc.qualifyingLoss)}</strong>
                    </span>
                  </div>
                </div>
              )}
            </div>
            <button
              onClick={copySummary}
              className="p-2 hover:bg-blue-100 rounded-lg transition-colors self-start"
              title="Copy summary"
            >
              {copiedSummary ? (
                <Check className="w-5 h-5 text-green-600" />
              ) : (
                <Copy className="w-5 h-5 text-blue-600" />
              )}
            </button>
          </div>

          {/* Action Buttons */}
          <div className="flex justify-between flex-wrap gap-3 pt-1">
            <div className="flex gap-2">
              <button
                onClick={() => window.open(getBookmakerUrl(odds.back_bookmaker_code), '_blank')}
                className="px-4 py-2 bg-blue-600 text-white rounded-xl hover:bg-blue-700 transition-all hover:shadow-lg flex items-center gap-2 text-sm"
              >
                <ExternalLink className="w-4 h-4" />
                Open {odds.back_bookmaker_name}
              </button>
              <button
                onClick={() => window.open(getBookmakerUrl('betfair'), '_blank')}
                className="px-4 py-2 bg-yellow-500 text-white rounded-xl hover:bg-yellow-600 transition-all hover:shadow-lg flex items-center gap-2 text-sm"
              >
                <ExternalLink className="w-4 h-4" />
                Open Betfair
              </button>
            </div>

            <div className="flex gap-2">
              {onStakeChange && backStake !== odds.back_stake && (
                <button
                  onClick={() => {
                    onStakeChange(backStake)
                    onClose()
                  }}
                  className="px-4 py-2 bg-green-600 text-white rounded-xl hover:bg-green-700 transition-all hover:shadow-lg text-sm"
                >
                  Update Stake
                </button>
              )}
              <button
                onClick={onClose}
                className="px-4 py-2 border border-gray-300 rounded-xl hover:bg-gray-50 transition-colors text-sm"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
