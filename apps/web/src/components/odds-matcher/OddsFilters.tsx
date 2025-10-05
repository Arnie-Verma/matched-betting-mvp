'use client'

import { useState } from 'react'
import { Search } from 'lucide-react'
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
  onSearch: () => void
}

export function OddsFilters({ filters, onFiltersChange, onSearch }: OddsFiltersProps) {
  const [showAdvanced, setShowAdvanced] = useState(false)

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

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    onSearch()
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
          <form onSubmit={handleSearchSubmit} className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              id="search"
              type="text"
              placeholder="Team name or event..."
              value={filters.search}
              onChange={handleSearchChange}
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </form>
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
            <div className="flex flex-wrap gap-2">
              {availableBookmakers.map(bookmaker => (
                <button
                  key={bookmaker.code}
                  onClick={() => handleBookmakerToggle(bookmaker.code)}
                  className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                    filters.bookmakers.includes(bookmaker.code)
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }`}
                >
                  {bookmaker.name}
                </button>
              ))}
            </div>
          </div>

          {/* Sport Filter */}
          <div>
            <Label className="text-sm font-medium text-gray-700 mb-2 block">
              Sports
            </Label>
            <div className="flex flex-wrap gap-2">
              {availableSports.map(sport => (
                <button
                  key={sport.code}
                  onClick={() => {
                    const current = filters.sports
                    const updated = current.includes(sport.code)
                      ? current.filter(s => s !== sport.code)
                      : [...current, sport.code]
                    onFiltersChange({ ...filters, sports: updated })
                  }}
                  className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                    filters.sports.includes(sport.code)
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }`}
                >
                  {sport.name}
                </button>
              ))}
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

      {/* Search Button */}
      <div>
        <button
          onClick={onSearch}
          className="w-full md:w-auto bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 transition-colors font-medium"
        >
          Search Opportunities
        </button>
      </div>
    </div>
  )
}
