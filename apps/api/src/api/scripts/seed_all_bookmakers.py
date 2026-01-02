"""
Seed all 100+ Australian bookmakers with platform groupings.

Platform groups allow reusing scrapers across multiple bookmaker skins:
- STANDALONE: Major operators with proprietary systems (need individual scrapers)
- GENERATION_WEB: ~15 skins on shared platform (1 scraper covers all)
- PUNTERS_TECH: ~15 skins on shared platform (1 scraper covers all)
- ENTAIN: Ladbrokes, Neds, Unibet (1 scraper covers all)
- BETMAKERS: Platform provider for multiple skins

Tier structure:
- FREE: Ladbrokes + Neds (2 bookmakers) + Betfair exchange
- PREMIUM: 17 bookmakers (includes Free tier)
- DIAMOND: All 103 bookmakers

Run with:
    python -m api.scripts.seed_all_bookmakers
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy.orm import Session
from api.core.database import SessionLocal
from api.models import Sport, Bookmaker, Competition
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def seed_all_bookmakers(db: Session):
    """Seed all 100+ Australian bookmakers with platform and tier config"""
    logger.info("Seeding all bookmakers with platform groupings...")

    # ==========================================================================
    # TIER DEFINITIONS
    # ==========================================================================
    # FREE: Ladbrokes + Neds (2 bookmakers) + Betfair (exchange, always included)
    # PREMIUM: 17 bookmakers total (Free + 15 more)
    # DIAMOND: All 103 bookmakers
    # ==========================================================================

    bookmakers_data = [
        # ======================================================================
        # FREE TIER (2 bookmakers) - Entain Platform
        # ======================================================================
        {
            "code": "ladbrokes",
            "name": "Ladbrokes",
            "display_name": "Ladbrokes",
            "website_url": "https://www.ladbrokes.com.au",
            "is_active": True,
            "base_url": "https://www.ladbrokes.com.au",
            "scraping_config": {
                "tier": "free",
                "platform": "entain",
                "scraper_class": "entain",
                "difficulty": "medium",
                "requires_proxy": False,
            },
        },
        {
            "code": "neds",
            "name": "Neds",
            "display_name": "Neds",
            "website_url": "https://www.neds.com.au",
            "is_active": True,  # ENABLED - uses EntainScraper (same as Ladbrokes)
            "base_url": "https://www.neds.com.au",
            "scraping_config": {
                "tier": "free",
                "platform": "entain",
                "scraper_class": "entain",
                "difficulty": "medium",
                "requires_proxy": False,
            },
        },

        # ======================================================================
        # PREMIUM TIER (15 more bookmakers = 17 total with Free)
        # ======================================================================

        # Betfair Exchange (always included as lay side)
        {
            "code": "betfair",
            "name": "Betfair Exchange",
            "display_name": "Betfair",
            "website_url": "https://www.betfair.com.au",
            "is_active": True,
            "api_endpoint": "https://api.betfair.com/exchange/betting/rest/v1.0",
            "default_source_type": "api",
            "scraping_config": {
                "tier": "premium",
                "platform": "exchange",
                "scraper_class": "betfair",
                "difficulty": "easy",
                "requires_proxy": False,
            },
        },

        # Standalone Major Operators (Premium)
        {
            "code": "sportsbet",
            "name": "Sportsbet",
            "display_name": "Sportsbet",
            "website_url": "https://www.sportsbet.com.au",
            "is_active": False,
            "scraping_config": {
                "tier": "premium",
                "platform": "standalone",
                "scraper_class": "sportsbet",
                "difficulty": "hard",
                "requires_proxy": True,
            },
        },
        {
            "code": "tab",
            "name": "TAB",
            "display_name": "TAB",
            "website_url": "https://www.tab.com.au",
            "is_active": False,  # Disabled - needs rotating proxy
            "base_url": "https://api.beta.tab.com.au",
            "scraping_config": {
                "tier": "premium",
                "platform": "standalone",
                "scraper_class": "tab",
                "difficulty": "hard",
                "requires_proxy": True,
            },
        },
        {
            "code": "pointsbet",
            "name": "PointsBet",
            "display_name": "PointsBet",
            "website_url": "https://www.pointsbet.com.au",
            "is_active": False,
            "scraping_config": {
                "tier": "premium",
                "platform": "standalone",
                "scraper_class": "pointsbet",
                "difficulty": "medium",
                "requires_proxy": False,
            },
        },
        {
            "code": "unibet",
            "name": "UniBet",
            "display_name": "UniBet",
            "website_url": "https://www.unibet.com.au",
            "is_active": False,
            "scraping_config": {
                "tier": "premium",
                "platform": "entain",
                "scraper_class": "entain",
                "difficulty": "medium",
                "requires_proxy": False,
            },
        },
        {
            "code": "betr",
            "name": "Betr",
            "display_name": "Betr",
            "website_url": "https://www.betr.com.au",
            "is_active": False,
            "scraping_config": {
                "tier": "premium",
                "platform": "standalone",
                "scraper_class": "betr",
                "difficulty": "medium",
                "requires_proxy": False,
            },
        },
        {
            "code": "betdeluxe",
            "name": "BetDeluxe",
            "display_name": "BetDeluxe",
            "website_url": "https://www.betdeluxe.com.au",
            "is_active": False,
            "scraping_config": {
                "tier": "premium",
                "platform": "standalone",
                "scraper_class": "betdeluxe",
                "difficulty": "medium",
                "requires_proxy": False,
            },
        },
        {
            "code": "betright",
            "name": "BetRight",
            "display_name": "BetRight",
            "website_url": "https://www.betright.com.au",
            "is_active": False,
            "scraping_config": {
                "tier": "premium",
                "platform": "standalone",
                "scraper_class": "betright",
                "difficulty": "medium",
                "requires_proxy": False,
            },
        },
        {
            "code": "crossbet",
            "name": "CrossBet",
            "display_name": "CrossBet",
            "website_url": "https://www.crossbet.com.au",
            "is_active": False,
            "scraping_config": {
                "tier": "premium",
                "platform": "standalone",
                "scraper_class": "generic",
                "difficulty": "medium",
                "requires_proxy": False,
            },
        },
        {
            "code": "dabble",
            "name": "Dabble",
            "display_name": "Dabble",
            "website_url": "https://www.dabble.com.au",
            "is_active": False,
            "scraping_config": {
                "tier": "premium",
                "platform": "standalone",
                "scraper_class": "dabble",
                "difficulty": "medium",
                "requires_proxy": False,
            },
        },
        {
            "code": "elitebet",
            "name": "EliteBet",
            "display_name": "EliteBet",
            "website_url": "https://www.elitebet.com.au",
            "is_active": False,
            "scraping_config": {
                "tier": "premium",
                "platform": "generation_web",
                "scraper_class": "generation_web",
                "difficulty": "medium",
                "requires_proxy": False,
            },
        },
        {
            "code": "tabtouch",
            "name": "TABTouch",
            "display_name": "TABTouch",
            "website_url": "https://www.tabtouch.com.au",
            "is_active": False,
            "scraping_config": {
                "tier": "premium",
                "platform": "standalone",
                "scraper_class": "tabtouch",
                "difficulty": "hard",
                "requires_proxy": True,
            },
        },
        {
            "code": "realbookie",
            "name": "Real Bookie",
            "display_name": "Real Bookie",
            "website_url": "https://www.realbookie.com.au",
            "is_active": False,
            "scraping_config": {
                "tier": "premium",
                "platform": "standalone",
                "scraper_class": "realbookie",
                "difficulty": "medium",
                "requires_proxy": False,
            },
        },
        {
            "code": "picklebet",
            "name": "Picklebet",
            "display_name": "Picklebet",
            "website_url": "https://www.picklebet.com",
            "is_active": False,
            "scraping_config": {
                "tier": "premium",
                "platform": "standalone",
                "scraper_class": "picklebet",
                "difficulty": "medium",
                "requires_proxy": False,
            },
        },

        # ======================================================================
        # DIAMOND TIER - Standalone Major Operators (not in Premium)
        # ======================================================================
        {
            "code": "palmerbet",
            "name": "Palmerbet",
            "display_name": "Palmerbet",
            "website_url": "https://www.palmerbet.com",
            "is_active": False,
            "scraping_config": {"tier": "diamond", "platform": "standalone", "scraper_class": "palmerbet"},
        },
        {
            "code": "playup",
            "name": "PlayUp",
            "display_name": "PlayUp",
            "website_url": "https://www.playup.com",
            "is_active": False,
            "scraping_config": {"tier": "diamond", "platform": "standalone", "scraper_class": "playup"},
        },
        {
            "code": "betnation",
            "name": "BetNation",
            "display_name": "BetNation",
            "website_url": "https://www.betnation.com.au",
            "is_active": False,
            "scraping_config": {"tier": "diamond", "platform": "standalone", "scraper_class": "betnation"},
        },
        {
            "code": "pulsebet",
            "name": "PulseBet",
            "display_name": "PulseBet",
            "website_url": "https://www.pulsebet.com.au",
            "is_active": False,
            "scraping_config": {"tier": "diamond", "platform": "standalone", "scraper_class": "pulsebet"},
        },
        {
            "code": "bigbet",
            "name": "BigBet",
            "display_name": "BigBet",
            "website_url": "https://www.bigbet.com.au",
            "is_active": False,
            "scraping_config": {"tier": "diamond", "platform": "standalone", "scraper_class": "bigbet"},
        },
        {
            "code": "surge",
            "name": "Surge",
            "display_name": "Surge",
            "website_url": "https://www.surge.com.au",
            "is_active": False,
            "scraping_config": {"tier": "diamond", "platform": "standalone", "scraper_class": "surge"},
        },
        {
            "code": "noisy",
            "name": "Noisy",
            "display_name": "Noisy",
            "website_url": "https://www.noisy.com.au",
            "is_active": False,
            "scraping_config": {"tier": "diamond", "platform": "standalone", "scraper_class": "noisy"},
        },
        {
            "code": "betyoucan",
            "name": "BetYouCan",
            "display_name": "BetYouCan",
            "website_url": "https://www.betyoucan.com.au",
            "is_active": False,
            "scraping_config": {"tier": "diamond", "platform": "standalone", "scraper_class": "betyoucan"},
        },
        {
            "code": "dowbet",
            "name": "DowBet",
            "display_name": "DowBet",
            "website_url": "https://www.dowbet.com.au",
            "is_active": False,
            "scraping_config": {"tier": "diamond", "platform": "standalone", "scraper_class": "dowbet"},
        },
        {
            "code": "terrybet",
            "name": "TerryBet",
            "display_name": "TerryBet",
            "website_url": "https://www.terrybet.com.au",
            "is_active": False,
            "scraping_config": {"tier": "diamond", "platform": "standalone", "scraper_class": "terrybet"},
        },
        {
            "code": "bossbet",
            "name": "BossBet",
            "display_name": "BossBet",
            "website_url": "https://www.bossbet.com.au",
            "is_active": False,
            "scraping_config": {"tier": "diamond", "platform": "standalone", "scraper_class": "bossbet"},
        },
        {
            "code": "robwaterhouse",
            "name": "Rob Waterhouse",
            "display_name": "Rob Waterhouse",
            "website_url": "https://www.robwaterhouse.com.au",
            "is_active": False,
            "scraping_config": {"tier": "diamond", "platform": "standalone", "scraper_class": "robwaterhouse"},
        },
        {
            "code": "baggybet",
            "name": "BaggyBet",
            "display_name": "BaggyBet",
            "website_url": "https://www.baggybet.com.au",
            "is_active": False,
            "scraping_config": {"tier": "diamond", "platform": "standalone", "scraper_class": "baggybet"},
        },
        {
            "code": "betgold",
            "name": "BetGold",
            "display_name": "BetGold",
            "website_url": "https://www.betgold.com.au",
            "is_active": False,
            "scraping_config": {"tier": "diamond", "platform": "standalone", "scraper_class": "betgold"},
        },
        {
            "code": "bet66",
            "name": "Bet66",
            "display_name": "Bet66",
            "website_url": "https://www.bet66.com.au",
            "is_active": False,
            "scraping_config": {"tier": "diamond", "platform": "standalone", "scraper_class": "bet66"},
        },
        {
            "code": "betestate",
            "name": "BetEstate",
            "display_name": "BetEstate",
            "website_url": "https://www.betestate.com.au",
            "is_active": False,
            "scraping_config": {"tier": "diamond", "platform": "standalone", "scraper_class": "betestate"},
        },
        {
            "code": "betlocal",
            "name": "BetLocal",
            "display_name": "BetLocal",
            "website_url": "https://www.betlocal.com.au",
            "is_active": False,
            "scraping_config": {"tier": "diamond", "platform": "standalone", "scraper_class": "betlocal"},
        },
        {
            "code": "marantellibet",
            "name": "MarantelliBet",
            "display_name": "MarantelliBet",
            "website_url": "https://www.marantellibet.com.au",
            "is_active": False,
            "scraping_config": {"tier": "diamond", "platform": "standalone", "scraper_class": "marantellibet"},
        },
        {
            "code": "readybet",
            "name": "ReadyBet",
            "display_name": "ReadyBet",
            "website_url": "https://www.readybet.com.au",
            "is_active": False,
            "scraping_config": {"tier": "diamond", "platform": "standalone", "scraper_class": "readybet"},
        },
        # chasebet moved to Punterstech platform section
        {
            "code": "diamondbet",
            "name": "DiamondBet",
            "display_name": "DiamondBet",
            "website_url": "https://www.diamondbet.com.au",
            "is_active": False,
            "scraping_config": {"tier": "diamond", "platform": "standalone", "scraper_class": "diamondbet"},
        },
        {
            "code": "okebet",
            "name": "OkeBet",
            "display_name": "OkeBet",
            "website_url": "https://www.okebet.com.au",
            "is_active": False,
            "scraping_config": {"tier": "diamond", "platform": "standalone", "scraper_class": "okebet"},
        },
        {
            "code": "picnicbet",
            "name": "PicnicBet",
            "display_name": "PicnicBet",
            "website_url": "https://www.picnicbet.com.au",
            "is_active": False,
            "scraping_config": {"tier": "diamond", "platform": "standalone", "scraper_class": "picnicbet"},
        },
        {
            "code": "playwest",
            "name": "PlayWest",
            "display_name": "PlayWest",
            "website_url": "https://www.playwest.com.au",
            "is_active": False,
            "scraping_config": {"tier": "diamond", "platform": "standalone", "scraper_class": "playwest"},
        },
        {
            "code": "ponybet",
            "name": "PonyBet",
            "display_name": "PonyBet",
            "website_url": "https://www.ponybet.com.au",
            "is_active": False,
            "scraping_config": {"tier": "diamond", "platform": "standalone", "scraper_class": "ponybet"},
        },
        {
            "code": "premiumbet",
            "name": "PremiumBet",
            "display_name": "PremiumBet",
            "website_url": "https://www.premiumbet.com.au",
            "is_active": False,
            "scraping_config": {"tier": "diamond", "platform": "standalone", "scraper_class": "premiumbet"},
        },
        {
            "code": "punt123",
            "name": "Punt123",
            "display_name": "Punt123",
            "website_url": "https://www.punt123.com.au",
            "is_active": False,
            "scraping_config": {"tier": "diamond", "platform": "standalone", "scraper_class": "punt123"},
        },
        {
            "code": "swiftbet",
            "name": "SwiftBet",
            "display_name": "SwiftBet",
            "website_url": "https://www.swiftbet.com.au",
            "is_active": False,
            "scraping_config": {"tier": "diamond", "platform": "standalone", "scraper_class": "swiftbet"},
        },
        {
            "code": "upcoz",
            "name": "UpCoz",
            "display_name": "UpCoz",
            "website_url": "https://www.upcoz.com.au",
            "is_active": False,
            "scraping_config": {"tier": "diamond", "platform": "standalone", "scraper_class": "upcoz"},
        },
        {
            "code": "wishbet",
            "name": "WishBet",
            "display_name": "WishBet",
            "website_url": "https://www.wishbet.com.au",
            "is_active": False,
            "scraping_config": {"tier": "diamond", "platform": "standalone", "scraper_class": "wishbet"},
        },
        {
            "code": "zbet",
            "name": "ZBet",
            "display_name": "ZBet",
            "website_url": "https://www.zbet.com.au",
            "is_active": False,
            "scraping_config": {"tier": "diamond", "platform": "standalone", "scraper_class": "zbet"},
        },
        {
            "code": "betm",
            "name": "BetM",
            "display_name": "BetM",
            "website_url": "https://www.betm.com.au",
            "is_active": False,
            "scraping_config": {"tier": "diamond", "platform": "standalone", "scraper_class": "betm"},
        },
        {
            "code": "slambet",
            "name": "SlamBet",
            "display_name": "SlamBet",
            "website_url": "https://www.slambet.com.au",
            "is_active": False,
            "scraping_config": {"tier": "diamond", "platform": "standalone", "scraper_class": "slambet"},
        },
        {
            "code": "bet575",
            "name": "Bet575",
            "display_name": "Bet575",
            "website_url": "https://www.bet575.com.au",
            "is_active": False,
            "scraping_config": {"tier": "diamond", "platform": "standalone", "scraper_class": "bet575"},
        },
        {
            "code": "bet777",
            "name": "Bet777",
            "display_name": "Bet777",
            "website_url": "https://www.bet777.com.au",
            "is_active": False,
            "scraping_config": {"tier": "diamond", "platform": "standalone", "scraper_class": "bet777"},
        },
        {
            "code": "betgalaxy",
            "name": "BetGalaxy",
            "display_name": "BetGalaxy",
            "website_url": "https://www.betgalaxy.com.au",
            "is_active": False,
            "scraping_config": {"tier": "diamond", "platform": "standalone", "scraper_class": "betgalaxy"},
        },
        {
            "code": "betprofessor",
            "name": "BetProfessor",
            "display_name": "BetProfessor",
            "website_url": "https://www.betprofessor.com.au",
            "is_active": False,
            "scraping_config": {"tier": "diamond", "platform": "standalone", "scraper_class": "betprofessor"},
        },
        {
            "code": "betroyale",
            "name": "BetRoyale",
            "display_name": "BetRoyale",
            "website_url": "https://www.betroyale.com.au",
            "is_active": False,
            "scraping_config": {"tier": "diamond", "platform": "standalone", "scraper_class": "betroyale"},
        },
        {
            "code": "buffalobet",
            "name": "BuffaloBet",
            "display_name": "BuffaloBet",
            "website_url": "https://www.buffalobet.com.au",
            "is_active": False,
            "scraping_config": {"tier": "diamond", "platform": "standalone", "scraper_class": "buffalobet"},
        },
        {
            "code": "chromabet",
            "name": "ChromaBet",
            "display_name": "ChromaBet",
            "website_url": "https://www.chromabet.com.au",
            "is_active": False,
            "scraping_config": {"tier": "diamond", "platform": "standalone", "scraper_class": "chromabet"},
        },
        {
            "code": "fiestabet",
            "name": "FiestaBet",
            "display_name": "FiestaBet",
            "website_url": "https://www.fiestabet.com.au",
            "is_active": False,
            "scraping_config": {"tier": "diamond", "platform": "standalone", "scraper_class": "fiestabet"},
        },
        {
            "code": "gigabet",
            "name": "GigaBet",
            "display_name": "GigaBet",
            "website_url": "https://www.gigabet.com.au",
            "is_active": False,
            "scraping_config": {"tier": "diamond", "platform": "standalone", "scraper_class": "gigabet"},
        },
        {
            "code": "goldenbet888",
            "name": "GoldenBet888",
            "display_name": "GoldenBet888",
            "website_url": "https://www.goldenbet888.com.au",
            "is_active": False,
            "scraping_config": {"tier": "diamond", "platform": "standalone", "scraper_class": "goldenbet888"},
        },
        {
            "code": "goldenrush",
            "name": "GoldenRush",
            "display_name": "GoldenRush",
            "website_url": "https://www.goldenrush.com.au",
            "is_active": False,
            "scraping_config": {"tier": "diamond", "platform": "standalone", "scraper_class": "goldenrush"},
        },
        {
            "code": "juicybet",
            "name": "JuicyBet",
            "display_name": "JuicyBet",
            "website_url": "https://www.juicybet.com.au",
            "is_active": False,
            "scraping_config": {"tier": "diamond", "platform": "standalone", "scraper_class": "juicybet"},
        },
        {
            "code": "junglebet",
            "name": "JungleBet",
            "display_name": "JungleBet",
            "website_url": "https://www.junglebet.com.au",
            "is_active": False,
            "scraping_config": {"tier": "diamond", "platform": "standalone", "scraper_class": "junglebet"},
        },
        {
            "code": "oldgill",
            "name": "OldGill",
            "display_name": "OldGill",
            "website_url": "https://www.oldgill.com.au",
            "is_active": False,
            "scraping_config": {"tier": "diamond", "platform": "standalone", "scraper_class": "oldgill"},
        },
        {
            "code": "puntcity",
            "name": "PuntCity",
            "display_name": "PuntCity",
            "website_url": "https://www.puntcity.com.au",
            "is_active": False,
            "scraping_config": {"tier": "diamond", "platform": "standalone", "scraper_class": "puntcity"},
        },
        {
            "code": "puntgenie",
            "name": "PuntGenie",
            "display_name": "PuntGenie",
            "website_url": "https://www.puntgenie.com.au",
            "is_active": False,
            "scraping_config": {"tier": "diamond", "platform": "standalone", "scraper_class": "puntgenie"},
        },
        {
            "code": "questbet",
            "name": "QuestBet",
            "display_name": "QuestBet",
            "website_url": "https://www.questbet.com.au",
            "is_active": False,
            "scraping_config": {"tier": "diamond", "platform": "standalone", "scraper_class": "questbet"},
        },
        {
            "code": "sterlingparker",
            "name": "SterlingParker",
            "display_name": "SterlingParker",
            "website_url": "https://www.sterlingparker.com.au",
            "is_active": False,
            "scraping_config": {"tier": "diamond", "platform": "standalone", "scraper_class": "sterlingparker"},
        },
        {
            "code": "sugarcastle",
            "name": "SugarCastle",
            "display_name": "SugarCastle",
            "website_url": "https://www.sugarcastle.com.au",
            "is_active": False,
            "scraping_config": {"tier": "diamond", "platform": "standalone", "scraper_class": "sugarcastle"},
        },
        {
            "code": "templebet",
            "name": "TempleBet",
            "display_name": "TempleBet",
            "website_url": "https://www.templebet.com.au",
            "is_active": False,
            "scraping_config": {"tier": "diamond", "platform": "standalone", "scraper_class": "templebet"},
        },
        {
            "code": "titanbet",
            "name": "TitanBet",
            "display_name": "TitanBet",
            "website_url": "https://www.titanbet.com.au",
            "is_active": False,
            "scraping_config": {"tier": "diamond", "platform": "standalone", "scraper_class": "titanbet"},
        },
        {
            "code": "vikingbet",
            "name": "VikingBet",
            "display_name": "VikingBet",
            "website_url": "https://www.vikingbet.com.au",
            "is_active": False,
            "scraping_config": {"tier": "diamond", "platform": "standalone", "scraper_class": "vikingbet"},
        },
        {
            "code": "volcanobet",
            "name": "VolcanoBet",
            "display_name": "VolcanoBet",
            "website_url": "https://www.volcanobet.com.au",
            "is_active": False,
            "scraping_config": {"tier": "diamond", "platform": "standalone", "scraper_class": "volcanobet"},
        },
        {
            "code": "wellbet",
            "name": "WellBet",
            "display_name": "WellBet",
            "website_url": "https://www.wellbet.com.au",
            "is_active": False,
            "scraping_config": {"tier": "diamond", "platform": "standalone", "scraper_class": "wellbet"},
        },

        # ======================================================================
        # DIAMOND TIER - Generation Web Platform (~15 skins, 1 scraper)
        # ======================================================================
        {
            "code": "goldbet",
            "name": "GoldBet",
            "display_name": "GoldBet",
            "website_url": "https://www.goldbet.com.au",
            "is_active": False,
            "scraping_config": {"tier": "diamond", "platform": "generation_web", "scraper_class": "generation_web"},
        },
        {
            "code": "mybet",
            "name": "MyBet",
            "display_name": "MyBet",
            "website_url": "https://www.mybet.com.au",
            "is_active": False,
            "scraping_config": {"tier": "diamond", "platform": "generation_web", "scraper_class": "generation_web"},
        },
        {
            "code": "winnersbet",
            "name": "WinnersBet",
            "display_name": "WinnersBet",
            "website_url": "https://www.winnersbet.com.au",
            "is_active": False,
            "scraping_config": {"tier": "diamond", "platform": "generation_web", "scraper_class": "generation_web"},
        },
        {
            "code": "midasbet",
            "name": "MidasBet",
            "display_name": "MidasBet",
            "website_url": "https://www.midasbet.com.au",
            "is_active": False,
            "scraping_config": {"tier": "diamond", "platform": "generation_web", "scraper_class": "generation_web"},
        },
        {
            "code": "justbet",
            "name": "JustBet",
            "display_name": "JustBet",
            "website_url": "https://www.justbet.com.au",
            "is_active": False,
            "scraping_config": {"tier": "diamond", "platform": "generation_web", "scraper_class": "generation_web"},
        },
        {
            "code": "puntnow",
            "name": "PuntNow",
            "display_name": "PuntNow",
            "website_url": "https://www.puntnow.com.au",
            "is_active": False,
            "scraping_config": {"tier": "diamond", "platform": "generation_web", "scraper_class": "generation_web"},
        },
        {
            "code": "jimmybet",
            "name": "JimmyBet",
            "display_name": "JimmyBet",
            "website_url": "https://www.jimmybet.com.au",
            "is_active": False,
            "scraping_config": {"tier": "diamond", "platform": "generation_web", "scraper_class": "generation_web"},
        },
        {
            "code": "letsbet",
            "name": "LetsBet",
            "display_name": "LetsBet",
            "website_url": "https://www.letsbet.com.au",
            "is_active": False,
            "scraping_config": {"tier": "diamond", "platform": "generation_web", "scraper_class": "generation_web"},
        },
        {
            "code": "betbetbet",
            "name": "BetBetBet",
            "display_name": "BetBetBet",
            "website_url": "https://www.betbetbet.com.au",
            "is_active": False,
            "scraping_config": {"tier": "diamond", "platform": "generation_web", "scraper_class": "generation_web"},
        },
        {
            "code": "ultrabet",
            "name": "UltraBet",
            "display_name": "UltraBet",
            "website_url": "https://www.ultrabet.com.au",
            "is_active": False,
            "scraping_config": {"tier": "diamond", "platform": "generation_web", "scraper_class": "generation_web"},
        },
        {
            "code": "puntzone",
            "name": "PuntZone",
            "display_name": "PuntZone",
            "website_url": "https://www.puntzone.com.au",
            "is_active": False,
            "scraping_config": {"tier": "diamond", "platform": "generation_web", "scraper_class": "generation_web"},
        },
        {
            "code": "boostbet",
            "name": "BoostBet",
            "display_name": "BoostBet",
            "website_url": "https://www.boostbet.com.au",
            "is_active": False,
            "scraping_config": {"tier": "diamond", "platform": "generation_web", "scraper_class": "generation_web"},
        },
        {
            "code": "hotbet",
            "name": "HotBet",
            "display_name": "HotBet",
            "website_url": "https://www.hotbet.com.au",
            "is_active": False,
            "scraping_config": {"tier": "diamond", "platform": "generation_web", "scraper_class": "generation_web"},
        },
        {
            "code": "boombet",
            "name": "BoomBet",
            "display_name": "BoomBet",
            "website_url": "https://www.boombet.com.au",
            "is_active": False,
            "scraping_config": {"tier": "diamond", "platform": "generation_web", "scraper_class": "generation_web"},
        },

        # ======================================================================
        # DIAMOND TIER - Punterstech Platform (21 skins, 1 scraper)
        # API Pattern: https://api.public.{domain}/api-events/public/...
        # ======================================================================
        {
            "code": "tradiebet",
            "name": "TradieBET",
            "display_name": "TradieBET",
            "website_url": "https://www.tradie.bet",
            "base_url": "https://api.public.tradie.bet",
            "is_active": True,  # ENABLED - Punterstech scraper ready
            "scraping_config": {
                "tier": "diamond",
                "platform": "punterstech",
                "scraper_class": "punterstech",
                "difficulty": "easy",
                "requires_proxy": False,
            },
        },
        {
            "code": "mintbet",
            "name": "MintBet",
            "display_name": "MintBet",
            "website_url": "https://www.mintbet.com.au",
            "base_url": "https://api.public.mintbet.au",
            "is_active": True,  # ENABLED - Punterstech scraper ready
            "scraping_config": {
                "tier": "diamond",
                "platform": "punterstech",
                "scraper_class": "punterstech",
                "difficulty": "easy",
                "requires_proxy": False,
            },
        },
        {
            "code": "betchamps",
            "name": "BetChamps",
            "display_name": "BetChamps",
            "website_url": "https://www.betchamps.com.au",
            "base_url": "https://api.public.betchamps.com.au",
            "is_active": True,  # ENABLED - API verified working
            "scraping_config": {
                "tier": "diamond",
                "platform": "punterstech",
                "scraper_class": "punterstech",
                "difficulty": "easy",
                "requires_proxy": False,
            },
        },
        {
            "code": "blondebet",
            "name": "BlondeBet",
            "display_name": "BlondeBet",
            "website_url": "https://www.blondebet.com.au",
            "base_url": "https://api.public.blondebet.com.au",
            "is_active": False,
            "scraping_config": {
                "tier": "diamond",
                "platform": "punterstech",
                "scraper_class": "punterstech",
                "difficulty": "easy",
                "requires_proxy": False,
            },
        },
        {
            "code": "betfocus",
            "name": "BetFocus",
            "display_name": "BetFocus",
            "website_url": "https://www.betfocus.com.au",
            "base_url": "https://api.public.betfocus.com.au",
            "is_active": False,
            "scraping_config": {
                "tier": "diamond",
                "platform": "punterstech",
                "scraper_class": "punterstech",
                "difficulty": "easy",
                "requires_proxy": False,
            },
        },
        {
            "code": "cashcage",
            "name": "CashCage",
            "display_name": "CashCage",
            "website_url": "https://www.cashcage.com.au",
            "base_url": "https://api.public.cashcage.com.au",
            "is_active": False,
            "scraping_config": {
                "tier": "diamond",
                "platform": "punterstech",
                "scraper_class": "punterstech",
                "difficulty": "easy",
                "requires_proxy": False,
            },
        },
        {
            "code": "lightningbet",
            "name": "LightningBet",
            "display_name": "LightningBet",
            "website_url": "https://www.lightningbet.com.au",
            "base_url": "https://api.public.lightningbet.com.au",
            "is_active": False,
            "scraping_config": {
                "tier": "diamond",
                "platform": "punterstech",
                "scraper_class": "punterstech",
                "difficulty": "easy",
                "requires_proxy": False,
            },
        },
        {
            "code": "starsports",
            "name": "StarSports",
            "display_name": "StarSports",
            "website_url": "https://www.starsports.com.au",
            "base_url": "https://api.public.starsports.com.au",
            "is_active": True,  # ENABLED - API verified working
            "scraping_config": {
                "tier": "diamond",
                "platform": "punterstech",
                "scraper_class": "punterstech",
                "difficulty": "easy",
                "requires_proxy": False,
            },
        },
        {
            "code": "topbet",
            "name": "TopBet",
            "display_name": "TopBet",
            "website_url": "https://www.topbet.au",
            "base_url": "https://api.public.topbet.au",
            "is_active": True,  # ENABLED - API verified working
            "scraping_config": {
                "tier": "diamond",
                "platform": "punterstech",
                "scraper_class": "punterstech",
                "difficulty": "easy",
                "requires_proxy": False,
            },
        },
        {
            "code": "betalpha",
            "name": "BetAlpha",
            "display_name": "BetAlpha",
            "website_url": "https://www.betalpha.au",
            "base_url": "https://api.public.betalpha.au",
            "is_active": False,  # Verify API works before enabling
            "scraping_config": {
                "tier": "diamond",
                "platform": "punterstech",
                "scraper_class": "punterstech",
                "difficulty": "easy",
                "requires_proxy": False,
            },
        },
        {
            "code": "betblitz",
            "name": "BetBlitz",
            "display_name": "BetBlitz",
            "website_url": "https://www.betblitz.com.au",
            "base_url": "https://api.public.betblitz.com.au",
            "is_active": True,  # ENABLED - API verified working
            "scraping_config": {
                "tier": "diamond",
                "platform": "punterstech",
                "scraper_class": "punterstech",
                "difficulty": "easy",
                "requires_proxy": False,
            },
        },
        {
            "code": "truebet",
            "name": "TrueBet",
            "display_name": "TrueBet",
            "website_url": "https://www.truebet.com.au",
            "base_url": "https://api.public.truebet.com.au",
            "is_active": False,
            "scraping_config": {
                "tier": "diamond",
                "platform": "punterstech",
                "scraper_class": "punterstech",
                "difficulty": "easy",
                "requires_proxy": False,
            },
        },
        {
            "code": "wizbet",
            "name": "WizBet",
            "display_name": "WizBet",
            "website_url": "https://www.wizbet.com.au",
            "base_url": "https://api.public.wizbet.com.au",
            "is_active": False,
            "scraping_config": {
                "tier": "diamond",
                "platform": "punterstech",
                "scraper_class": "punterstech",
                "difficulty": "easy",
                "requires_proxy": False,
            },
        },
        {
            "code": "betbuzz",
            "name": "BetBuzz",
            "display_name": "BetBuzz",
            "website_url": "https://www.betbuzz.au",
            "base_url": "https://api.public.betbuzz.au",
            "is_active": True,  # ENABLED - API verified working
            "scraping_config": {
                "tier": "diamond",
                "platform": "punterstech",
                "scraper_class": "punterstech",
                "difficulty": "easy",
                "requires_proxy": False,
            },
        },
        {
            "code": "ripperbet",
            "name": "RipperBet",
            "display_name": "RipperBet",
            "website_url": "https://www.ripperbet.au",
            "base_url": "https://api.public.ripperbet.au",
            "is_active": True,  # ENABLED - API verified working
            "scraping_config": {
                "tier": "diamond",
                "platform": "punterstech",
                "scraper_class": "punterstech",
                "difficulty": "easy",
                "requires_proxy": False,
            },
        },
        {
            "code": "teambet",
            "name": "TeamBet",
            "display_name": "TeamBet",
            "website_url": "https://www.teambet.com.au",
            "base_url": "https://api.public.teambet.com.au",
            "is_active": False,
            "scraping_config": {
                "tier": "diamond",
                "platform": "punterstech",
                "scraper_class": "punterstech",
                "difficulty": "easy",
                "requires_proxy": False,
            },
        },
        # xbet removed - domain not found/defunct
        {
            "code": "millennialbet",
            "name": "MillennialBet",
            "display_name": "MillennialBet",
            "website_url": "https://www.millennialbet.com.au",
            "base_url": "https://api.public.millennialbet.com.au",
            "is_active": True,  # ENABLED - API verified working
            "scraping_config": {
                "tier": "diamond",
                "platform": "punterstech",
                "scraper_class": "punterstech",
                "difficulty": "easy",
                "requires_proxy": False,
            },
        },
        {
            "code": "betreal",
            "name": "BetReal",
            "display_name": "BetReal",
            "website_url": "https://www.betreal.com.au",
            "base_url": "https://api.public.betreal.com.au",
            "is_active": True,  # ENABLED - API verified working
            "scraping_config": {
                "tier": "diamond",
                "platform": "punterstech",
                "scraper_class": "punterstech",
                "difficulty": "easy",
                "requires_proxy": False,
            },
        },
        {
            "code": "chasebet",
            "name": "ChaseBet",
            "display_name": "ChaseBet",
            "website_url": "https://www.chasebet.au",
            "base_url": "https://api.public.chasebet.au",
            "is_active": False,  # Verify API works before enabling
            "scraping_config": {
                "tier": "diamond",
                "platform": "punterstech",
                "scraper_class": "punterstech",
                "difficulty": "easy",
                "requires_proxy": False,
            },
        },
        {
            "code": "betvista",
            "name": "BetVista",
            "display_name": "BetVista",
            "website_url": "https://www.betvista.com.au",
            "base_url": "https://api.public.betvista.com.au",
            "is_active": False,
            "scraping_config": {
                "tier": "diamond",
                "platform": "punterstech",
                "scraper_class": "punterstech",
                "difficulty": "easy",
                "requires_proxy": False,
            },
        },
    ]

    # Count by tier and platform for summary
    tier_counts = {"free": 0, "premium": 0, "diamond": 0}
    platform_counts = {}

    for bm_data in bookmakers_data:
        # Set defaults
        if "country" not in bm_data:
            bm_data["country"] = "AU"
        if "default_source_type" not in bm_data:
            bm_data["default_source_type"] = "scrape"
        if "rate_limit_seconds" not in bm_data:
            bm_data["rate_limit_seconds"] = 3

        # Track counts
        tier = bm_data.get("scraping_config", {}).get("tier", "diamond")
        platform = bm_data.get("scraping_config", {}).get("platform", "unknown")
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
        platform_counts[platform] = platform_counts.get(platform, 0) + 1

        # Check if exists - update if so
        existing = db.query(Bookmaker).filter(Bookmaker.code == bm_data["code"]).first()
        if existing:
            # Update scraping_config and other fields
            for key, value in bm_data.items():
                setattr(existing, key, value)
            logger.info(f"Updated bookmaker: {bm_data['display_name']} ({tier})")
            continue

        bookmaker = Bookmaker(**bm_data)
        db.add(bookmaker)
        logger.info(f"Created bookmaker: {bm_data['display_name']} ({tier})")

    db.commit()

    # Summary
    logger.info("=" * 60)
    logger.info("BOOKMAKER SEEDING SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total bookmakers: {len(bookmakers_data)}")
    logger.info("")
    logger.info("By Tier:")
    for tier, count in sorted(tier_counts.items()):
        logger.info(f"  {tier.upper()}: {count}")
    logger.info("")
    logger.info("By Platform (scraper reuse opportunity):")
    for platform, count in sorted(platform_counts.items(), key=lambda x: -x[1]):
        logger.info(f"  {platform}: {count} bookmakers")
    logger.info("=" * 60)


def main():
    """Run seed"""
    logger.info("Seeding all bookmakers with platform groupings...")

    db = SessionLocal()
    try:
        seed_all_bookmakers(db)
        logger.info("✅ Database seeding completed!")

    except Exception as e:
        logger.error(f"❌ Seeding failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
