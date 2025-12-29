'use client'

import { useState, useEffect } from 'react'
import { Plus, Trash2, Info, Settings, HelpCircle, Play } from 'lucide-react'
import { calculateLongTermEV, formatCurrency, formatPercentage } from '@/lib/calculators/calculations'
import { Label } from '@/components/ui/label'
import { PremiumLock } from '@/hooks/useSubscription'

interface LegEntry {
  id: number
  odds: number
}

function LongTermEVContent() {
  // Input state
  const [numBets, setNumBets] = useState<number>(100)
  const [stake, setStake] = useState<number>(50)
  const [overround, setOverround] = useState<number>(5)
  const [bonusRetention, setBonusRetention] = useState<number>(70)
  const [anyLegFail, setAnyLegFail] = useState<boolean>(false)
  const [isSGM, setIsSGM] = useState<boolean>(false)
  const [showAdvanced, setShowAdvanced] = useState<boolean>(false)
  const [isSimulating, setIsSimulating] = useState<boolean>(false)
  const [legs, setLegs] = useState<LegEntry[]>([
    { id: 1, odds: 1.5 }
  ])
  const [nextId, setNextId] = useState(2)

  // Calculated results
  const [result, setResult] = useState<ReturnType<typeof calculateLongTermEV> | null>(null)

  const runSimulation = () => {
    setIsSimulating(true)

    // Use setTimeout to allow UI to update
    setTimeout(() => {
      const legData = legs.map(l => ({ odds: l.odds }))
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
      { id: nextId, odds: 1.5 }
    ])
    setNextId(prev => prev + 1)
  }

  const removeLeg = (id: number) => {
    if (legs.length <= 1) return
    setLegs(prev => prev.filter(l => l.id !== id))
  }

  const updateLegOdds = (id: number, odds: number) => {
    setLegs(prev =>
      prev.map(l => l.id === id ? { ...l, odds } : l)
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="text-center">
        <h1 className="text-3xl font-bold text-gray-900">Long Term EV Calculator</h1>
        <p className="text-gray-600 mt-2">Simulate expected value over many bets</p>
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

      {/* Number of Bets */}
      <div className="bg-blue-50 rounded-xl p-4 border border-blue-100">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Label className="text-blue-800 font-medium">Number of bets</Label>
            <button className="text-blue-400 hover:text-blue-600">
              <HelpCircle className="w-4 h-4" />
            </button>
          </div>
          <input
            type="number"
            min="1"
            max="10000"
            step="10"
            value={numBets}
            onChange={(e) => setNumBets(parseInt(e.target.value) || 1)}
            className="w-32 px-3 py-2 border border-blue-200 rounded-lg text-center font-semibold focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
        </div>
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
      <div className="bg-purple-50 rounded-xl p-4 border border-purple-100">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Label className="text-purple-800 font-medium">Stake</Label>
            <button className="text-purple-400 hover:text-purple-600">
              <HelpCircle className="w-4 h-4" />
            </button>
          </div>
          <input
            type="number"
            min="1"
            step="1"
            value={stake}
            onChange={(e) => setStake(parseFloat(e.target.value) || 0)}
            className="w-32 px-3 py-2 border border-purple-200 rounded-lg text-center font-semibold focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
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
                  type="number"
                  min="0"
                  max="20"
                  step="0.5"
                  value={overround}
                  onChange={(e) => setOverround(parseFloat(e.target.value) || 0)}
                  className="w-20 px-3 py-2 border border-pink-200 rounded-lg text-center font-semibold focus:ring-2 focus:ring-pink-500 focus:border-pink-500"
                />
                <span className="bg-pink-200 text-pink-800 px-3 py-2 rounded-lg font-medium">%</span>
              </div>
            </div>
          </div>

          <div className="bg-amber-50 rounded-xl p-4 border border-amber-100">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Label className="text-amber-800 font-medium">Bonus bet retention</Label>
                <button className="text-amber-400 hover:text-amber-600">
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
                  className="w-20 px-3 py-2 border border-amber-200 rounded-lg text-center font-semibold focus:ring-2 focus:ring-amber-500 focus:border-amber-500"
                />
                <span className="bg-amber-200 text-amber-800 px-3 py-2 rounded-lg font-medium">%</span>
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
            <span className="font-medium text-gray-700">Add Leg {index + 1}</span>
            <div className="flex items-center gap-3">
              <input
                type="number"
                min="1.01"
                step="0.01"
                value={leg.odds}
                onChange={(e) => updateLegOdds(leg.id, parseFloat(e.target.value) || 1.01)}
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
        Add Add Leg
      </button>

      {/* Simulate Button */}
      <button
        onClick={runSimulation}
        disabled={isSimulating}
        className="w-full py-4 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white rounded-xl font-medium text-lg transition-colors flex items-center justify-center gap-2"
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
            <div className="bg-white rounded-xl border border-gray-200 p-4 text-center">
              <div className="text-sm text-gray-500">Expected Profit</div>
              <div className={`text-xl font-bold ${
                result.expectedProfit >= 0 ? 'text-green-600' : 'text-red-600'
              }`}>
                {formatCurrency(result.expectedProfit)}
              </div>
            </div>
            <div className="bg-white rounded-xl border border-gray-200 p-4 text-center">
              <div className="text-sm text-gray-500">Per Bet</div>
              <div className={`text-xl font-bold ${
                result.expectedProfitPerBet >= 0 ? 'text-green-600' : 'text-red-600'
              }`}>
                {formatCurrency(result.expectedProfitPerBet)}
              </div>
            </div>
            <div className="bg-white rounded-xl border border-gray-200 p-4 text-center">
              <div className="text-sm text-gray-500">Std Deviation</div>
              <div className="text-xl font-bold text-gray-900">
                {formatCurrency(result.standardDeviation)}
              </div>
            </div>
            <div className="bg-white rounded-xl border border-gray-200 p-4 text-center">
              <div className="text-sm text-gray-500">Profit Probability</div>
              <div className={`text-xl font-bold ${
                result.probabilityOfProfit >= 50 ? 'text-green-600' : 'text-amber-600'
              }`}>
                {formatPercentage(result.probabilityOfProfit, false)}
              </div>
            </div>
          </div>

          {/* Range */}
          <div className="bg-gray-50 rounded-xl border border-gray-200 p-4">
            <div className="text-sm text-gray-600 mb-2">90% Confidence Interval</div>
            <div className="flex items-center justify-between">
              <div>
                <span className="text-sm text-gray-500">Worst (5%)</span>
                <div className={`text-lg font-bold ${
                  result.worstCase >= 0 ? 'text-green-600' : 'text-red-600'
                }`}>
                  {formatCurrency(result.worstCase)}
                </div>
              </div>
              <div className="flex-1 mx-4 h-2 bg-gradient-to-r from-red-200 via-yellow-200 to-green-200 rounded-full"></div>
              <div className="text-right">
                <span className="text-sm text-gray-500">Best (95%)</span>
                <div className="text-lg font-bold text-green-600">
                  {formatCurrency(result.bestCase)}
                </div>
              </div>
            </div>
          </div>
        </>
      )}

      {/* Info Box */}
      <div className="bg-blue-50 border border-blue-200 rounded-xl p-4">
        <div className="flex gap-3">
          <Info className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
          <div className="text-sm text-blue-800">
            <strong>Long-Term EV</strong> uses Monte Carlo simulation to estimate outcomes over many bets.
            <ul className="mt-2 space-y-1 list-disc list-inside text-blue-700">
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
