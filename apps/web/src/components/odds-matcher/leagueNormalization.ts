// Normalization helpers for league/competition names so UI filters match API data

const COMPETITION_ALIAS_MAP: Record<string, string> = {
  // Soccer
  'epl': 'epl',
  'premier league': 'epl',
  'english premier league': 'epl',
  'a-league': 'a-league',
  'a league': 'a-league',
  'a-league men': 'a-league',
  'a-league women': 'a-league',
  'la liga': 'la liga',
  'spanish la liga': 'la liga',
  'spanish la-liga': 'la liga',
  'bundesliga': 'bundesliga',
  'german bundesliga': 'bundesliga',
  'german bundesliga women': 'bundesliga',
  'serie a': 'serie a',
  'italian serie a': 'serie a',
  'ligue 1': 'ligue 1',
  'french ligue 1': 'ligue 1',
  'mls': 'mls',
  'major league soccer': 'mls',
  'ucl': 'ucl',
  'champions league': 'ucl',
  'uefa champions league': 'ucl',

  // Football codes
  'afl': 'afl',
  'nrl': 'nrl',

  // Basketball
  'nba': 'nba',
  'nbl': 'nbl',

  // Ice hockey
  'nhl': 'nhl',

  // Boxing
  'boxing': 'boxing',
  'upcoming fights': 'boxing',
}

export const LEAGUE_DISPLAY_NAMES: Record<string, string> = {
  'a-league': 'A-League',
  'afl': 'AFL',
  'boxing': 'Boxing',
  'epl': 'EPL',
  'ligue 1': 'French Ligue 1',
  'bundesliga': 'German Bundesliga',
  'serie a': 'Italian Serie A',
  'mls': 'Major League Soccer',
  'nba': 'NBA',
  'nbl': 'NBL',
  'nhl': 'NHL',
  'nrl': 'NRL',
  'la liga': 'Spanish La Liga',
  'ucl': 'UEFA Champions League',
}

export const LEAGUE_ORDER: string[] = [
  'a-league',
  'afl',
  'boxing',
  'epl',
  'ligue 1',
  'bundesliga',
  'serie a',
  'mls',
  'nba',
  'nbl',
  'nhl',
  'nrl',
  'la liga',
  'ucl',
]

export function normalizeLeagueName(name: string): string {
  const key = name.trim().toLowerCase()
  return COMPETITION_ALIAS_MAP[key] ?? key
}
