'use client'

import { useState, useEffect } from 'react'
import { X, Calculator, TrendingUp, TrendingDown, Copy, Check, ChevronDown } from 'lucide-react'
import { OddsMatch } from './OddsMatcherClient'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'

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

export function BetCalculatorModal({ odds, onClose, onStakeChange }: BetCalculatorModalProps) {
  // Editable values (only bookmaker stake and odds, plus Betfair lay odds)
  const [backStake, setBackStake] = useState(odds.back_stake)
  const [backOdds, setBackOdds] = useState(odds.back_odds)
  const [layOdds, setLayOdds] = useState(odds.lay_odds)

  // Commission - default 6%, editable in advanced mode
  const [commission, setCommission] = useState(0.06)
  const [showAdvanced, setShowAdvanced] = useState(false)

  // Copy state
  const [copied, setCopied] = useState(false)

  // Calculated values (lay stake is auto-calculated based on back stake and odds)
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

  // Recalculate whenever inputs change (including commission)
  useEffect(() => {
    calculateMatchedBet()
  }, [backStake, backOdds, layOdds, commission])

  const calculateMatchedBet = () => {
    const isBonus = odds.bet_type === 'bonus'

    // Calculate lay stake (auto-calculated based on back stake and odds)
    let layStake: number
    if (isBonus) {
      // Bonus bet: only winnings matter (stake not returned)
      layStake = (backStake * (backOdds - 1)) / layOdds
    } else {
      // Normal bet: stake + winnings
      layStake = (backStake * backOdds) / layOdds
    }

    // Calculate lay liability
    const layLiability = layStake * (layOdds - 1)

    // Scenario 1: Back wins
    let backWinnings: number
    if (isBonus) {
      backWinnings = backStake * (backOdds - 1) // Only profit, no stake returned
    } else {
      backWinnings = (backStake * backOdds) - backStake // Stake + winnings - stake = just winnings
    }

    const profitIfBackWins = backWinnings - layLiability

    // Scenario 2: Lay wins
    const layProfit = layStake - (layStake * commission) // Keep lay stake minus commission
    const backLoss = isBonus ? 0 : backStake // Lose stake on normal bet, nothing on bonus

    const profitIfLayWins = layProfit - backLoss

    // Qualifying loss (average)
    const qualifyingLoss = (profitIfBackWins + profitIfLayWins) / 2

    // PnL percentage
    const pnlPercentage = (qualifyingLoss / backStake) * 100

    // Calculate rating (0-100)
    let rating: number
    if (isBonus) {
      // Bonus bets: rating based on profit potential (70-95% = good)
      const returnPercentage = (qualifyingLoss / backStake) * 100
      rating = Math.min(100, Math.max(0, returnPercentage))
    } else {
      // Normal bets: rating based on closeness of odds (lower loss = higher rating)
      const lossPercentage = Math.abs(pnlPercentage)
      // 0% loss = 100 rating, 5% loss = 0 rating
      rating = Math.max(0, 100 - (lossPercentage * 20))
    }

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
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
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

  return (
    <Dialog open={true} onOpenChange={onClose}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Calculator className="w-5 h-5" />
            Bet Calculator - {odds.event_name}
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-6">
          {/* Event Info */}
          <div className="bg-gray-50 rounded-lg p-4">
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <span className="text-gray-600">Selection:</span>
                <span className="font-semibold ml-2">{odds.selection_name}</span>
              </div>
              <div>
                <span className="text-gray-600">Market:</span>
                <span className="font-semibold ml-2">{odds.market_name}</span>
              </div>
              <div>
                <span className="text-gray-600">Sport:</span>
                <span className="font-semibold ml-2">{odds.sport_name}</span>
              </div>
              <div>
                <span className="text-gray-600">Bet Type:</span>
                <span className={`font-semibold ml-2 ${odds.bet_type === 'bonus' ? 'text-green-700' : 'text-blue-700'}`}>
                  {odds.bet_type === 'bonus' ? 'Bonus Bet' : 'Normal Bet'}
                </span>
              </div>
            </div>
          </div>

          {/* Editable Inputs - Only Bookmaker Stake & Odds, Betfair Lay Odds */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <Label htmlFor="back-stake" className="text-sm font-medium mb-1 block">
                Bookmaker Stake (AUD)
              </Label>
              <input
                id="back-stake"
                type="number"
                min="1"
                step="10"
                value={backStake}
                onChange={(e) => setBackStake(parseFloat(e.target.value))}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
              <div className="text-xs text-gray-500 mt-1">{odds.back_bookmaker_name}</div>
            </div>

            <div>
              <Label htmlFor="back-odds" className="text-sm font-medium mb-1 block">
                Bookmaker Odds
              </Label>
              <input
                id="back-odds"
                type="number"
                min="1.01"
                step="0.01"
                value={backOdds}
                onChange={(e) => setBackOdds(parseFloat(e.target.value))}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
              <div className="text-xs text-gray-500 mt-1">{odds.back_bookmaker_name}</div>
            </div>

            <div>
              <Label htmlFor="lay-odds" className="text-sm font-medium mb-1 block">
                Betfair Lay Odds
              </Label>
              <input
                id="lay-odds"
                type="number"
                min="1.01"
                step="0.01"
                value={layOdds}
                onChange={(e) => setLayOdds(parseFloat(e.target.value))}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
              <div className="text-xs text-gray-500 mt-1">Betfair ({(commission * 100).toFixed(0)}% commission)</div>
            </div>
          </div>

          {/* Advanced Toggle */}
          <div className="border-t pt-4">
            <button
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="flex items-center gap-2 text-sm text-blue-600 hover:text-blue-700 font-medium"
            >
              <ChevronDown className={`w-4 h-4 transition-transform ${showAdvanced ? 'rotate-180' : ''}`} />
              {showAdvanced ? 'Hide' : 'Show'} Advanced Settings
            </button>

            {showAdvanced && (
              <div className="mt-4 p-4 bg-gray-50 rounded-lg">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <Label htmlFor="commission" className="text-sm font-medium mb-1 block">
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
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    />
                    <div className="text-xs text-gray-500 mt-1">
                      Default: 6% (2% for base rate customers)
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Calculated Stakes (auto-calculated, read-only display) */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="bg-blue-50 rounded-lg p-4">
              <div className="text-sm text-gray-600 mb-1">Betfair Lay Stake (Auto-calculated)</div>
              <div className="flex items-center gap-2">
                <div className="text-2xl font-bold text-blue-900">{formatCurrency(calc.layStake)}</div>
                <button
                  onClick={copyLayStake}
                  className="p-2 hover:bg-blue-100 rounded transition-colors"
                  title="Copy stake amount"
                >
                  {copied ? (
                    <Check className="w-5 h-5 text-green-600" />
                  ) : (
                    <Copy className="w-5 h-5 text-blue-600" />
                  )}
                </button>
              </div>
              <div className="text-xs text-gray-600 mt-1">
                {copied ? 'Copied to clipboard!' : 'Place this amount at Betfair'}
              </div>
            </div>

            <div className="bg-red-50 rounded-lg p-4">
              <div className="text-sm text-gray-600 mb-1">Betfair Liability</div>
              <div className="text-2xl font-bold text-red-900">{formatCurrency(calc.layLiability)}</div>
              <div className="text-xs text-gray-600 mt-1">Maximum risk on exchange</div>
            </div>
          </div>

          {/* Outcome Matrix */}
          <div>
            <h3 className="text-lg font-semibold mb-3">Outcome Matrix</h3>
            <div className="space-y-3">
              {/* Outcome 1: Back wins */}
              <div className={`border-2 rounded-lg p-4 ${calc.profitIfBackWins > calc.profitIfLayWins ? 'border-green-500 bg-green-50' : 'border-gray-300 bg-white'}`}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    {calc.profitIfBackWins >= 0 ? (
                      <TrendingUp className="w-5 h-5 text-green-600" />
                    ) : (
                      <TrendingDown className="w-5 h-5 text-red-600" />
                    )}
                    <span className="font-semibold">Selection Wins (Back bet wins)</span>
                  </div>
                  <span className={`text-xl font-bold ${calc.profitIfBackWins >= 0 ? 'text-green-700' : 'text-red-700'}`}>
                    {formatCurrency(calc.profitIfBackWins)}
                  </span>
                </div>
                <div className="mt-2 text-sm text-gray-600 grid grid-cols-2 gap-2">
                  <div>
                    Bookmaker wins: {formatCurrency(odds.bet_type === 'bonus' ? backStake * (backOdds - 1) : (backStake * backOdds) - backStake)}
                  </div>
                  <div>
                    Betfair loses: -{formatCurrency(calc.layLiability)}
                  </div>
                </div>
              </div>

              {/* Outcome 2: Lay wins */}
              <div className={`border-2 rounded-lg p-4 ${calc.profitIfLayWins > calc.profitIfBackWins ? 'border-green-500 bg-green-50' : 'border-gray-300 bg-white'}`}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    {calc.profitIfLayWins >= 0 ? (
                      <TrendingUp className="w-5 h-5 text-green-600" />
                    ) : (
                      <TrendingDown className="w-5 h-5 text-red-600" />
                    )}
                    <span className="font-semibold">Selection Loses (Lay bet wins)</span>
                  </div>
                  <span className={`text-xl font-bold ${calc.profitIfLayWins >= 0 ? 'text-green-700' : 'text-red-700'}`}>
                    {formatCurrency(calc.profitIfLayWins)}
                  </span>
                </div>
                <div className="mt-2 text-sm text-gray-600 grid grid-cols-2 gap-2">
                  <div>
                    Betfair wins: {formatCurrency(calc.layStake - (calc.layStake * commission))}
                  </div>
                  <div>
                    Bookmaker loses: {odds.bet_type === 'bonus' ? formatCurrency(0) : `-${formatCurrency(backStake)}`}
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Summary */}
          <div className="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-lg p-6 border border-blue-200">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <div className="text-sm text-gray-600 mb-1">Qualifying Loss/Profit</div>
                <div className={`text-2xl font-bold ${calc.qualifyingLoss >= 0 ? 'text-green-700' : 'text-red-700'}`}>
                  {formatCurrency(calc.qualifyingLoss)}
                </div>
              </div>

              <div>
                <div className="text-sm text-gray-600 mb-1">PnL Percentage</div>
                <div className={`text-2xl font-bold ${calc.pnlPercentage >= 0 ? 'text-green-700' : 'text-red-700'}`}>
                  {formatPercentage(calc.pnlPercentage)}
                </div>
              </div>

              <div>
                <div className="text-sm text-gray-600 mb-1">Rating (Dynamic)</div>
                <div className="text-2xl font-bold text-blue-700">
                  {calc.rating.toFixed(0)}/100
                </div>
                <div className="text-xs text-gray-500 mt-1">
                  Updates as you edit
                </div>
              </div>
            </div>

            {odds.bet_type === 'bonus' && (
              <div className="mt-4 p-3 bg-green-100 rounded-lg">
                <p className="text-sm text-green-800">
                  <strong>Bonus Bet:</strong> This is a free bet. You won't get your stake back, but you also risk nothing!
                  Average profit: {formatCurrency(calc.qualifyingLoss)}
                </p>
              </div>
            )}

            {odds.bet_type === 'normal' && calc.qualifyingLoss < 0 && (
              <div className="mt-4 p-3 bg-yellow-100 rounded-lg">
                <p className="text-sm text-yellow-800">
                  <strong>Qualifying Bet:</strong> You'll lose about {formatCurrency(Math.abs(calc.qualifyingLoss))} on average,
                  but this unlocks bonus bets worth much more!
                </p>
              </div>
            )}
          </div>

          {/* Actions */}
          <div className="flex justify-end gap-3">
            <button
              onClick={onClose}
              className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
            >
              Close
            </button>
            {onStakeChange && backStake !== odds.back_stake && (
              <button
                onClick={() => {
                  onStakeChange(backStake)
                  onClose()
                }}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
              >
                Update Stake & Close
              </button>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
