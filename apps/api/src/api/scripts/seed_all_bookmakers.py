"""
Seed all 100+ Australian bookmakers and 14 leagues.

This creates the complete database structure for the full platform,
but only activates bookmakers as scrapers are built.

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
    """Seed all 100+ Australian bookmakers"""
    logger.info("Seeding all bookmakers...")

    # Tier structure is CUMULATIVE:
    # - Free tier: TAB, Ladbrokes (2 bookmakers)
    # - Premium tier: Free + 13 more (15 total)
    # - Platinum tier: Premium + all others (100+ total)

    bookmakers_data = [
        # FREE TIER - Only these 2 for free users (ACTIVE NOW)
        {
            "code": "tab",
            "name": "TAB",
            "display_name": "TAB",
            "website_url": "https://www.tab.com.au",
            "is_active": True,
            "base_url": "https://api.beta.tab.com.au",
            "scraping_config": {"tier": "free", "platform": "proprietary", "difficulty": "medium"},
        },
        {
            "code": "ladbrokes",
            "name": "Ladbrokes",
            "display_name": "Ladbrokes",
            "website_url": "https://www.ladbrokes.com.au",
            "is_active": True,
            "base_url": "https://www.ladbrokes.com.au",
            "scraping_config": {"tier": "free", "platform": "entain", "difficulty": "medium"},
        },

        # PREMIUM TIER - These 13 bookmakers (INACTIVE - to be built)
        # Premium users get: Free (2) + Premium (13) = 15 total
        {
            "code": "sportsbet",
            "name": "Sportsbet",
            "display_name": "Sportsbet",
            "website_url": "https://www.sportsbet.com.au",
            "is_active": False,
            "scraping_config": {"tier": "premium", "platform": "proprietary", "difficulty": "hard"},
        },
        {
            "code": "neds",
            "name": "Neds",
            "display_name": "Neds",
            "website_url": "https://www.neds.com.au",
            "is_active": False,
            "scraping_config": {"tier": "premium", "platform": "entain", "difficulty": "medium"},
        },
        {
            "code": "betfair",
            "name": "Betfair Exchange",
            "display_name": "Betfair",
            "website_url": "https://www.betfair.com.au",
            "is_active": False,
            "api_endpoint": "https://api.betfair.com/exchange/betting/rest/v1.0",
            "default_source_type": "api",
            "scraping_config": {"tier": "premium", "platform": "exchange", "difficulty": "easy"},
        },
        {
            "code": "pointsbet",
            "name": "PointsBet",
            "display_name": "PointsBet",
            "website_url": "https://www.pointsbet.com.au",
            "is_active": False,
            "scraping_config": {"tier": "premium", "platform": "proprietary", "difficulty": "medium"},
        },
        {
            "code": "unibet",
            "name": "UniBet",
            "display_name": "UniBet",
            "website_url": "https://www.unibet.com.au",
            "is_active": False,
            "scraping_config": {"tier": "premium", "platform": "entain", "difficulty": "medium"},
        },
        {
            "code": "betr",
            "name": "Betr",
            "display_name": "Betr",
            "website_url": "https://www.betr.com.au",
            "is_active": False,
            "scraping_config": {"tier": "premium", "platform": "proprietary", "difficulty": "medium"},
        },
        {
            "code": "betdeluxe",
            "name": "BetDeluxe",
            "display_name": "BetDeluxe",
            "website_url": "https://www.betdeluxe.com.au",
            "is_active": False,
            "scraping_config": {"tier": "premium", "platform": "proprietary", "difficulty": "medium"},
        },
        {
            "code": "betright",
            "name": "BetRight",
            "display_name": "BetRight",
            "website_url": "https://www.betright.com.au",
            "is_active": False,
            "scraping_config": {"tier": "premium", "platform": "proprietary", "difficulty": "medium"},
        },
        {
            "code": "crossbet",
            "name": "CrossBet",
            "display_name": "CrossBet",
            "website_url": "https://www.crossbet.com.au",
            "is_active": False,
            "scraping_config": {"tier": "premium", "platform": "proprietary", "difficulty": "medium"},
        },
        {
            "code": "dabble",
            "name": "Dabble",
            "display_name": "Dabble",
            "website_url": "https://www.dabble.com.au",
            "is_active": False,
            "scraping_config": {"tier": "premium", "platform": "proprietary", "difficulty": "medium"},
        },
        {
            "code": "elitebet",
            "name": "EliteBet",
            "display_name": "EliteBet",
            "website_url": "https://www.elitebet.com.au",
            "is_active": False,
            "scraping_config": {"tier": "premium", "platform": "proprietary", "difficulty": "medium"},
        },
        {
            "code": "tabtouch",
            "name": "TABTouch",
            "display_name": "TABTouch",
            "website_url": "https://www.tabtouch.com.au",
            "is_active": False,
            "scraping_config": {"tier": "premium", "platform": "proprietary", "difficulty": "medium"},
        },
        {
            "code": "realbookie",
            "name": "Realbookie",
            "display_name": "Realbookie",
            "website_url": "https://www.realbookie.com.au",
            "is_active": False,
            "scraping_config": {"tier": "premium", "platform": "proprietary", "difficulty": "medium"},
        },
        {
            "code": "picklebet",
            "name": "Picklebet",
            "display_name": "Picklebet",
            "website_url": "https://www.picklebet.com",
            "is_active": False,
            "scraping_config": {"tier": "premium", "platform": "proprietary", "difficulty": "medium"},
        },

        # PLATINUM TIER - All other bookmakers (INACTIVE)
        # Platinum users get: Free (2) + Premium (13) + Platinum (85+) = 100+ total
        {"code": "playup", "name": "PlayUp", "display_name": "PlayUp", "website_url": "https://www.playup.com", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "boombet", "name": "BoomBet", "display_name": "BoomBet", "website_url": "https://www.boombet.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "betnation", "name": "BetNation", "display_name": "BetNation", "website_url": "https://www.betnation.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "mybet", "name": "MyBet", "display_name": "MyBet", "website_url": "https://www.mybet.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "goldbet", "name": "GoldBet", "display_name": "GoldBet", "website_url": "https://www.goldbet.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "bluebet", "name": "BlueBet", "display_name": "BlueBet", "website_url": "https://www.bluebet.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "palmerbet", "name": "Palmerbet", "display_name": "Palmerbet", "website_url": "https://www.palmerbet.com", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "topsport", "name": "TopSport", "display_name": "TopSport", "website_url": "https://www.topsport.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "alphabet", "name": "AlphaBet", "display_name": "AlphaBet", "website_url": "https://www.alphabetsports.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "baggybet", "name": "BaggyBet", "display_name": "BaggyBet", "website_url": "https://www.baggybet.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "bet575", "name": "Bet575", "display_name": "Bet575", "website_url": "https://www.bet575.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "bet66", "name": "Bet66", "display_name": "Bet66", "website_url": "https://www.bet66.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "bet777", "name": "Bet777", "display_name": "Bet777", "website_url": "https://www.bet777.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "betbetbet", "name": "BetBetBet", "display_name": "BetBetBet", "website_url": "https://www.betbetbet.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "betblitz", "name": "BetBlitz", "display_name": "BetBlitz", "website_url": "https://www.betblitz.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "betchamps", "name": "BetChamps", "display_name": "BetChamps", "website_url": "https://www.betchamps.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "betestate", "name": "BetEstate", "display_name": "BetEstate", "website_url": "https://www.betestate.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "betfocus", "name": "BetFocus", "display_name": "BetFocus", "website_url": "https://www.betfocus.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "betgalaxy", "name": "BetGalaxy", "display_name": "BetGalaxy", "website_url": "https://www.betgalaxy.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "betlocal", "name": "BetLocal", "display_name": "BetLocal", "website_url": "https://www.betlocal.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "betm", "name": "BetM", "display_name": "BetM", "website_url": "https://www.betm.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "betprofessor", "name": "BetProfessor", "display_name": "BetProfessor", "website_url": "https://www.betprofessor.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "betroyale", "name": "BetRoyale", "display_name": "BetRoyale", "website_url": "https://www.betroyale.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "betyoucan", "name": "BetYouCan", "display_name": "BetYouCan", "website_url": "https://www.betyoucan.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "bigbet", "name": "BigBet", "display_name": "BigBet", "website_url": "https://www.bigbet.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "blondebet", "name": "BlondeBet", "display_name": "BlondeBet", "website_url": "https://www.blondebet.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "boostbet", "name": "BoostBet", "display_name": "BoostBet", "website_url": "https://www.boostbet.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "bossbet", "name": "BossBet", "display_name": "BossBet", "website_url": "https://www.bossbet.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "buffalobet", "name": "BuffaloBet", "display_name": "BuffaloBet", "website_url": "https://www.buffalobet.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "cashcage", "name": "CashCage", "display_name": "CashCage", "website_url": "https://www.cashcage.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "chasebet", "name": "ChaseBet", "display_name": "ChaseBet", "website_url": "https://www.chasebet.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "chromabet", "name": "ChromaBet", "display_name": "ChromaBet", "website_url": "https://www.chromabet.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "diamondbet", "name": "DiamondBet", "display_name": "DiamondBet", "website_url": "https://www.diamondbet.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "dowbet", "name": "DowBet", "display_name": "DowBet", "website_url": "https://www.dowbet.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "fiestabet", "name": "FiestaBet", "display_name": "FiestaBet", "website_url": "https://www.fiestabet.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "gigabet", "name": "GigaBet", "display_name": "GigaBet", "website_url": "https://www.gigabet.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "goldenbet888", "name": "GoldenBet888", "display_name": "GoldenBet888", "website_url": "https://www.goldenbet888.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "goldenrush", "name": "GoldenRush", "display_name": "GoldenRush", "website_url": "https://www.goldenrush.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "havabet", "name": "HavaBet", "display_name": "HavaBet", "website_url": "https://www.havabet.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "hotbet", "name": "HotBet", "display_name": "HotBet", "website_url": "https://www.hotbet.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "jimmybet", "name": "JimmyBet", "display_name": "JimmyBet", "website_url": "https://www.jimmybet.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "juicybet", "name": "JuicyBet", "display_name": "JuicyBet", "website_url": "https://www.juicybet.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "junglebet", "name": "JungleBet", "display_name": "JungleBet", "website_url": "https://www.junglebet.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "justbet", "name": "JustBet", "display_name": "JustBet", "website_url": "https://www.justbet.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "letsbet", "name": "LetsBet", "display_name": "LetsBet", "website_url": "https://www.letsbet.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "lightningbet", "name": "LightningBet", "display_name": "LightningBet", "website_url": "https://www.lightningbet.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "marantellibet", "name": "MarantelliBet", "display_name": "MarantelliBet", "website_url": "https://www.marantellibet.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "midasbet", "name": "MidasBet", "display_name": "MidasBet", "website_url": "https://www.midasbet.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "mintbet", "name": "MintBet", "display_name": "MintBet", "website_url": "https://www.mintbet.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "noisy", "name": "Noisy", "display_name": "Noisy", "website_url": "https://www.noisy.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "okebet", "name": "OkeBet", "display_name": "OkeBet", "website_url": "https://www.okebet.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "oldgill", "name": "OldGill", "display_name": "OldGill", "website_url": "https://www.oldgill.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "picnicbet", "name": "PicnicBet", "display_name": "PicnicBet", "website_url": "https://www.picnicbet.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "playwest", "name": "PlayWest", "display_name": "PlayWest", "website_url": "https://www.playwest.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "ponybet", "name": "PonyBet", "display_name": "PonyBet", "website_url": "https://www.ponybet.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "premiumbet", "name": "PremiumBet", "display_name": "PremiumBet", "website_url": "https://www.premiumbet.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "pulsebet", "name": "PulseBet", "display_name": "PulseBet", "website_url": "https://www.pulsebet.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "punt123", "name": "Punt123", "display_name": "Punt123", "website_url": "https://www.punt123.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "puntcity", "name": "PuntCity", "display_name": "PuntCity", "website_url": "https://www.puntcity.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "puntgenie", "name": "PuntGenie", "display_name": "PuntGenie", "website_url": "https://www.puntgenie.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "puntnow", "name": "PuntNow", "display_name": "PuntNow", "website_url": "https://www.puntnow.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "puntzone", "name": "PuntZone", "display_name": "PuntZone", "website_url": "https://www.puntzone.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "questbet", "name": "QuestBet", "display_name": "QuestBet", "website_url": "https://www.questbet.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "readybet", "name": "ReadyBet", "display_name": "ReadyBet", "website_url": "https://www.readybet.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "robwaterhouse", "name": "Rob Waterhouse", "display_name": "Rob Waterhouse", "website_url": "https://www.robwaterhouse.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "slambet", "name": "SlamBet", "display_name": "SlamBet", "website_url": "https://www.slambet.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "starsports", "name": "StarSports", "display_name": "StarSports", "website_url": "https://www.starsports.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "sterlingparker", "name": "SterlingParker", "display_name": "SterlingParker", "website_url": "https://www.sterlingparker.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "sugarcastle", "name": "SugarCastle", "display_name": "SugarCastle", "website_url": "https://www.sugarcastle.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "surge", "name": "Surge", "display_name": "Surge", "website_url": "https://www.surge.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "swiftbet", "name": "SwiftBet", "display_name": "SwiftBet", "website_url": "https://www.swiftbet.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "templebet", "name": "TempleBet", "display_name": "TempleBet", "website_url": "https://www.templebet.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "terrybet", "name": "TerryBet", "display_name": "TerryBet", "website_url": "https://www.terrybet.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "titanbet", "name": "TitanBet", "display_name": "TitanBet", "website_url": "https://www.titanbet.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "topbet", "name": "TopBet", "display_name": "TopBet", "website_url": "https://www.topbet.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "tradiebet", "name": "TradieBet", "display_name": "TradieBet", "website_url": "https://www.tradiebet.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "truebet", "name": "TrueBet", "display_name": "TrueBet", "website_url": "https://www.truebet.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "ultrabet", "name": "UltraBet", "display_name": "UltraBet", "website_url": "https://www.ultrabet.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "upcoz", "name": "UpCoz", "display_name": "UpCoz", "website_url": "https://www.upcoz.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "vikingbet", "name": "VikingBet", "display_name": "VikingBet", "website_url": "https://www.vikingbet.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "vinbet", "name": "VinBet", "display_name": "VinBet", "website_url": "https://www.vinbet.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "volcanobet", "name": "VolcanoBet", "display_name": "VolcanoBet", "website_url": "https://www.volcanobet.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "wellbet", "name": "WellBet", "display_name": "WellBet", "website_url": "https://www.wellbet.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "winnersbet", "name": "WinnersBet", "display_name": "WinnersBet", "website_url": "https://www.winnersbet.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "wishbet", "name": "WishBet", "display_name": "WishBet", "website_url": "https://www.wishbet.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "wizbet", "name": "WizBet", "display_name": "WizBet", "website_url": "https://www.wizbet.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
        {"code": "zbet", "name": "ZBet", "display_name": "ZBet", "website_url": "https://www.zbet.com.au", "is_active": False, "scraping_config": {"tier": "platinum"}},
    ]

    for bm_data in bookmakers_data:
        # Set defaults
        if "country" not in bm_data:
            bm_data["country"] = "AU"
        if "default_source_type" not in bm_data:
            bm_data["default_source_type"] = "scrape"
        if "rate_limit_seconds" not in bm_data:
            bm_data["rate_limit_seconds"] = 3

        # Check if exists
        existing = db.query(Bookmaker).filter(Bookmaker.code == bm_data["code"]).first()
        if existing:
            logger.info(f"Bookmaker {bm_data['code']} exists, skipping")
            continue

        bookmaker = Bookmaker(**bm_data)
        db.add(bookmaker)
        logger.info(f"Created bookmaker: {bm_data['display_name']} ({bm_data.get('tier', 'diamond')})")

    db.commit()
    logger.info(f"✅ Seeded {len(bookmakers_data)} bookmakers")


def main():
    """Run seed"""
    logger.info("Seeding all bookmakers and leagues...")

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
