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
    minRating: number | null
  }
  onFiltersChange: (filters: any) => void
}

export function OddsFilters({ filters, onFiltersChange }: OddsFiltersProps) {
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [showBookmakers, setShowBookmakers] = useState(false)
  const [showSports, setShowSports] = useState(false)
  const bookmakersRef = useRef<HTMLDivElement>(null)
  const sportsRef = useRef<HTMLDivElement>(null)

  // Close dropdowns when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (bookmakersRef.current && !bookmakersRef.current.contains(event.target as Node)) {
        setShowBookmakers(false)
      }
      if (sportsRef.current && !sportsRef.current.contains(event.target as Node)) {
        setShowSports(false)
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

  // Available bookmakers (free tier gets TAB and Ladbrokes)
  const availableBookmakers = [
    { code: 'tab', name: 'TAB' },
    { code: 'ladbrokes', name: 'Ladbrokes' }
  ]

  const availableSports = [
    { code: 'afl', name: 'AFL' },
    { code: 'nrl', name: 'NRL' },
    { code: 'cricket', name: 'Cricket' },
    { code: 'tennis', name: 'Tennis' },
    { code: 'soccer', name: 'Soccer' }
  ]

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
                <div className="absolute z-10 mt-1 w-full md:w-64 bg-white border border-gray-300 rounded-lg shadow-lg max-h-64 overflow-y-auto">
                  {availableBookmakers.map(bookmaker => (
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
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Sport Filter */}
          <div>
            <Label className="text-sm font-medium text-gray-700 mb-2 block">
              Sports
            </Label>
            <div ref={sportsRef} className="relative">
              <button
                onClick={() => setShowSports(!showSports)}
                className="w-full md:w-64 flex items-center justify-between gap-2 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
              >
                <span className="text-sm text-gray-700">
                  {filters.sports.length === 0
                    ? 'All Sports'
                    : `${filters.sports.length} selected`}
                </span>
                <ChevronDown className={`w-4 h-4 text-gray-500 transition-transform ${showSports ? 'rotate-180' : ''}`} />
              </button>

              {showSports && (
                <div className="absolute z-10 mt-1 w-full md:w-64 bg-white border border-gray-300 rounded-lg shadow-lg max-h-64 overflow-y-auto">
                  {availableSports.map(sport => (
                    <label
                      key={sport.code}
                      className="flex items-center gap-3 px-4 py-2 hover:bg-gray-50 cursor-pointer border-b border-gray-100 last:border-b-0"
                    >
                      <input
                        type="checkbox"
                        checked={filters.sports.includes(sport.code)}
                        onChange={() => {
                          const current = filters.sports
                          const updated = current.includes(sport.code)
                            ? current.filter(s => s !== sport.code)
                            : [...current, sport.code]
                          onFiltersChange({ ...filters, sports: updated })
                        }}
                        className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                      />
                      <span className="text-sm text-gray-700">{sport.name}</span>
                    </label>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Minimum Rating */}
          <div>
            <Label htmlFor="min-rating" className="text-sm font-medium text-gray-700 mb-1 block">
              Minimum Rating (Quality Score)
            </Label>
            <input
              id="min-rating"
              type="number"
              min="0"
              max="100"
              step="5"
              placeholder="e.g., 80"
              value={filters.minRating ?? ''}
              onChange={(e) => {
                const value = e.target.value ? parseFloat(e.target.value) : null
                onFiltersChange({ ...filters, minRating: value })
              }}
              className="w-full md:w-48 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>
        </div>
      )}
    </div>
  )
}
