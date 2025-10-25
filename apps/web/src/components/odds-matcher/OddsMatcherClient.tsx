'use client'

import { useState, useEffect, useMemo } from 'react'
import { OddsFilters } from './OddsFilters'
import { OddsTable } from './OddsTable'
import { BetCalculatorModal } from './BetCalculatorModal'
import { RefreshCw } from 'lucide-react'

export type BetType = 'normal' | 'bonus'

export interface OddsMatch {
  event_id: number
  event_name: string
  event_start_time: string
  sport_name: string
  competition_name: string
  market_id: number
  market_name: string
  market_type: string
  selection_id: number
  selection_name: string
  back_bookmaker_code: string
  back_bookmaker_name: string
  back_odds: number
  back_stake: number
  lay_odds: number
  lay_stake: number
  lay_liability: number
  lay_commission: number
  lay_liquidity: number | null
  profit_if_back_wins: number
  profit_if_lay_wins: number
  qualifying_loss: number
  pnl_percentage: number
  bet_type: BetType
  rating: number
  last_updated: string
}

export interface OddsFilters {
  stake: number
  betType: BetType
  bookmakers: string[]
  sports: string[]
  competitions: number[]
  search: string
}

export function OddsMatcherClient() {
  const [filters, setFilters] = useState<OddsFilters>({
    stake: 100,
    betType: 'normal',
    bookmakers: [],
    sports: [],
    competitions: [],
    search: ''
  })

  const [opportunities, setOpportunities] = useState<OddsMatch[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null)

  const [selectedOdds, setSelectedOdds] = useState<OddsMatch | null>(null)

  // Auto-refresh odds on component mount (triggers scraping if cache expired)
  useEffect(() => {
    refreshOdds()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Refetch opportunities when bet type or stake changes (recalculates with new parameters)
  useEffect(() => {
    if (opportunities.length > 0) {
      fetchOpportunities()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters.betType, filters.stake])

  const fetchOpportunities = async () => {
    setLoading(true)
    setError(null)

    try {
      // Fetch ALL opportunities with just stake and bet type (filtering happens client-side)
      const params = new URLSearchParams()
      params.append('stake', filters.stake.toString())
      params.append('bet_type', filters.betType)

      // ✅ Using real TAB + Betfair odds from database
      const response = await fetch(`/api/proxy/odds/matcher?${params.toString()}`)

      if (!response.ok) {
        throw new Error('Failed to fetch odds')
      }

      const data = await response.json()
      setOpportunities(data)
      setLastRefresh(new Date())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setLoading(false)
    }
  }

  // Client-side filtering for instant results
  const filteredOpportunities = useMemo(() => {
    return opportunities.filter(opp => {
      // Filter by bookmaker
      if (filters.bookmakers.length > 0 && !filters.bookmakers.includes(opp.back_bookmaker_code)) {
        return false
      }

      // Filter by league/competition
      if (filters.sports.length > 0 && !filters.sports.includes(opp.competition_name.toLowerCase())) {
        return false
      }

      // Filter by search text
      if (filters.search) {
        const searchLower = filters.search.toLowerCase()
        const matchesEvent = opp.event_name.toLowerCase().includes(searchLower)
        const matchesSelection = opp.selection_name.toLowerCase().includes(searchLower)
        if (!matchesEvent && !matchesSelection) {
          return false
        }
      }

      return true
    })
  }, [opportunities, filters])

  const refreshOdds = async () => {
    setLoading(true)
    setError(null)

    try {
      const response = await fetch('/api/proxy/odds/refresh', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ force: false })  // Respect cache!
      })

      if (!response.ok) {
        throw new Error('Failed to refresh odds')
      }

      // After refresh, fetch new opportunities
      await fetchOpportunities()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* Filters */}
      <OddsFilters
        filters={filters}
        onFiltersChange={setFilters}
      />

      {/* Refresh Button */}
      <div className="flex justify-between items-center">
        <div className="text-sm text-gray-600">
          {lastRefresh && (
            <span>Last updated: {lastRefresh.toLocaleTimeString()}</span>
          )}
          {opportunities.length > 0 && (
            <span className="ml-4">
              Showing {filteredOpportunities.length} of {opportunities.length} opportunities
            </span>
          )}
        </div>

        <button
          onClick={refreshOdds}
          disabled={loading}
          className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          REFRESH ODDS
        </button>
      </div>

      {/* Error Display */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-800 px-4 py-3 rounded-lg">
          {error}
        </div>
      )}

      {/* Odds Table */}
      <OddsTable
        opportunities={filteredOpportunities}
        loading={loading}
        onSelectOdds={setSelectedOdds}
      />

      {/* Bet Calculator Modal */}
      {selectedOdds && (
        <BetCalculatorModal
          odds={selectedOdds}
          onClose={() => setSelectedOdds(null)}
          onStakeChange={(newStake) => {
            setFilters({ ...filters, stake: newStake })
          }}
        />
      )}
    </div>
  )
}
