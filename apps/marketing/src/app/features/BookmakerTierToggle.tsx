"use client";

import { useState } from "react";

type Tier = "premium" | "platinum";

const bookmakersByTier = {
  free: ["ladbrokes", "neds", "betfair"],
  premium: [
    "sportsbet",
    "ladbrokes",
    "neds",
    "tab",
    "pointsbet",
    "unibet",
    "betr",
    "betdeluxe",
    "betright",
    "crossbet",
    "dabble",
    "elitebet",
    "tabtouch",
    "realbookie",
    "picklebet",
    "betfair",
  ],
  platinum: [
    "alphabet",
    "baggybet",
    "bet575",
    "bet66",
    "bet777",
    "betbetbet",
    "betblitz",
    "betchamps",
    "betdeluxe",
    "betestate",
    "betfocus",
    "betgalaxy",
    "betgold",
    "betlocal",
    "betm",
    "betnation",
    "betprofessor",
    "betr",
    "betright",
    "betroyale",
    "betyoucan",
    "bigbet",
    "blondebet",
    "boombet",
    "boostbet",
    "bossbet",
    "buffalobet",
    "cashcage",
    "chasebet",
    "chromabet",
    "crossbet",
    "dabble",
    "diamondbet",
    "dowbet",
    "elitebet",
    "fiestaet",
    "gigabet",
    "goldbet",
    "goldenbet888",
    "goldenrush",
    "havabet",
    "hotbet",
    "jimmybet",
    "juicybet",
    "junglebet",
    "justbet",
    "ladbrokes",
    "letsbet",
    "lightningbet",
    "marantellibet",
    "midasbet",
    "mintbet",
    "mybet",
    "neds",
    "noisy",
    "okebet",
    "oldgill",
    "palmerbet",
    "picklebet",
    "picnicbet",
    "playup",
    "playwest",
    "pointsbet",
    "ponybet",
    "premiumbet",
    "pulsebet",
    "punt123",
    "puntcity",
    "puntgenie",
    "puntnow",
    "puntzone",
    "questbet",
    "readybet",
    "realbookie",
    "robwaterhouse",
    "slambet",
    "sportsbet",
    "starsports",
    "sterlingparker",
    "sugarcastle",
    "surge",
    "swiftbet",
    "tab",
    "tabtouch",
    "templebet",
    "terrybet",
    "titanbet",
    "topbet",
    "tradiebet",
    "truebet",
    "ultrabet",
    "unibet",
    "upcoz",
    "vikingbet",
    "vinbet",
    "volcanobet",
    "wellbet",
    "winnersbet",
    "wishbet",
    "wizbet",
    "zbet",
    "betfair",
  ],
} as const;

function dedupe(items: readonly string[]) {
  return Array.from(new Set(items));
}

const bookmakerNameOverrides: Record<string, string> = {
  tab: "TAB",
  tabtouch: "TABTouch",
  betfair: "Betfair",
  sportsbet: "Sportsbet",
  ladbrokes: "Ladbrokes",
  neds: "Neds",
  pointsbet: "PointsBet",
  unibet: "Unibet",
  betr: "Betr",
  betdeluxe: "BetDeluxe",
  betright: "BetRight",
  crossbet: "CrossBet",
  realbookie: "RealBookie",
  picklebet: "Picklebet",
  ultrabet: "UltraBet",
};

function formatBookmakerName(slug: string) {
  const normalized = slug.trim().toLowerCase();
  if (bookmakerNameOverrides[normalized]) {
    return bookmakerNameOverrides[normalized];
  }

  return normalized ? normalized[0].toUpperCase() + normalized.slice(1) : slug;
}

export function BookmakerTierToggle() {
  const [tier, setTier] = useState<Tier>("premium");
  const premiumList = dedupe(bookmakersByTier.premium).map(formatBookmakerName);
  const platinumList = dedupe(bookmakersByTier.platinum).map(formatBookmakerName);

  return (
    <div className="surface p-6 md:p-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="inline-flex rounded-full border border-[var(--border)] bg-white/70 p-1">
          <button
            type="button"
            aria-pressed={tier === "premium"}
            onClick={() => setTier("premium")}
            className={`rounded-full px-4 py-2 text-sm font-semibold transition ${
              tier === "premium" ? "bg-[var(--brand)] text-white shadow-sm" : "text-[var(--ink-muted)] hover:text-[var(--brand)]"
            }`}
          >
            Premium
          </button>
          <button
            type="button"
            aria-pressed={tier === "platinum"}
            onClick={() => setTier("platinum")}
            className={`rounded-full px-4 py-2 text-sm font-semibold transition ${
              tier === "platinum" ? "bg-[var(--brand)] text-white shadow-sm" : "text-[var(--ink-muted)] hover:text-[var(--brand)]"
            }`}
          >
            Platinum
          </button>
        </div>

        <p className="text-xs text-[var(--ink-muted)]">Bookmaker availability varies by plan and market conditions.</p>
      </div>

      <div className="mt-6">
        {tier === "premium" ? (
          <div className="space-y-3">
            <p className="text-sm text-[var(--ink-muted)]">
              Access odds matching across {premiumList.length}+ leading Australian bookmakers, including:
            </p>
            <p className="text-sm font-semibold text-[var(--ink)]">{premiumList.join(" · ")}</p>
            <p className="text-sm text-[var(--ink-muted)]">Designed for users scaling beyond beginner offers.</p>
          </div>
        ) : (
          <div className="space-y-3">
            <p className="text-sm text-[var(--ink-muted)]">
              Unlock 100+ Australian bookmakers, including niche and high-value platforms for advanced matched bettors.
            </p>
            <p className="text-sm font-semibold text-[var(--ink)]">Maximum coverage. Maximum opportunity.</p>
            <div className="mt-2 max-h-56 overflow-auto rounded-xl border border-[var(--border)] bg-white/70 p-3">
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {platinumList.map((name) => (
                  <div
                    key={name}
                    className="flex items-center justify-center rounded-xl border border-[var(--border)] bg-white/80 px-3 py-2 text-xs font-semibold text-[var(--ink)]"
                  >
                    {name}
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
