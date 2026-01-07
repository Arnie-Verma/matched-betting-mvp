'use client'

import { useState, useEffect, useMemo, useRef, useCallback } from 'react'
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
  const [debouncedSearch, setDebouncedSearch] = useState('')

  const [selectedOdds, setSelectedOdds] = useState<OddsMatch | null>(null)

  // Refs for infinite scroll
  const hasInitialized = useRef(false)
  const skipInitialFilterFetch = useRef(true)
  const filtersRef = useRef(filters)
  const requestToken = useRef(0)
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

  // Debounce search input to avoid rapid refetches
  useEffect(() => {
    const handle = setTimeout(() => setDebouncedSearch(filters.search.trim()), 300)
    return () => clearTimeout(handle)
  }, [filters.search])

  useEffect(() => {
    filtersRef.current = filters
  }, [filters])

  const fetchOpportunities = useCallback(async (reset = false) => {
    const token = reset ? ++requestToken.current : requestToken.current
    const offset = reset ? 0 : currentOffset.current
    const currentFilters = filtersRef.current

    if (reset) {
      setLoading(true)
      setLoadingMore(false)
      currentOffset.current = 0
      setOpportunities([])
      setTotalCount(0)
      setHasMore(false)
    } else {
      setLoadingMore(true)
    }
    setError(null)

    try {
      const params = new URLSearchParams()
      params.append('stake', debouncedStake.toString())
      params.append('bet_type', currentFilters.betType)
      params.append('limit', PAGE_SIZE.toString())
      params.append('offset', offset.toString())
      if (currentFilters.bookmakers.length > 0) {
        params.append('bookmaker_codes', currentFilters.bookmakers.join(','))
      }
      if (currentFilters.sports.length > 0) {
        params.append('competition_codes', currentFilters.sports.join(','))
      }
      if (debouncedSearch) {
        params.append('search', debouncedSearch)
      }

      const response = await fetch(`/api/proxy/odds/matcher?${params.toString()}`)

      if (!response.ok) {
        let message = `Failed to fetch odds (${response.status})`
        const responseText = await response.text()
        if (responseText) {
          try {
            const errorData = JSON.parse(responseText) as { detail?: string; error?: string }
            message = errorData.detail || errorData.error || message
          } catch {
            message = responseText.slice(0, 200)
          }
        }
        throw new Error(message)
      }

      const data: PaginatedResponse = await response.json()

      if (token !== requestToken.current) {
        return
      }

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
      if (token !== requestToken.current) {
        return
      }
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      // Always clear loading state, even for stale responses
      setLoading(false)
      setLoadingMore(false)
      // But don't update UI if this is a stale response
      if (token !== requestToken.current) {
        return
      }
    }
  }, [debouncedStake, debouncedSearch])

  // Refetch opportunities when filters change (bookmaker/league/search/stake/bet type)
  useEffect(() => {
    if (skipInitialFilterFetch.current) {
      skipInitialFilterFetch.current = false
      return
    }
    fetchOpportunities(true)
  }, [debouncedStake, filters.betType, filters.bookmakers, filters.sports, debouncedSearch, fetchOpportunities])

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
    if (!filters.search) {
      return opportunities
    }

    const searchLower = filters.search.toLowerCase()
    return opportunities.filter(opp => {
      const matchesEvent = opp.event_name.toLowerCase().includes(searchLower)
      const matchesSelection = opp.selection_name.toLowerCase().includes(searchLower)
      return matchesEvent || matchesSelection
    })
  }, [opportunities, filters.search])

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
    // Show banner immediately to indicate refresh is starting
    setError(null)
    setScrapeStatus('Checking for latest odds...')
    setShowPerformanceNotice(true)

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
          setShowPerformanceNotice(false)
          await fetchOpportunities(true)
          return
        }
        let message = `Failed to refresh odds (${response.status})`
        const responseText = await response.text()
        if (responseText) {
          try {
            const errorData = JSON.parse(responseText) as { detail?: string; error?: string }
            message = errorData.detail || errorData.error || message
          } catch {
            message = responseText.slice(0, 200)
          }
        }
        setError(message)
        setScrapeStatus(null)
        setShowPerformanceNotice(false)
        await fetchOpportunities(true)
        return
      }

      const refreshData = await response.json()
      console.log('[OddsMatcherClient] Refresh response:', refreshData)

      // If cache was used, data is already fresh - hide banner and fetch opportunities
      if (refreshData.used_cache === true) {
        console.log('[OddsMatcherClient] Cache hit - fetching cached odds')
        setShowPerformanceNotice(false)
        await fetchOpportunities(true)
        return
      }

      // Fresh refresh was queued - update banner and poll for completion
      console.log('[OddsMatcherClient] Cache miss - will poll for job:', refreshData.job_id)
      if (refreshData.job_id) {
        setScrapeStatus('Fetching latest odds from bookmakers...')

        const success = await pollJobStatus(refreshData.job_id)

        if (!success) {
          // Still fetch cached odds even if refresh failed
          console.warn('[OddsMatcherClient] Refresh may have failed, fetching cached odds')
        }
      }

      // Hide banner before fetching opportunities
      setShowPerformanceNotice(false)

      // Fetch opportunities (fresh or cached)
      await fetchOpportunities(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
      setScrapeStatus(null)
      setShowPerformanceNotice(false)
      await fetchOpportunities(true)
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
        <div className="text-sm text-muted-foreground">
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
          className="flex items-center gap-2 bg-primary text-white px-4 py-2 rounded-lg hover:bg-primary/90 disabled:bg-muted disabled:cursor-not-allowed transition-colors"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          REFRESH ODDS
        </button>
      </div>

      {/* Scrape Progress Notice */}
      {showPerformanceNotice && (
        <div className="bg-secondary border border-[var(--accent-soft)] text-[var(--brand)] px-4 py-3 rounded-lg">
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
              <p className="text-sm text-primary/90 mt-1">
                This typically takes 60-90 seconds
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Error Display */}
      {error && (
        <div className="bg-[var(--danger-soft)] border border-[var(--danger-border)] text-destructive px-4 py-3 rounded-lg">
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
          <div className="flex items-center gap-2 text-muted-foreground">
            <svg className="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <span>Loading more...</span>
          </div>
        )}
        {!hasMore && opportunities.length > 0 && !loading && (
          <span className="text-muted-foreground/60 text-sm">No more opportunities</span>
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
