'use client'

import { useState, useRef, useEffect } from 'react'
import { Search, ChevronDown } from 'lucide-react'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'

interface OddsFiltersProps {
  filters: {
    stake: number
    betType: 'normal' | 'bonus'
    bookmakers: string[]
    sports: string[]
    competitions: number[]
    search: string
  }
  onFiltersChange: (filters: any) => void
}

interface Bookmaker {
  code: string
  name: string
}

interface Competition {
  id: number
  short_name: string
  full_name: string
}

export function OddsFilters({ filters, onFiltersChange }: OddsFiltersProps) {
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [showBookmakers, setShowBookmakers] = useState(false)
  const [showLeagues, setShowLeagues] = useState(false)
  const [availableBookmakers, setAvailableBookmakers] = useState<Bookmaker[]>([])
  const [availableLeagues, setAvailableLeagues] = useState<Competition[]>([])
  const [bookmakerSearch, setBookmakerSearch] = useState('')
  const [leagueSearch, setLeagueSearch] = useState('')
  const bookmakersRef = useRef<HTMLDivElement>(null)
  const leaguesRef = useRef<HTMLDivElement>(null)

  // Fetch available bookmakers and sports on mount
  useEffect(() => {
    const fetchOptions = async () => {
      try {
        // Fetch bookmakers from API
        const bookmakersRes = await fetch('/api/proxy/bookmakers')
        if (bookmakersRes.ok) {
          const bookmakers = await bookmakersRes.json()
          // Sort alphabetically by name
          const sorted = bookmakers
            .map((b: any) => ({ code: b.code, name: b.display_name }))
            .sort((a: Bookmaker, b: Bookmaker) => a.name.localeCompare(b.name))
          setAvailableBookmakers(sorted)
        }

        // Fetch competitions/leagues from API
        const leaguesRes = await fetch('/api/proxy/competitions')
        if (leaguesRes.ok) {
          const leagues = await leaguesRes.json()
          // Sort alphabetically by short_name
          const sorted = leagues
            .map((c: any) => ({ id: c.id, short_name: c.short_name, full_name: c.full_name }))
            .sort((a: Competition, b: Competition) => a.short_name.localeCompare(b.short_name))
          setAvailableLeagues(sorted)
        }
      } catch (error) {
        console.error('Failed to fetch filter options:', error)
      }
    }
    fetchOptions()
  }, [])

  // Close dropdowns when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (bookmakersRef.current && !bookmakersRef.current.contains(event.target as Node)) {
        setShowBookmakers(false)
      }
      if (leaguesRef.current && !leaguesRef.current.contains(event.target as Node)) {
        setShowLeagues(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleStakeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = parseFloat(e.target.value)
    if (!isNaN(value) && value > 0) {
      onFiltersChange({ ...filters, stake: value })
    }
  }

  const handleBetTypeChange = (checked: boolean) => {
    onFiltersChange({ ...filters, betType: checked ? 'bonus' : 'normal' })
  }

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onFiltersChange({ ...filters, search: e.target.value })
  }

  const handleBookmakerToggle = (bookmaker: string) => {
    const current = filters.bookmakers
    const updated = current.includes(bookmaker)
      ? current.filter(b => b !== bookmaker)
      : [...current, bookmaker]
    onFiltersChange({ ...filters, bookmakers: updated })
  }

  // Filter bookmakers by search term
  const filteredBookmakers = availableBookmakers.filter(bookmaker =>
    bookmaker.name.toLowerCase().includes(bookmakerSearch.toLowerCase())
  )

  // Filter leagues by search term
  const filteredLeagues = availableLeagues.filter(league =>
    league.short_name.toLowerCase().includes(leagueSearch.toLowerCase()) ||
    league.full_name.toLowerCase().includes(leagueSearch.toLowerCase())
  )

  return (
    <div className="bg-white rounded-lg border shadow-sm p-6 space-y-4">
      {/* Primary Filters */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Stake Amount */}
        <div>
          <Label htmlFor="stake" className="text-sm font-medium text-gray-700 mb-1 block">
            Stake Amount (AUD)
          </Label>
          <div className="relative">
            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500">$</span>
            <input
              id="stake"
              type="number"
              min="1"
              step="10"
              value={filters.stake}
              onChange={handleStakeChange}
              className="w-full pl-8 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>
        </div>

        {/* Bet Type Toggle */}
        <div>
          <Label htmlFor="bet-type" className="text-sm font-medium text-gray-700 mb-1 block">
            Bet Type
          </Label>
          <div className="flex items-center gap-3 h-10">
            <span className={`text-sm ${!filters.betType || filters.betType === 'normal' ? 'font-semibold text-gray-900' : 'text-gray-500'}`}>
              Normal
            </span>
            <Switch
              id="bet-type"
              checked={filters.betType === 'bonus'}
              onCheckedChange={handleBetTypeChange}
            />
            <span className={`text-sm ${filters.betType === 'bonus' ? 'font-semibold text-gray-900' : 'text-gray-500'}`}>
              Bonus
            </span>
          </div>
          <p className="text-xs text-gray-500 mt-1">
            {filters.betType === 'bonus' ? 'Free bets - no stake returned' : 'Regular bets - stake returned'}
          </p>
        </div>

        {/* Search */}
        <div>
          <Label htmlFor="search" className="text-sm font-medium text-gray-700 mb-1 block">
            Search Events
          </Label>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              id="search"
              type="text"
              placeholder="Team name or event..."
              value={filters.search}
              onChange={handleSearchChange}
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>
        </div>
      </div>

      {/* Advanced Filters Toggle */}
      <button
        onClick={() => setShowAdvanced(!showAdvanced)}
        className="text-sm text-blue-600 hover:text-blue-700 font-medium"
      >
        {showAdvanced ? '− Hide' : '+ Show'} Advanced Filters
      </button>

      {/* Advanced Filters */}
      {showAdvanced && (
        <div className="space-y-4 pt-4 border-t">
          {/* Bookmaker Filter */}
          <div>
            <Label className="text-sm font-medium text-gray-700 mb-2 block">
              Bookmakers (Free tier: TAB & Ladbrokes)
            </Label>
            <div ref={bookmakersRef} className="relative">
              <button
                onClick={() => setShowBookmakers(!showBookmakers)}
                className="w-full md:w-64 flex items-center justify-between gap-2 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
              >
                <span className="text-sm text-gray-700">
                  {filters.bookmakers.length === 0
                    ? 'All Bookmakers'
                    : `${filters.bookmakers.length} selected`}
                </span>
                <ChevronDown className={`w-4 h-4 text-gray-500 transition-transform ${showBookmakers ? 'rotate-180' : ''}`} />
              </button>

              {showBookmakers && (
                <div className="absolute z-10 mt-1 w-full md:w-64 bg-white border border-gray-300 rounded-lg shadow-lg">
                  {/* Search input */}
                  <div className="p-2 border-b border-gray-200 sticky top-0 bg-white">
                    <div className="relative">
                      <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                      <input
                        type="text"
                        placeholder="Search bookmakers..."
                        value={bookmakerSearch}
                        onChange={(e) => setBookmakerSearch(e.target.value)}
                        className="w-full pl-9 pr-3 py-1.5 text-sm border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                        onClick={(e) => e.stopPropagation()}
                      />
                    </div>
                  </div>
                  {/* Bookmaker list */}
                  <div className="max-h-60 overflow-y-auto">
                    {filteredBookmakers.length > 0 ? (
                      filteredBookmakers.map(bookmaker => (
                        <label
                          key={bookmaker.code}
                          className="flex items-center gap-3 px-4 py-2 hover:bg-gray-50 cursor-pointer border-b border-gray-100 last:border-b-0"
                        >
                          <input
                            type="checkbox"
                            checked={filters.bookmakers.includes(bookmaker.code)}
                            onChange={() => handleBookmakerToggle(bookmaker.code)}
                            className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                          />
                          <span className="text-sm text-gray-700">{bookmaker.name}</span>
                        </label>
                      ))
                    ) : (
                      <div className="px-4 py-3 text-sm text-gray-500 text-center">
                        No bookmakers found
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Leagues Filter */}
          <div>
            <Label className="text-sm font-medium text-gray-700 mb-2 block">
              Leagues
            </Label>
            <div ref={leaguesRef} className="relative">
              <button
                onClick={() => setShowLeagues(!showLeagues)}
                className="w-full md:w-64 flex items-center justify-between gap-2 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
              >
                <span className="text-sm text-gray-700">
                  {filters.sports.length === 0
                    ? 'All Leagues'
                    : `${filters.sports.length} selected`}
                </span>
                <ChevronDown className={`w-4 h-4 text-gray-500 transition-transform ${showLeagues ? 'rotate-180' : ''}`} />
              </button>

              {showLeagues && (
                <div className="absolute z-10 mt-1 w-full md:w-64 bg-white border border-gray-300 rounded-lg shadow-lg">
                  {/* Search input */}
                  <div className="p-2 border-b border-gray-200 sticky top-0 bg-white">
                    <div className="relative">
                      <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                      <input
                        type="text"
                        placeholder="Search leagues..."
                        value={leagueSearch}
                        onChange={(e) => setLeagueSearch(e.target.value)}
                        className="w-full pl-9 pr-3 py-1.5 text-sm border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                        onClick={(e) => e.stopPropagation()}
                      />
                    </div>
                  </div>
                  {/* League list */}
                  <div className="max-h-60 overflow-y-auto">
                    {filteredLeagues.length > 0 ? (
                      filteredLeagues.map(league => (
                        <label
                          key={league.id}
                          className="flex items-center gap-3 px-4 py-2 hover:bg-gray-50 cursor-pointer border-b border-gray-100 last:border-b-0"
                        >
                          <input
                            type="checkbox"
                            checked={filters.sports.includes(league.short_name.toLowerCase())}
                            onChange={() => {
                              const current = filters.sports
                              const leagueCode = league.short_name.toLowerCase()
                              const updated = current.includes(leagueCode)
                                ? current.filter(s => s !== leagueCode)
                                : [...current, leagueCode]
                              onFiltersChange({ ...filters, sports: updated })
                            }}
                            className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                          />
                          <span className="text-sm text-gray-700">{league.short_name}</span>
                        </label>
                      ))
                    ) : (
                      <div className="px-4 py-3 text-sm text-gray-500 text-center">
                        No leagues found
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>

        </div>
      )}
    </div>
  )
}
 
