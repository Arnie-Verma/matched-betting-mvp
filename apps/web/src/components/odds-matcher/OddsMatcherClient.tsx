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
  const [showPerformanceNotice, setShowPerformanceNotice] = useState(false)

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
    setShowPerformanceNotice(false)

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

      const refreshData = await response.json()

      // Show performance notice if cache was NOT used (fresh scrape)
      if (refreshData.used_cache === false) {
        setShowPerformanceNotice(true)
        // Auto-hide after 10 seconds
        setTimeout(() => setShowPerformanceNotice(false), 10000)
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

      {/* Performance Notice */}
      {showPerformanceNotice && (
        <div className="bg-yellow-50 border border-yellow-200 text-yellow-800 px-4 py-3 rounded-lg">
          <div className="flex items-start gap-2">
            <svg className="w-5 h-5 mt-0.5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
            </svg>
            <div>
              <p className="font-medium">Performance Notice</p>
              <p className="text-sm mt-1">
                Scraping fresh odds data may take 10-15 seconds. This only happens when the cache expires (every 5 minutes). Subsequent refreshes will be instant.
              </p>
            </div>
          </div>
        </div>
      )}

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
