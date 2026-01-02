import Link from "next/link";
import type { CSSProperties } from "react";
import { ArrowUpRight, BadgeCheck, Rocket, Layers } from "lucide-react";
import { appUrl } from "@/lib/site";

const tiers = [
  {
    name: "Free",
    description: "Start with the essentials.",
    accent: "bg-[var(--accent-soft)]",
    bookmakers: ["Ladbrokes", "Neds", "Betfair"],
  },
  {
    name: "Premium",
    description: "Unlock high value Australian operators.",
    accent: "bg-[var(--highlight)]/20",
    bookmakers: [
      "Sportsbet",
      "TAB",
      "PointsBet",
      "Unibet",
      "Betr",
      "BetDeluxe",
      "BetRight",
      "CrossBet",
      "Dabble",
      "EliteBet",
      "TABTouch",
      "RealBookie",
      "Picklebet",
    ],
  },
  {
    name: "Platinum",
    description: "103+ bookmakers across every major platform.",
    accent: "bg-[var(--brand)]/12",
    bookmakers: [
      "BetMakers network",
      "Punterstech brands",
      "Generation Web operators",
      "BetCloud bookmakers",
      "Standalone premium brands",
    ],
  },
];

const platforms = [
  {
    title: "Entain",
    detail: "Ladbrokes, Neds",
  },
  {
    title: "Kindred",
    detail: "Unibet",
  },
  {
    title: "Punterstech",
    detail: "21 bookmakers",
  },
  {
    title: "BetMakers",
    detail: "33 bookmakers",
  },
  {
    title: "Generation Web",
    detail: "22 bookmakers",
  },
  {
    title: "BetCloud",
    detail: "26 bookmakers",
  },
];

export default function BookmakersPage() {
  return (
    <main>
      <section className="hero-bg section">
        <div className="container">
          <div className="grid gap-8 md:grid-cols-[1.2fr_0.8fr] md:items-center">
            <div>
              <p className="eyebrow">Bookmaker coverage</p>
              <h1 className="mt-4 text-4xl md:text-5xl">Coverage built for Australia.</h1>
              <p className="mt-4 text-[var(--ink-muted)]">
                We map coverage by platform so you always know how many bookmakers are included at each tier.
              </p>
              <div className="mt-6 flex flex-wrap gap-3">
                <Link href={`${appUrl}/sign-up`} className="btn-primary">
                  Start free
                  <ArrowUpRight className="h-4 w-4" />
                </Link>
                <Link href="/pricing" className="btn-outline">
                  Compare plans
                </Link>
              </div>
            </div>
            <div className="surface p-6">
              <div className="flex items-center gap-3">
                <BadgeCheck className="h-5 w-5 text-[var(--accent)]" />
                <div>
                  <div className="text-sm text-[var(--ink-muted)]">Total coverage</div>
                  <div className="text-2xl font-semibold">103+ bookmakers</div>
                </div>
              </div>
              <div className="mt-6 grid gap-3 text-sm">
                {platforms.map((item) => (
                  <div
                    key={item.title}
                    className="flex items-center justify-between rounded-xl border border-[var(--border)] bg-white/70 px-3 py-2"
                  >
                    <span className="font-semibold">{item.title}</span>
                    <span className="text-[var(--ink-muted)]">{item.detail}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="section">
        <div className="container">
          <div className="grid gap-6 md:grid-cols-3">
            {tiers.map((tier, index) => (
              <div
                key={tier.name}
                className="surface p-6 reveal"
                style={{ "--delay": `${0.1 * index}s` } as CSSProperties}
              >
                <div className={`h-10 w-10 rounded-2xl ${tier.accent} flex items-center justify-center`}>
                  <Layers className="h-5 w-5" />
                </div>
                <h3 className="mt-4 text-xl font-semibold">{tier.name}</h3>
                <p className="mt-2 text-sm text-[var(--ink-muted)]">{tier.description}</p>
                <div className="mt-4 space-y-2 text-sm">
                  {tier.bookmakers.map((bookmaker) => (
                    <div key={bookmaker} className="flex items-center gap-2 text-[var(--ink-muted)]">
                      <span className="h-2 w-2 rounded-full bg-[var(--accent)]"></span>
                      {bookmaker}
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="section">
        <div className="container">
          <div className="surface p-8 md:p-10 flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
            <div>
              <div className="flex items-center gap-3">
                <Rocket className="h-5 w-5 text-[var(--accent)]" />
                <h2 className="text-2xl md:text-3xl font-semibold">Building coverage fast</h2>
              </div>
              <p className="mt-3 text-[var(--ink-muted)]">
                We are actively expanding platform scrapers so Platinum members get every Australian bookmaker.
              </p>
            </div>
            <Link href={`${appUrl}/sign-up`} className="btn-outline">
              Join the waitlist
            </Link>
          </div>
        </div>
      </section>
    </main>
  );
}
