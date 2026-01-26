'use client'

import { OddsMatch } from './OddsMatcherClient'
import { TrendingUp, TrendingDown } from 'lucide-react'

interface OddsTableProps {
  opportunities: OddsMatch[]
  loading: boolean
  backgroundRefreshing?: boolean
  backgroundMessage?: string | null
  onSelectOdds: (odds: OddsMatch) => void
}

export function OddsTable({
  opportunities,
  loading,
  backgroundRefreshing = false,
  backgroundMessage,
  onSelectOdds
}: OddsTableProps) {
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
      <div className="bg-card rounded-lg border shadow-sm p-12">
        <div className="flex flex-col items-center justify-center text-muted-foreground">
          <div className="w-12 h-12 border-4 border-primary border-t-transparent rounded-full animate-spin mb-4"></div>
          <p>Loading opportunities...</p>
        </div>
      </div>
    )
  }

  if (!loading && opportunities.length === 0) {
    if (backgroundRefreshing) {
      return (
        <div className="bg-card rounded-lg border shadow-sm p-12">
          <div className="flex flex-col items-center justify-center text-muted-foreground text-center">
            <div className="w-12 h-12 border-4 border-primary border-t-transparent rounded-full animate-spin mb-4"></div>
            <p className="text-lg font-medium mb-2 text-foreground/80">
              {backgroundMessage || 'Fetching latest odds...'}
            </p>
            <p className="text-sm">
              No cached opportunities yet. This typically takes 60-90 seconds.
            </p>
          </div>
        </div>
      )
    }
    return (
      <div className="bg-card rounded-lg border shadow-sm p-12">
        <div className="text-center text-muted-foreground">
          <p className="text-lg font-medium mb-2">No opportunities found</p>
          <p className="text-sm">Try adjusting your filters or refresh the odds</p>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-card rounded-lg border shadow-sm overflow-hidden">
      {/* Desktop Table */}
      <div className="hidden lg:block overflow-x-auto">
        <table className="w-full">
          <thead className="bg-muted border-b">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-semibold text-foreground/80 uppercase tracking-wider">
                Event
              </th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-foreground/80 uppercase tracking-wider">
                Selection
              </th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-foreground/80 uppercase tracking-wider">
                Bookmaker
              </th>
              <th className="px-4 py-3 text-center text-xs font-semibold text-foreground/80 uppercase tracking-wider">
                Back Odds
              </th>
              <th className="px-4 py-3 text-center text-xs font-semibold text-foreground/80 uppercase tracking-wider">
                Lay Odds
              </th>
              <th className="px-4 py-3 text-center text-xs font-semibold text-foreground/80 uppercase tracking-wider">
                Liquidity
              </th>
              <th className="px-4 py-3 text-right text-xs font-semibold text-foreground/80 uppercase tracking-wider">
                PnL
              </th>
              <th className="px-4 py-3 text-center text-xs font-semibold text-foreground/80 uppercase tracking-wider">
                Action
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {opportunities.map((opp) => (
              <tr
                key={`${opp.event_id}-${opp.selection_id}-${opp.back_bookmaker_code}`}
                className="hover:bg-muted transition-colors"
              >
                <td className="px-4 py-4">
                  <div>
                    <div className="font-medium text-foreground text-sm">{opp.event_name}</div>
                    <div className="text-xs text-muted-foreground">
                      {opp.sport_name} · {opp.competition_name}
                    </div>
                    <div className="text-xs text-muted-foreground/60 mt-1">
                      in {formatDate(opp.event_start_time)}
                    </div>
                  </div>
                </td>
                <td className="px-4 py-4">
                  <div className="text-sm font-medium text-foreground">{opp.selection_name}</div>
                  <div className="text-xs text-muted-foreground">{opp.market_name}</div>
                </td>
                <td className="px-4 py-4">
                  <div className="text-sm font-medium text-foreground">{opp.back_bookmaker_name}</div>
                  <div className="text-xs text-muted-foreground">vs Betfair</div>
                </td>
                <td className="px-4 py-4 text-center">
                  <span className="text-sm font-semibold text-[var(--profit)]">{formatOdds(opp.back_odds)}</span>
                </td>
                <td className="px-4 py-4 text-center">
                  <span className="text-sm font-semibold text-destructive">{formatOdds(opp.lay_odds)}</span>
                </td>
                <td className="px-4 py-4 text-center">
                  {opp.lay_liquidity ? (
                    <span className="text-sm text-foreground/80">{formatCurrency(opp.lay_liquidity)}</span>
                  ) : (
                    <span className="text-xs text-muted-foreground/60">N/A</span>
                  )}
                </td>
                <td className="px-4 py-4 text-right">
                  <div className="flex flex-col items-end justify-center gap-1 leading-tight">
                    <div className="flex items-center gap-2">
                      {opp.pnl_percentage >= 0 ? (
                        <TrendingUp className="w-4 h-4 text-[var(--profit)]" />
                      ) : (
                        <TrendingDown className="w-4 h-4 text-destructive" />
                      )}
                      <span className={`text-sm font-semibold ${opp.pnl_percentage >= 0 ? 'text-[var(--profit)]' : 'text-destructive'}`}>
                        {formatCurrency(opp.qualifying_loss)}
                      </span>
                    </div>
                    <div className={`text-xs ${opp.pnl_percentage >= 0 ? 'text-[var(--profit)]' : 'text-destructive'}`}>
                      {formatPercentage(opp.pnl_percentage)}
                    </div>
                  </div>
                </td>
                <td className="px-4 py-4 text-center">
                  <button
                    onClick={() => onSelectOdds(opp)}
                    className="bg-primary text-white px-3 py-1 rounded text-sm font-medium hover:bg-primary/90 transition-colors"
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
      <div className="lg:hidden divide-y divide-border">
        {opportunities.map((opp) => (
          <div key={`${opp.event_id}-${opp.selection_id}-${opp.back_bookmaker_code}`} className="p-4 space-y-3">
            {/* Event Info */}
            <div>
              <div className="font-medium text-foreground">{opp.event_name}</div>
              <div className="text-xs text-muted-foreground">
                {opp.sport_name} · {opp.competition_name} · in {formatDate(opp.event_start_time)}
              </div>
            </div>

            {/* Selection and Bookmaker */}
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <div className="text-xs text-muted-foreground mb-1">Selection</div>
                <div className="font-medium">{opp.selection_name}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground mb-1">Bookmaker</div>
                <div className="font-medium">{opp.back_bookmaker_name}</div>
              </div>
            </div>

            {/* Odds */}
            <div className="grid grid-cols-3 gap-3 text-sm">
              <div>
                <div className="text-xs text-muted-foreground mb-1">Back</div>
                <div className="font-semibold text-[var(--profit)]">{formatOdds(opp.back_odds)}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground mb-1">Lay</div>
                <div className="font-semibold text-destructive">{formatOdds(opp.lay_odds)}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground mb-1">PnL</div>
                <div className="flex flex-col items-start leading-tight gap-1">
                  <div className="flex items-center gap-2">
                    {opp.pnl_percentage >= 0 ? (
                      <TrendingUp className="w-4 h-4 text-[var(--profit)]" />
                    ) : (
                      <TrendingDown className="w-4 h-4 text-destructive" />
                    )}
                    <span className={`text-sm font-semibold ${opp.pnl_percentage >= 0 ? 'text-[var(--profit)]' : 'text-destructive'}`}>
                      {formatCurrency(opp.qualifying_loss)}
                    </span>
                  </div>
                  <span className={`text-xs ${opp.pnl_percentage >= 0 ? 'text-[var(--profit)]' : 'text-destructive'}`}>
                    {formatPercentage(opp.pnl_percentage)}
                  </span>
                </div>
              </div>
            </div>

            {/* Action */}
            <div className="flex items-center justify-end">
              <button
                onClick={() => onSelectOdds(opp)}
                className="bg-primary text-white px-4 py-2 rounded font-medium hover:bg-primary/90 transition-colors"
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
