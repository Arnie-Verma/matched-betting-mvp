'use client'

import { OddsMatch } from './OddsMatcherClient'
import { TrendingUp, TrendingDown } from 'lucide-react'

interface OddsTableProps {
  opportunities: OddsMatch[]
  loading: boolean
  onSelectOdds: (odds: OddsMatch) => void
}

export function OddsTable({ opportunities, loading, onSelectOdds }: OddsTableProps) {
  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-AU', {
      style: 'currency',
      currency: 'AUD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    }).format(amount)
  }

  const formatOdds = (odds: number) => {
    return odds.toFixed(2)
  }

  const formatPercentage = (pct: number) => {
    return `${pct >= 0 ? '+' : ''}${pct.toFixed(2)}%`
  }

  const formatDate = (dateString: string) => {
    const date = new Date(dateString)
    const now = new Date()
    const diffMs = date.getTime() - now.getTime()
    const diffMins = Math.floor(diffMs / 60000)
    const diffHours = Math.floor(diffMins / 60)
    const diffDays = Math.floor(diffHours / 24)

    if (diffDays > 0) {
      return `${diffDays}d ${diffHours % 24}h`
    } else if (diffHours > 0) {
      return `${diffHours}h ${diffMins % 60}m`
    } else if (diffMins > 0) {
      return `${diffMins}m`
    } else {
      return 'Soon'
    }
  }

  if (loading && opportunities.length === 0) {
    return (
      <div className="bg-white rounded-lg border shadow-sm p-12">
        <div className="flex flex-col items-center justify-center text-gray-500">
          <div className="w-12 h-12 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mb-4"></div>
          <p>Loading opportunities...</p>
        </div>
      </div>
    )
  }

  if (!loading && opportunities.length === 0) {
    return (
      <div className="bg-white rounded-lg border shadow-sm p-12">
        <div className="text-center text-gray-500">
          <p className="text-lg font-medium mb-2">No opportunities found</p>
          <p className="text-sm">Try adjusting your filters or refresh the odds</p>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-lg border shadow-sm overflow-hidden">
      {/* Desktop Table */}
      <div className="hidden lg:block overflow-x-auto">
        <table className="w-full">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider">
                Event
              </th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider">
                Selection
              </th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider">
                Bookmaker
              </th>
              <th className="px-4 py-3 text-center text-xs font-semibold text-gray-700 uppercase tracking-wider">
                Back Odds
              </th>
              <th className="px-4 py-3 text-center text-xs font-semibold text-gray-700 uppercase tracking-wider">
                Lay Odds
              </th>
              <th className="px-4 py-3 text-center text-xs font-semibold text-gray-700 uppercase tracking-wider">
                Liquidity
              </th>
              <th className="px-4 py-3 text-right text-xs font-semibold text-gray-700 uppercase tracking-wider">
                PnL %
              </th>
              <th className="px-4 py-3 text-center text-xs font-semibold text-gray-700 uppercase tracking-wider">
                Action
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {opportunities.map((opp) => (
              <tr
                key={`${opp.event_id}-${opp.selection_id}`}
                className="hover:bg-gray-50 transition-colors"
              >
                <td className="px-4 py-4">
                  <div>
                    <div className="font-medium text-gray-900 text-sm">{opp.event_name}</div>
                    <div className="text-xs text-gray-500">
                      {opp.sport_name} · {opp.competition_name}
                    </div>
                    <div className="text-xs text-gray-400 mt-1">
                      in {formatDate(opp.event_start_time)}
                    </div>
                  </div>
                </td>
                <td className="px-4 py-4">
                  <div className="text-sm font-medium text-gray-900">{opp.selection_name}</div>
                  <div className="text-xs text-gray-500">{opp.market_name}</div>
                </td>
                <td className="px-4 py-4">
                  <div className="text-sm font-medium text-gray-900">{opp.back_bookmaker_name}</div>
                  <div className="text-xs text-gray-500">vs Betfair</div>
                </td>
                <td className="px-4 py-4 text-center">
                  <span className="text-sm font-semibold text-green-700">{formatOdds(opp.back_odds)}</span>
                </td>
                <td className="px-4 py-4 text-center">
                  <span className="text-sm font-semibold text-red-700">{formatOdds(opp.lay_odds)}</span>
                </td>
                <td className="px-4 py-4 text-center">
                  {opp.lay_liquidity ? (
                    <span className="text-sm text-gray-700">{formatCurrency(opp.lay_liquidity)}</span>
                  ) : (
                    <span className="text-xs text-gray-400">N/A</span>
                  )}
                </td>
                <td className="px-4 py-4 text-right">
                  <div className="flex items-center justify-end gap-1">
                    {opp.pnl_percentage >= 0 ? (
                      <TrendingUp className="w-4 h-4 text-green-600" />
                    ) : (
                      <TrendingDown className="w-4 h-4 text-red-600" />
                    )}
                    <span className={`text-sm font-semibold ${opp.pnl_percentage >= 0 ? 'text-green-700' : 'text-red-700'}`}>
                      {formatPercentage(opp.pnl_percentage)}
                    </span>
                  </div>
                </td>
                <td className="px-4 py-4 text-center">
                  <button
                    onClick={() => onSelectOdds(opp)}
                    className="bg-blue-600 text-white px-3 py-1 rounded text-sm font-medium hover:bg-blue-700 transition-colors"
                  >
                    OPEN
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Mobile Cards */}
      <div className="lg:hidden divide-y divide-gray-200">
        {opportunities.map((opp) => (
          <div key={`${opp.event_id}-${opp.selection_id}`} className="p-4 space-y-3">
            {/* Event Info */}
            <div>
              <div className="font-medium text-gray-900">{opp.event_name}</div>
              <div className="text-xs text-gray-500">
                {opp.sport_name} · {opp.competition_name} · in {formatDate(opp.event_start_time)}
              </div>
            </div>

            {/* Selection and Bookmaker */}
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <div className="text-xs text-gray-500 mb-1">Selection</div>
                <div className="font-medium">{opp.selection_name}</div>
              </div>
              <div>
                <div className="text-xs text-gray-500 mb-1">Bookmaker</div>
                <div className="font-medium">{opp.back_bookmaker_name}</div>
              </div>
            </div>

            {/* Odds */}
            <div className="grid grid-cols-3 gap-3 text-sm">
              <div>
                <div className="text-xs text-gray-500 mb-1">Back</div>
                <div className="font-semibold text-green-700">{formatOdds(opp.back_odds)}</div>
              </div>
              <div>
                <div className="text-xs text-gray-500 mb-1">Lay</div>
                <div className="font-semibold text-red-700">{formatOdds(opp.lay_odds)}</div>
              </div>
              <div>
                <div className="text-xs text-gray-500 mb-1">PnL %</div>
                <div className={`font-semibold ${opp.pnl_percentage >= 0 ? 'text-green-700' : 'text-red-700'}`}>
                  {formatPercentage(opp.pnl_percentage)}
                </div>
              </div>
            </div>

            {/* Action */}
            <div className="flex items-center justify-end">
              <button
                onClick={() => onSelectOdds(opp)}
                className="bg-blue-600 text-white px-4 py-2 rounded font-medium hover:bg-blue-700 transition-colors"
              >
                OPEN
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
