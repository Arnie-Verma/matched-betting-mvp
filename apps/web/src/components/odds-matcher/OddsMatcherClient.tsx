'use client'

import { useState, useEffect, useMemo, useRef, useCallback } from 'react'
import { OddsFilters } from './OddsFilters'
import { OddsTable } from './OddsTable'
import { BetCalculatorModal } from './BetCalculatorModal'
import { RefreshCw } from 'lucide-react'
import { normalizeLeagueName } from './leagueNormalization'

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

interface PaginatedResponse {
  items: OddsMatch[]
  total: number
  offset: number
  limit: number
  has_more: boolean
}

export interface OddsFilters {
  stake: number
  betType: BetType
  bookmakers: string[]
  sports: string[]
  competitions: number[]
  search: string
}

const PAGE_SIZE = 30

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
  const [totalCount, setTotalCount] = useState(0)
  const [hasMore, setHasMore] = useState(false)
  const [loading, setLoading] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null)
  const [showPerformanceNotice, setShowPerformanceNotice] = useState(false)
  const [scrapeStatus, setScrapeStatus] = useState<string | null>(null)
  const [debouncedStake, setDebouncedStake] = useState(100)

  const [selectedOdds, setSelectedOdds] = useState<OddsMatch | null>(null)

  // Refs for infinite scroll
  const hasInitialized = useRef(false)
  const loadMoreRef = useRef<HTMLDivElement>(null)
  const currentOffset = useRef(0)

  // Auto-refresh odds on component mount (triggers scraping if cache expired)
  useEffect(() => {
    if (hasInitialized.current) return
    hasInitialized.current = true
    refreshOdds()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Debounce stake changes to avoid multiple rapid recalculations
  useEffect(() => {
    const handle = setTimeout(() => setDebouncedStake(filters.stake), 300)
    return () => clearTimeout(handle)
  }, [filters.stake])

  // Refetch opportunities when bet type or debounced stake changes (recalculates with new parameters)
  useEffect(() => {
    if (opportunities.length > 0) {
      fetchOpportunities(true) // Reset to first page
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters.betType, debouncedStake])

  const fetchOpportunities = useCallback(async (reset = false) => {
    const offset = reset ? 0 : currentOffset.current

    if (reset) {
      setLoading(true)
      currentOffset.current = 0
    } else {
      setLoadingMore(true)
    }
    setError(null)

    try {
      const params = new URLSearchParams()
      params.append('stake', debouncedStake.toString())
      params.append('bet_type', filters.betType)
      params.append('limit', PAGE_SIZE.toString())
      params.append('offset', offset.toString())

      const response = await fetch(`/api/proxy/odds/matcher?${params.toString()}`)

      if (!response.ok) {
        throw new Error('Failed to fetch odds')
      }

      const data: PaginatedResponse = await response.json()

      if (reset) {
        setOpportunities(data.items)
      } else {
        setOpportunities(prev => [...prev, ...data.items])
      }

      setTotalCount(data.total)
      setHasMore(data.has_more)
      currentOffset.current = offset + data.items.length
      setLastRefresh(new Date())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setLoading(false)
      setLoadingMore(false)
    }
  }, [debouncedStake, filters.betType])

  // Load more when scrolling near bottom
  const loadMore = useCallback(() => {
    if (!loadingMore && hasMore && !loading) {
      fetchOpportunities(false)
    }
  }, [loadingMore, hasMore, loading, fetchOpportunities])

  // Intersection Observer for infinite scroll
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasMore && !loadingMore && !loading) {
          loadMore()
        }
      },
      { threshold: 0.1, rootMargin: '100px' }
    )

    if (loadMoreRef.current) {
      observer.observe(loadMoreRef.current)
    }

    return () => observer.disconnect()
  }, [hasMore, loadingMore, loading, loadMore])

  // Client-side filtering for instant results
  const filteredOpportunities = useMemo(() => {
    const selectedLeagues = new Set(filters.sports.map(normalizeLeagueName))
    return opportunities.filter(opp => {
      // Filter by bookmaker
      if (filters.bookmakers.length > 0 && !filters.bookmakers.includes(opp.back_bookmaker_code)) {
        return false
      }

      // Filter by league/competition
      if (selectedLeagues.size > 0 && !selectedLeagues.has(normalizeLeagueName(opp.competition_name))) {
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

  // Poll job status until complete
  const pollJobStatus = async (jobId: string, maxAttempts = 40): Promise<boolean> => {
    for (let attempt = 0; attempt < maxAttempts; attempt++) {
      try {
        console.log(`[OddsMatcherClient] Poll attempt ${attempt + 1}/${maxAttempts} for job ${jobId}`)
        const response = await fetch(`/api/proxy/odds/refresh/status?job_id=${encodeURIComponent(jobId)}`)

        if (!response.ok) {
          // 404 means job expired or doesn't exist - could mean it completed
          if (response.status === 404) {
            console.log(`[OddsMatcherClient] Job ${jobId} not found (may have completed and expired)`)
            // Job completed and expired - treat as success
            return true
          }
          console.warn(`[OddsMatcherClient] Job status check failed: ${response.status}`)
          return false
        }

        const status = await response.json()
        console.log(`[OddsMatcherClient] Job status:`, status)

        // Update UI with current status
        if (status.status === 'running') {
          setScrapeStatus(status.message || 'Fetching odds in progress...')
        } else if (status.status === 'pending') {
          setScrapeStatus('Queued, waiting to start...')
        }

        // Check if job is complete
        if (status.status === 'success') {
          setScrapeStatus(null)
          return true
        }

        if (status.status === 'failed') {
          console.error('[OddsMatcherClient] Odds refresh job failed:', status.errors)
          setScrapeStatus(null)
          return false
        }

        // Wait 3 seconds before next poll
        await new Promise(resolve => setTimeout(resolve, 3000))
      } catch (err) {
        console.error('[OddsMatcherClient] Error polling job status:', err)
        return false
      }
    }

    console.warn('[OddsMatcherClient] Job polling timed out after max attempts')
    setScrapeStatus(null)
    return false
  }

  const refreshOdds = async () => {
    setLoading(true)
    setError(null)
    setScrapeStatus(null)

    try {
      const response = await fetch('/api/proxy/odds/refresh', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ force: false })
      })

      if (!response.ok) {
        // 429 = rate limited - silently continue to fetch cached odds
        if (response.status === 429) {
          console.log('[OddsMatcherClient] Rate limited, fetching cached odds instead')
          await fetchOpportunities(true)
          return
        }
        throw new Error('Failed to refresh odds')
      }

      const refreshData = await response.json()
      console.log('[OddsMatcherClient] Refresh response:', refreshData)

      // If cache was used, data is already fresh - just fetch opportunities
      if (refreshData.used_cache === true) {
        console.log('[OddsMatcherClient] Cache hit - skipping poll')
        await fetchOpportunities(true)
        return
      }

      // Fresh refresh was queued - poll for completion
      console.log('[OddsMatcherClient] Cache miss - will poll for job:', refreshData.job_id)
      if (refreshData.job_id) {
        setShowPerformanceNotice(true)
        setScrapeStatus('Starting refresh...')

        const success = await pollJobStatus(refreshData.job_id)

        setShowPerformanceNotice(false)

        if (!success) {
          // Still fetch cached odds even if refresh failed
          console.warn('[OddsMatcherClient] Refresh may have failed, fetching cached odds')
        }
      }

      // Fetch opportunities (fresh or cached)
      await fetchOpportunities(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
      setScrapeStatus(null)
      setShowPerformanceNotice(false)
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
          {totalCount > 0 && (
            <span className="ml-4">
              Showing {filteredOpportunities.length} of {totalCount} opportunities
              {hasMore && ' (scroll for more)'}
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

      {/* Scrape Progress Notice */}
      {showPerformanceNotice && (
        <div className="bg-blue-50 border border-blue-200 text-blue-800 px-4 py-3 rounded-lg">
          <div className="flex items-center gap-3">
            <div className="flex-shrink-0">
              <svg className="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
            </div>
            <div>
              <p className="font-medium">
                {scrapeStatus || 'Fetching latest odds from bookmakers...'}
              </p>
              <p className="text-sm text-blue-600 mt-1">
                This typically takes 60-90 seconds
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

      {/* Infinite Scroll Trigger */}
      <div ref={loadMoreRef} className="h-10 flex items-center justify-center">
        {loadingMore && (
          <div className="flex items-center gap-2 text-gray-500">
            <svg className="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <span>Loading more...</span>
          </div>
        )}
        {!hasMore && opportunities.length > 0 && !loading && (
          <span className="text-gray-400 text-sm">No more opportunities</span>
        )}
      </div>

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
