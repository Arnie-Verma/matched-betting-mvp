/**
 * Calculator utility functions for matched betting calculations.
 * All calculations use standard decimal odds format.
 */

// ============================================
// BACK/LAY CALCULATOR
// ============================================

export interface BackLayResult {
  layStake: number
  layLiability: number
  profitIfBackWins: number
  profitIfLayWins: number
  qualifyingLoss: number
  pnlPercentage: number
}

/**
 * Calculate lay stake and outcomes for a back/lay matched bet.
 *
 * @param backStake - Amount to bet at bookmaker
 * @param backOdds - Decimal odds at bookmaker (e.g., 2.5)
 * @param layOdds - Decimal odds at exchange (e.g., 2.6)
 * @param commission - Exchange commission as decimal (e.g., 0.05 for 5%)
 * @param isBonus - Whether this is a bonus/free bet (stake not returned)
 */
export function calculateBackLay(
  backStake: number,
  backOdds: number,
  layOdds: number,
  commission: number,
  isBonus: boolean = false
): BackLayResult {
  // Lay stake formula differs for bonus bets
  const layStake = isBonus
    ? (backStake * (backOdds - 1)) / (layOdds - commission)
    : (backStake * backOdds) / (layOdds - commission)

  const layLiability = layStake * (layOdds - 1)

  // Back winnings (for bonus bets, stake isn't returned)
  const backWinnings = isBonus
    ? backStake * (backOdds - 1)
    : backStake * (backOdds - 1)

  // Profit if back bet wins = back winnings - lay liability
  const profitIfBackWins = backWinnings - layLiability

  // Profit if lay wins = lay stake after commission - back stake lost
  const layProfit = layStake * (1 - commission)
  const backLoss = isBonus ? 0 : backStake
  const profitIfLayWins = layProfit - backLoss

  // Average outcome (qualifying loss for normal bets, profit for bonus)
  const qualifyingLoss = (profitIfBackWins + profitIfLayWins) / 2
  const pnlPercentage = (qualifyingLoss / backStake) * 100

  return {
    layStake: round2(layStake),
    layLiability: round2(layLiability),
    profitIfBackWins: round2(profitIfBackWins),
    profitIfLayWins: round2(profitIfLayWins),
    qualifyingLoss: round2(qualifyingLoss),
    pnlPercentage: round2(pnlPercentage)
  }
}

// ============================================
// DUTCHING CALCULATOR
// ============================================

export interface DutchingOutcome {
  odds: number
  stake: number
  profit: number
}

export interface DutchingResult {
  totalStake: number
  outcomes: DutchingOutcome[]
  profitPerOutcome: number
  isValid: boolean
  overround: number
}

/**
 * Calculate stake distribution for dutching (backing multiple outcomes).
 * Dutching ensures equal profit regardless of which outcome wins.
 *
 * @param totalStake - Total amount to distribute across outcomes
 * @param odds - Array of decimal odds for each outcome
 */
export function calculateDutching(
  totalStake: number,
  odds: number[]
): DutchingResult {
  if (odds.length < 2 || odds.some(o => o < 1.01)) {
    return {
      totalStake,
      outcomes: [],
      profitPerOutcome: 0,
      isValid: false,
      overround: 0
    }
  }

  // Calculate implied probabilities and overround
  const impliedProbs = odds.map(o => 1 / o)
  const overround = (impliedProbs.reduce((a, b) => a + b, 0) - 1) * 100

  // Calculate stakes for equal profit on each outcome
  // Formula: stake_i = totalStake / (odds_i * sum(1/odds_j))
  const sumInverseOdds = impliedProbs.reduce((a, b) => a + b, 0)

  const outcomes: DutchingOutcome[] = odds.map(o => {
    const stake = totalStake / (o * sumInverseOdds)
    const profit = stake * o - totalStake // Return minus total stake
    return {
      odds: o,
      stake: round2(stake),
      profit: round2(profit)
    }
  })

  // Profit is the same for each outcome if math is correct
  const profitPerOutcome = outcomes.length > 0 ? outcomes[0].profit : 0

  // Valid if profit is positive (arbitrage) or acceptable loss
  const isValid = outcomes.every(o => Math.abs(o.profit - profitPerOutcome) < 0.01)

  return {
    totalStake,
    outcomes,
    profitPerOutcome: round2(profitPerOutcome),
    isValid,
    overround: round2(overround)
  }
}

// ============================================
// TRUE ODDS CALCULATOR
// ============================================

export interface TrueOddsResult {
  trueOdds: number[]
  impliedProbs: number[]
  fairProbs: number[]
  overround: number
  margin: number
}

/**
 * Calculate true odds by removing bookmaker margin.
 *
 * @param odds - Array of decimal odds for all outcomes in a market
 */
export function calculateTrueOdds(odds: number[]): TrueOddsResult {
  if (odds.length < 2 || odds.some(o => o < 1.01)) {
    return {
      trueOdds: [],
      impliedProbs: [],
      fairProbs: [],
      overround: 0,
      margin: 0
    }
  }

  // Calculate implied probabilities
  const impliedProbs = odds.map(o => (1 / o) * 100)
  const totalProb = impliedProbs.reduce((a, b) => a + b, 0)

  // Overround is how much over 100% the probabilities sum to
  const overround = totalProb - 100
  const margin = overround / totalProb * 100 // As percentage of total

  // Fair probabilities (normalized to 100%)
  const fairProbs = impliedProbs.map(p => (p / totalProb) * 100)

  // True odds (fair odds without margin)
  const trueOdds = fairProbs.map(p => 100 / p)

  return {
    trueOdds: trueOdds.map(o => round2(o)),
    impliedProbs: impliedProbs.map(p => round2(p)),
    fairProbs: fairProbs.map(p => round2(p)),
    overround: round2(overround),
    margin: round2(margin)
  }
}

// ============================================
// MULTI CALCULATOR (EV for multi-leg bets)
// ============================================

export interface MultiLeg {
  odds: number
  probability?: number // If not provided, calculated from odds
}

export interface MultiResult {
  combinedOdds: number
  combinedProbability: number
  expectedValue: number
  outcomes: {
    name: string
    probability: number
    profitLoss: number
  }[]
  isSGM: boolean
  anyLegFail: boolean
  bonusRetention: number
}

/**
 * Calculate expected value for multi-leg bets.
 * Supports SGM (Same Game Multi) and any-leg-fail promotions.
 *
 * @param stake - Amount to bet
 * @param legs - Array of legs with odds
 * @param overround - Bookmaker overround percentage (default 5%)
 * @param bonusRetention - Expected retention % if bonus refund (default 70%)
 * @param anyLegFail - Whether promo refunds if exactly one leg fails
 * @param isSGM - Whether this is a Same Game Multi (correlated legs)
 */
export function calculateMulti(
  stake: number,
  legs: MultiLeg[],
  overround: number = 5,
  bonusRetention: number = 70,
  anyLegFail: boolean = false,
  isSGM: boolean = false
): MultiResult {
  if (legs.length < 1 || legs.some(l => l.odds < 1.01)) {
    return {
      combinedOdds: 0,
      combinedProbability: 0,
      expectedValue: 0,
      outcomes: [],
      isSGM,
      anyLegFail,
      bonusRetention
    }
  }

  // Calculate fair probability for each leg
  const fairProbs = legs.map(leg => {
    // Remove overround to get fair probability
    const impliedProb = 1 / leg.odds
    const fairProb = impliedProb / (1 + overround / 100)
    return leg.probability ?? fairProb
  })

  // Combined odds = product of all leg odds
  const combinedOdds = legs.reduce((acc, leg) => acc * leg.odds, 1)

  // Combined probability = product of all probabilities (assuming independence)
  // For SGM, legs may be correlated - user can adjust overround
  const combinedProbability = fairProbs.reduce((acc, p) => acc * p, 1)

  // Calculate outcomes
  const outcomes: MultiResult['outcomes'] = []

  // Outcome 1: All legs win
  const allWinProfit = stake * (combinedOdds - 1)
  outcomes.push({
    name: 'All legs win',
    probability: combinedProbability * 100,
    profitLoss: round2(allWinProfit)
  })

  // Calculate probability of exactly one leg failing
  let oneLegFailProb = 0
  for (let i = 0; i < fairProbs.length; i++) {
    const failProb = 1 - fairProbs[i]
    const othersWinProb = fairProbs
      .filter((_, j) => j !== i)
      .reduce((acc, p) => acc * p, 1)
    oneLegFailProb += failProb * othersWinProb
  }

  // Bonus bet value for refund scenarios
  const bonusValue = stake * (bonusRetention / 100)

  if (anyLegFail) {
    // Any Leg Fail promo ON: ALL failure scenarios get bonus refund
    // Combined into single "Any leg fails (refund)" outcome
    const anyFailProb = 1 - combinedProbability
    outcomes.push({
      name: 'Any leg fails (refund)',
      probability: anyFailProb * 100,
      profitLoss: round2(bonusValue - stake) // Net position after refund
    })
  } else {
    // Default: Show detailed breakdown
    // One leg fails = gets refund (standard promo behavior)
    outcomes.push({
      name: 'One leg fails (refund)',
      probability: oneLegFailProb * 100,
      profitLoss: round2(bonusValue - stake) // Net position after refund
    })

    // More than one leg fails = lose stake (no refund)
    const moreThanOneFailProb = 1 - combinedProbability - oneLegFailProb
    outcomes.push({
      name: 'More than one leg fails',
      probability: Math.max(0, moreThanOneFailProb * 100),
      profitLoss: round2(-stake)
    })
  }

  // Calculate expected value
  const expectedValue = outcomes.reduce((acc, outcome) => {
    return acc + (outcome.probability / 100) * outcome.profitLoss
  }, 0)

  return {
    combinedOdds: round2(combinedOdds),
    combinedProbability: round2(combinedProbability * 100),
    expectedValue: round2(expectedValue),
    outcomes,
    isSGM,
    anyLegFail,
    bonusRetention
  }
}

// ============================================
// LONG TERM EV CALCULATOR (Monte Carlo)
// ============================================

export interface LongTermEVResult {
  expectedProfit: number
  expectedProfitPerBet: number
  variance: number
  standardDeviation: number
  worstCase: number
  bestCase: number
  probabilityOfProfit: number
  simulations: number[]
}

/**
 * Simulate long-term expected value over multiple bets.
 * Uses Monte Carlo simulation for variance analysis.
 *
 * @param numBets - Number of bets to simulate
 * @param stake - Stake per bet
 * @param legs - Multi legs (or single bet as one leg)
 * @param overround - Bookmaker overround percentage
 * @param bonusRetention - Bonus bet retention percentage
 * @param anyLegFail - Whether any-leg-fail promo applies
 * @param isSGM - Whether Same Game Multi
 * @param numSimulations - Number of Monte Carlo runs (default 1000)
 */
export function calculateLongTermEV(
  numBets: number,
  stake: number,
  legs: MultiLeg[],
  overround: number = 5,
  bonusRetention: number = 70,
  anyLegFail: boolean = false,
  isSGM: boolean = false,
  numSimulations: number = 1000
): LongTermEVResult {
  // Get per-bet EV
  const perBetResult = calculateMulti(
    stake,
    legs,
    overround,
    bonusRetention,
    anyLegFail,
    isSGM
  )

  const expectedProfitPerBet = perBetResult.expectedValue
  const expectedProfit = expectedProfitPerBet * numBets

  // Monte Carlo simulation
  const simResults: number[] = []

  for (let sim = 0; sim < numSimulations; sim++) {
    let totalProfit = 0

    for (let bet = 0; bet < numBets; bet++) {
      const random = Math.random()
      let cumProb = 0

      for (const outcome of perBetResult.outcomes) {
        cumProb += outcome.probability / 100
        if (random < cumProb) {
          totalProfit += outcome.profitLoss
          break
        }
      }
    }

    simResults.push(totalProfit)
  }

  // Calculate statistics
  simResults.sort((a, b) => a - b)
  const variance = calculateVariance(simResults)
  const standardDeviation = Math.sqrt(variance)
  const worstCase = simResults[Math.floor(numSimulations * 0.05)] // 5th percentile
  const bestCase = simResults[Math.floor(numSimulations * 0.95)] // 95th percentile
  const profitableCount = simResults.filter(r => r > 0).length
  const probabilityOfProfit = (profitableCount / numSimulations) * 100

  return {
    expectedProfit: round2(expectedProfit),
    expectedProfitPerBet: round2(expectedProfitPerBet),
    variance: round2(variance),
    standardDeviation: round2(standardDeviation),
    worstCase: round2(worstCase),
    bestCase: round2(bestCase),
    probabilityOfProfit: round2(probabilityOfProfit),
    simulations: simResults.map(r => round2(r))
  }
}

// ============================================
// UTILITY FUNCTIONS
// ============================================

function round2(num: number): number {
  return Math.round(num * 100) / 100
}

function calculateVariance(numbers: number[]): number {
  const n = numbers.length
  if (n === 0) return 0
  const mean = numbers.reduce((a, b) => a + b, 0) / n
  const squaredDiffs = numbers.map(x => Math.pow(x - mean, 2))
  return squaredDiffs.reduce((a, b) => a + b, 0) / n
}

/**
 * Format currency for display
 */
export function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('en-AU', {
    style: 'currency',
    currency: 'AUD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  }).format(amount)
}

/**
 * Format percentage for display
 */
export function formatPercentage(pct: number, showSign: boolean = true): string {
  const sign = showSign && pct >= 0 ? '+' : ''
  return `${sign}${pct.toFixed(2)}%`
}
