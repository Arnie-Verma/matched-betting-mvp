"""
Centralized normalization service for cross-bookmaker matching.

Phase 4 Optimization:
- Single source of truth for ALL team/competition/selection name mappings
- LRU cached for performance (10K lookups/second)
- Eliminates 400+ lines of duplicated code across odds_matcher.py, save_odds.py, scrapers

Usage:
    from api.services.normalization_service import normalizer

    # Normalize team names
    canonical = normalizer.normalize_team("Man Utd")  # -> "manutd"

    # Normalize events (handles team order reversal)
    key = normalizer.normalize_event("Man Utd vs Arsenal")  # -> "arsenalvmanutd"

    # Normalize competitions
    canonical = normalizer.normalize_competition("English Premier League")  # -> "epl"
"""
import re
from functools import lru_cache
from difflib import SequenceMatcher
from typing import Optional


class NormalizationService:
    """
    Centralized normalization for cross-bookmaker name matching.

    Handles:
    - Team name variations (Man Utd -> manutd, Wolverhampton Wanderers -> wolves)
    - Competition variations (English Premier League -> epl)
    - Event name normalization with team order sorting
    - Selection/market name normalization
    """

    # Competition name mappings
    # NOTE: Keys must include both:
    # 1. Database names (after stripping season/round prefixes)
    # 2. Frontend filter codes (from metadata.py ALLOWED_COMPETITIONS and leagueNormalization.ts)
    COMPETITION_MAP = {
        # EPL variations
        'premier league': 'epl',
        'english premier league': 'epl',
        'england premier league': 'epl',
        'epl': 'epl',
        # Bundesliga
        'german bundesliga': 'bundesliga',
        'germany bundesliga': 'bundesliga',
        'bundesliga': 'bundesliga',
        # La Liga - frontend sends "la liga" with space
        'spanish la liga': 'laliga',
        'la liga': 'laliga',
        'spanish primera division': 'laliga',
        'spain la liga': 'laliga',
        # Serie A - frontend sends "serie a" with space
        'italian serie a': 'seriea',
        'serie a': 'seriea',
        'italy serie a': 'seriea',
        # Ligue 1 - frontend sends "ligue 1" with space
        'french ligue 1': 'ligue1',
        'ligue 1': 'ligue1',
        'france ligue 1': 'ligue1',
        # A-League - frontend sends "a-league" with hyphen
        'a-league men': 'aleague',
        'a-league': 'aleague',
        'a league': 'aleague',
        'a-league women': 'aleaguewomen',
        'australia a-league': 'aleague',
        'australia a-league women': 'aleaguewomen',
        'australian a-league': 'aleague',
        # NBA
        'nba': 'nba',
        # NBL
        'nbl': 'nbl',
        'australia nbl': 'nbl',
        # NHL
        'nhl': 'nhl',
        # AFL
        'afl': 'afl',
        'australian football league': 'afl',
        # NRL
        'nrl': 'nrl',
        'national rugby league': 'nrl',
        # Boxing
        'boxing': 'boxing',
        'upcoming fights': 'boxing',
        'boxing matches': 'boxing',
        # Champions League
        'uefa champions league': 'ucl',
        'champions league': 'ucl',
        'ucl': 'ucl',
        # MLS
        'major league soccer': 'mls',
        'mls': 'mls',
    }

    # Team name mappings - SINGLE SOURCE OF TRUTH
    # Keys are lowercase variations, values are canonical forms
    TEAM_MAP = {
        # ============ EPL Teams ============
        'wolverhampton wanderers': 'wolves',
        'wolverhampton': 'wolves',
        'nottinghm forest': 'nottingham',
        'nottm forest': 'nottingham',
        'nottingham forest': 'nottingham',
        'brighton hovealb': 'brighton',
        'brighton & hove albion': 'brighton',
        'brighton hove albion': 'brighton',
        'manchester united': 'manutd',
        'man united': 'manutd',
        'man utd': 'manutd',
        'manchester city': 'mancity',
        'man city': 'mancity',
        'tottenham hotspur': 'tottenham',
        'tottenham': 'tottenham',
        'spurs': 'tottenham',
        'west ham united': 'westham',
        'west ham': 'westham',
        'newcastle united': 'newcastle',
        'leicester city': 'leicester',
        'leeds united': 'leeds',
        'sunderland afc': 'sunderland',
        'afc bournemouth': 'bournemouth',
        'everton fc': 'everton',
        'arsenal fc': 'arsenal',
        'crystal palace': 'crystalpalace',
        'aston villa': 'astonvilla',

        # ============ German Bundesliga ============
        'borussia dortmund': 'dortmund',
        'borussia monchengladbach': 'gladbach',
        'monchengladbach': 'gladbach',
        'mgladbach': 'gladbach',
        'bayer leverkusen': 'leverkusen',
        'bayern munich': 'bayern',
        'bayern munchen': 'bayern',
        'rb leipzig': 'leipzig',
        'vfl wolfsburg': 'wolfsburg',
        'vfb stuttgart': 'stuttgart',
        'union berlin': 'unionberlin',
        '1899 hoffenheim': 'hoffenheim',
        'tsg hoffenheim': 'hoffenheim',
        'eintracht frankfurt': 'frankfurt',
        '1. fc cologne': 'koln',
        '1. fc koln': 'koln',
        'fc koln': 'koln',
        'fc cologne': 'koln',
        'cologne': 'koln',
        'werder bremen': 'bremen',
        'sc freiburg': 'freiburg',
        'fc augsburg': 'augsburg',
        'hamburger sv': 'hamburg',
        '1. fsv mainz 05': 'mainz',
        'fsv mainz 05': 'mainz',
        'mainz 05': 'mainz',
        'fc st. pauli': 'stpauli',
        'fc st pauli': 'stpauli',
        'st. pauli': 'stpauli',
        'st pauli': 'stpauli',
        '1. fc heidenheim 1846': 'heidenheim',
        'fc heidenheim': 'heidenheim',
        'heidenheim 1846': 'heidenheim',

        # ============ Spanish La Liga ============
        'atletico madrid': 'atletico',
        'real sociedad': 'sociedad',
        'athletic bilbao': 'bilbao',
        'athletic club': 'bilbao',
        'real oviedo': 'oviedo',
        'rc celta de vigo': 'celtavigo',
        'celta vigo': 'celtavigo',
        'celta de vigo': 'celtavigo',
        'valencia cf': 'valencia',
        'rcd mallorca': 'mallorca',
        'villarreal cf': 'villarreal',
        'real valladolid': 'valladolid',
        'deportivo alaves': 'alaves',
        'ca osasuna': 'osasuna',
        'levante ud': 'levante',

        # ============ Italian Serie A ============
        'inter milan': 'inter',
        'internazionale': 'inter',
        'atalanta bc': 'atalanta',
        'genoa cfc': 'genoa',
        'ss lazio': 'lazio',
        'us cremonese': 'cremonese',
        'pisa sporting club': 'pisa',
        'us sassuolo calcio': 'sassuolo',
        'sassuolo calcio': 'sassuolo',
        'torino fc': 'torino',
        'cagliari calcio': 'cagliari',

        # ============ French Ligue 1 ============
        'paris saint-germain': 'psg',
        'paris st-g': 'psg',
        'paris sg': 'psg',
        'olympique marseille': 'marseille',
        'olympique lyon': 'lyon',

        # ============ UEFA Champions League ============
        'union saint-gilloise': 'unionsg',
        'sporting lisbon': 'sporting',
        'sporting cp': 'sporting',
        'sl benfica': 'benfica',
        'slavia prague': 'slavia',
        'galatasaray sk': 'galatasaray',
        'pafos fc': 'pafos',
        'fc copenhagen': 'copenhagen',
        'ssc napoli': 'napoli',
        'fc kairat almaty': 'kairat',
        'club brugge': 'brugge',
        'qarabag fk': 'qarabag',
        'juventus fc': 'juventus',
        'fc barcelona': 'barcelona',
        'bodo/glimt': 'bodoglimt',

        # ============ A-League ============
        'melbourne city': 'melbournecity',
        'melbourne victory': 'melbournevictory',
        'macarthur fc': 'macarthur',
        'newcastle jets': 'newcastlejets',
        'sydney fc': 'sydney',
        'adelaide united': 'adelaideunited',
        'perth glory': 'perthglory',
        'brisbane roar': 'brisbaneroar',
        'wellington phoenix': 'wellingtonphoenix',
        'central coast mariners': 'coastmariners',

        # ============ NBA Teams ============
        'los angeles lakers': 'lalakers',
        'la lakers': 'lalakers',
        'lakers': 'lalakers',
        'los angeles clippers': 'laclippers',
        'la clippers': 'laclippers',
        'clippers': 'laclippers',
        'golden state warriors': 'warriors',
        'warriors': 'warriors',
        'phoenix suns': 'suns',
        'boston celtics': 'celtics',
        'miami heat': 'heat',
        'milwaukee bucks': 'bucks',
        'philadelphia 76ers': 'sixers',
        'phila 76ers': 'sixers',
        '76ers': 'sixers',
        'denver nuggets': 'nuggets',
        'dallas mavericks': 'mavericks',
        'memphis grizzlies': 'grizzlies',
        'sacramento kings': 'kings',
        'orlando magic': 'magic',
        'indiana pacers': 'pacers',
        'oklahoma city thunder': 'thunder',
        'okc thunder': 'thunder',
        'new orleans pelicans': 'pelicans',
        'portland trail blazers': 'blazers',
        'trail blazers': 'blazers',
        'minnesota timberwolves': 'timberwolves',
        'houston rockets': 'rockets',
        'toronto raptors': 'raptors',
        'cleveland cavaliers': 'cavaliers',
        'brooklyn nets': 'nets',
        'new york knicks': 'knicks',
        'atlanta hawks': 'atlhawks',
        'chicago bulls': 'bulls',
        'detroit pistons': 'pistons',
        'charlotte hornets': 'hornets',
        'washington wizards': 'wizards',
        'utah jazz': 'jazz',
        'san antonio spurs': 'saspurs',

        # ============ NBL Teams (Australian) ============
        'sydney kings': 'sydneykings',
        'melbourne united': 'melbunited',
        'perth wildcats': 'wildcats',
        'brisbane bullets': 'bullets',
        'south east melbourne phoenix': 'semphoenix',
        'se melbourne phoenix': 'semphoenix',
        'cairns taipans': 'taipans',
        'tasmania jackjumpers': 'jackjumpers',
        'new zealand breakers': 'breakers',
        'nz breakers': 'breakers',
        'illawarra hawks': 'illawarrahawks',
        'adelaide 36ers': '36ers',

        # ============ NHL Teams ============
        'edmonton oilers': 'oilers',
        'toronto maple leafs': 'mapleleafs',
        'maple leafs': 'mapleleafs',
        'montreal canadiens': 'canadiens',
        'winnipeg jets': 'wpgjets',
        'vancouver canucks': 'canucks',
        'calgary flames': 'flames',
        'ottawa senators': 'senators',
        'new york rangers': 'nyrangers',
        'ny rangers': 'nyrangers',
        'new york islanders': 'islanders',
        'ny islanders': 'islanders',
        'boston bruins': 'bruins',
        'pittsburgh penguins': 'penguins',
        'washington capitals': 'capitals',
        'philadelphia flyers': 'flyers',
        'chicago blackhawks': 'blackhawks',
        'detroit red wings': 'redwings',
        'colorado avalanche': 'avalanche',
        'minnesota wild': 'mnwild',
        'st. louis blues': 'stlblues',
        'st louis blues': 'stlblues',
        'dallas stars': 'dalstars',
        'vegas golden knights': 'goldenknights',
        'seattle kraken': 'kraken',
        'tampa bay lightning': 'lightning',
        'florida panthers': 'flapanthers',
        'carolina hurricanes': 'hurricanes',
        'nashville predators': 'predators',
        'san jose sharks': 'sharks',
        'anaheim ducks': 'ducks',
        'los angeles kings': 'lakings',
        'la kings': 'lakings',
        'columbus blue jackets': 'bluejackets',
        'buffalo sabres': 'sabres',
        'new jersey devils': 'devils',
        'arizona coyotes': 'coyotes',

        # ============ Boxing ============
        'naoya inoue': 'inoue',
        'junto nakatani': 'nakatani',
        'callum simpson': 'csimpson',

        # ============ AFL Teams ============
        'richmond tigers': 'richmond',
        'collingwood magpies': 'collingwood',
        'essendon bombers': 'essendon',
        'carlton blues': 'carlton',
        'hawthorn hawks': 'hawthorn',
        'geelong cats': 'geelong',
        'melbourne demons': 'melbourne',
        'brisbane lions': 'brisbane',
        'sydney swans': 'sydneyswans',
        'west coast eagles': 'westcoast',
        'fremantle dockers': 'fremantle',
        'port adelaide power': 'portadelaide',
        'adelaide crows': 'adelaidecrows',
        'north melbourne kangaroos': 'northmelbourne',
        'western bulldogs': 'bulldogs',
        'st kilda saints': 'stkilda',
        'gold coast suns': 'goldcoast',
        'gws giants': 'gwsgiants',
        'greater western sydney giants': 'gwsgiants',

        # ============ NRL Teams ============
        'sydney roosters': 'roosters',
        'south sydney rabbitohs': 'rabbitohs',
        'melbourne storm': 'storm',
        'penrith panthers': 'penrith',
        'brisbane broncos': 'broncos',
        'north queensland cowboys': 'cowboys',
        'gold coast titans': 'titans',
        'cronulla sharks': 'cronulla',
        'canterbury bulldogs': 'canterbulldogs',
        'parramatta eels': 'eels',
        'wests tigers': 'weststigers',
        'manly sea eagles': 'manly',
        'newcastle knights': 'knights',
        'canberra raiders': 'raiders',
        'st george illawarra dragons': 'dragons',
        'new zealand warriors': 'nzwarriors',
        'dolphins': 'dolphins',
    }

    # Prefixes to remove from team names
    TEAM_PREFIXES = ['as ', 'ac ', 'fc ', 'cf ', 'sc ', 'ss ', 'us ', 'afc ', 'rcd ', 'cd ', 'ca ']

    # Suffixes to remove from team names
    TEAM_SUFFIXES = [' fc', ' cf', ' bc', ' sc', ' ac', ' afc', ' cfc']

    def __init__(self):
        """Initialize the normalization service."""
        # Pre-compile regex patterns
        self._numeric_prefix_pattern = re.compile(r'^\d+\.\s*')
        self._separator_patterns = [
            (re.compile(r'\s+vs\s+'), ' v '),
            (re.compile(r'\s+@\s+'), ' v '),
            (re.compile(r'\s+-\s+'), ' v '),
        ]

    @lru_cache(maxsize=10000)
    def normalize_competition(self, name: str) -> str:
        """
        Normalize competition name for cross-bookmaker matching.

        Args:
            name: Raw competition name from bookmaker

        Returns:
            Canonical competition key (e.g., "epl", "bundesliga")
        """
        if not name:
            return ""
        norm = name.lower().strip()
        # Strip season prefixes like "2025/2026 " or "2025 "
        norm = re.sub(r'^\d{4}(?:/\d{4})?\s+', '', norm)
        # Strip trailing phase markers like "- Round 20" or "- Regular Season"
        norm = re.sub(r'\s*-\s*(round\s+\d+|regular season)\s*$', '', norm)
        norm = norm.strip()
        return self.COMPETITION_MAP.get(norm, norm)

    @lru_cache(maxsize=10000)
    def normalize_team(self, name: str) -> str:
        """
        Normalize team/selection name for cross-bookmaker matching.

        Args:
            name: Raw team name from bookmaker

        Returns:
            Canonical team key (e.g., "manutd", "wolves")
        """
        if not name:
            return ""

        norm = name.lower().strip()

        # Handle draw variations
        if norm in ["draw", "the draw", "tie", "the tie"]:
            return "draw"

        # Remove "the " prefix
        norm = norm.replace('the ', '')

        # Remove common prefixes
        for prefix in self.TEAM_PREFIXES:
            if norm.startswith(prefix):
                norm = norm[len(prefix):]

        # Remove common suffixes
        for suffix in self.TEAM_SUFFIXES:
            if norm.endswith(suffix):
                norm = norm[:-len(suffix)]

        # Apply team mappings (longer strings first for correct matching)
        # Only apply FIRST matching replacement to avoid double-replacement
        # e.g., "la lakers" → "lalakers", then "lakers" in "lalakers" → "lalalakers" is wrong
        for old, new in sorted(self.TEAM_MAP.items(), key=lambda x: -len(x[0])):
            if old in norm:
                norm = norm.replace(old, new)
                break  # Stop after first match

        # Remove all spaces for final comparison
        return norm.replace(' ', '')

    @lru_cache(maxsize=10000)
    def normalize_event(self, name: str) -> str:
        """
        Normalize event name for cross-bookmaker matching.

        Handles:
        - Separator variations (vs, v, @, -)
        - Team name normalization
        - Team order sorting (alphabetical)

        Args:
            name: Raw event name (e.g., "Manchester United vs Arsenal")

        Returns:
            Normalized key with sorted teams (e.g., "arsenalvmanutd")
        """
        if not name:
            return ""

        norm = name.lower().strip()

        # Remove numeric prefixes like "1. " (e.g., "1. FC Heidenheim")
        norm = self._numeric_prefix_pattern.sub('', norm)

        # Standardize separators to "v"
        for pattern, replacement in self._separator_patterns:
            norm = pattern.sub(replacement, norm)

        # Remove common team suffixes/prefixes
        for suffix in self.TEAM_SUFFIXES:
            norm = norm.replace(suffix, '')
        for prefix in self.TEAM_PREFIXES:
            norm = norm.replace(prefix, '')

        # Apply team mappings
        for old, new in sorted(self.TEAM_MAP.items(), key=lambda x: -len(x[0])):
            norm = norm.replace(old, new)

        # CRITICAL: Mark the separator BEFORE removing spaces
        # This prevents issues with team names containing 'v' (e.g., "wolves", "liverpool")
        norm = norm.replace(' v ', '|VS|')

        # Now remove spaces
        norm = norm.replace(' ', '')

        # Sort teams alphabetically to handle reversed order
        # Betfair: "Boston Celtics @ Toronto Raptors" → "celtics|VS|raptors" → sorted → "celticsvraptors"
        # Ladbrokes: "Toronto Raptors vs Boston Celtics" → "raptors|VS|celtics" → sorted → "celticsvraptors"
        if '|VS|' in norm:
            parts = norm.split('|VS|')
            if len(parts) == 2:
                norm = 'v'.join(sorted(parts))
        else:
            # No separator found, just return normalized name
            pass

        return norm

    def normalize_selection(self, name: str) -> str:
        """
        Alias for normalize_team. Used for selection/outcome names.

        Args:
            name: Raw selection name from bookmaker

        Returns:
            Canonical selection key
        """
        return self.normalize_team(name)

    def fuzzy_match_score(self, str1: str, str2: str) -> float:
        """
        Calculate fuzzy match score between two strings (0.0 to 1.0).

        Uses normalize_team on both strings before comparison.

        Args:
            str1: First string
            str2: Second string

        Returns:
            Similarity ratio (0.0 to 1.0)
        """
        s1 = self.normalize_team(str1)
        s2 = self.normalize_team(str2)
        return SequenceMatcher(None, s1, s2).ratio()

    def clear_cache(self):
        """Clear all LRU caches. Useful for testing or after adding new mappings."""
        self.normalize_competition.cache_clear()
        self.normalize_team.cache_clear()
        self.normalize_event.cache_clear()


# Singleton instance for easy import
normalizer = NormalizationService()


# Convenience functions for backward compatibility
def normalize_team_name(name: str) -> str:
    """Convenience function for normalize_team."""
    return normalizer.normalize_team(name)


def normalize_event_name(name: str) -> str:
    """Convenience function for normalize_event."""
    return normalizer.normalize_event(name)


def normalize_competition_name(name: str) -> str:
    """Convenience function for normalize_competition."""
    return normalizer.normalize_competition(name)


def normalize_selection_name(name: str) -> str:
    """Convenience function for normalize_selection."""
    return normalizer.normalize_selection(name)


def fuzzy_match_score(str1: str, str2: str) -> float:
    """Convenience function for fuzzy_match_score."""
    return normalizer.fuzzy_match_score(str1, str2)
