import Link from "next/link";
import {
  Radar,
  Calculator,
  GraduationCap,
  ArrowUpRight,
  CheckCircle2,
  TrendingUp,
  MessageCircle,
} from "lucide-react";
import { appUrl } from "@/lib/site";
import { BookmakerTierToggle } from "./BookmakerTierToggle";

const premiumFeatures = [
  {
    title: "Odds matcher with expanded bookmaker coverage",
    lead: "Compare odds across more bookmakers and exchanges at once.",
    description:
      "Premium unlocks expanded bookmaker coverage inside the odds matcher, allowing you to compare prices across many more platforms in a single view.",
    icon: <Radar className="h-6 w-6" />,
  },
  {
    title: "Advanced matched betting calculators",
    lead: "Calculate stake size, liability, and EV automatically so every bet is sized correctly as stakes increase.",
    description: "Prevents costly human error.",
    icon: <Calculator className="h-6 w-6" />,
  },
  {
    title: "Premium academy courses",
    lead: "Learn advanced techniques around account sustainability, betting exchanges, and long-term scaling.",
    description: "Extend account lifespan and increase total profit.",
    icon: <GraduationCap className="h-6 w-6" />,
  },
  {
    title: "Premium community access",
    lead: "Stay aligned with other active matched bettors sharing what’s working across Australian bookmakers, without tips, noise, or gambling hype.",
    description: "Insight without speculation.",
    icon: <MessageCircle className="h-6 w-6" />,
  },
];

export default function FeaturesPage() {
  return (
    <main>
      <section className="hero-bg section">
        <div className="container">
          <div className="grid gap-10 md:grid-cols-[1.1fr_0.9fr] md:items-center">
            <div className="stack-lg">
              <div className="stack-sm">
                <p className="eyebrow">Upgrade</p>
                <h1 className="mt-4 text-4xl md:text-5xl">
                  Upgrade to Premium to maximise your matched betting profits
                </h1>
                <p className="mt-4 text-[var(--ink-muted)]">
                  Unlock broader bookmaker coverage, advanced tools, and higher profit ceilings.
                  <span className="block mt-2">Free proves the system, Premium and Platinum scale it.</span>
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-3">
                <Link href="/pricing" className="btn-primary btn-hero">
                  See pricing &amp; upgrade
                  <ArrowUpRight className="h-4 w-4" />
                </Link>
                <Link href={`${appUrl}/sign-up`} className="btn-ghost btn-hero">
                  Start free
                </Link>
              </div>
              <div className="flex items-center gap-2 text-sm text-[var(--ink-muted)]">
                <CheckCircle2 className="h-4 w-4 text-[var(--profit)]" />
                Most users upgrade once they’ve covered their subscription cost
              </div>
            </div>

            <div className="surface p-6 md:p-8 grid-dots">
              <div className="text-sm text-[var(--ink-muted)]">What upgrading unlocks</div>
              <div className="mt-4 space-y-3 text-sm">
                {[
                  "More bookmakers inside the odds matcher",
                  "Advanced calculators as stakes grow",
                  "Dutching workflows for more opportunities",
                  "Premium academy + community insights",
                ].map((item) => (
                  <div key={item} className="flex items-center gap-3">
                    <div className="h-2 w-2 rounded-full bg-[var(--accent)]"></div>
                    <span>{item}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="section">
        <div className="container">
          <div className="max-w-2xl">
            <p className="eyebrow">Supported bookmakers</p>
            <h2 className="mt-4 text-3xl md:text-4xl">Supported bookmakers (Premium &amp; Platinum)</h2>
            <p className="mt-4 text-[var(--ink-muted)]">
              Our paid plans unlock odds comparison across Australia’s major bookmakers — allowing you to extract value
              wherever it appears.
            </p>
          </div>
          <div className="mt-8">
            <BookmakerTierToggle />
          </div>
        </div>
      </section>

      <section className="section">
        <div className="container">
          <div className="relative overflow-hidden rounded-[var(--radius)] border border-[var(--border)] bg-[var(--brand)] text-white p-8 md:p-12">
            <div className="absolute -top-16 left-10 h-40 w-40 rounded-full bg-white/10 blur-3xl" aria-hidden="true" />
            <div
              className="absolute bottom-0 right-0 h-52 w-52 rounded-full bg-[var(--accent)]/30 blur-3xl"
              aria-hidden="true"
            />
            <div className="relative grid gap-6 md:grid-cols-[1.2fr_0.8fr] md:items-center">
              <div>
                <div className="flex items-center gap-2 text-white/80">
                  <TrendingUp className="h-5 w-5" />
                  <p className="text-xs uppercase tracking-[0.2em]">Price justification</p>
                </div>
                <h2 className="mt-3 text-3xl md:text-4xl font-semibold">
                  Earn up to 20× your subscription cost in bookmaker bonuses
                </h2>
                <p className="mt-4 text-sm text-white/80">
                  Premium and Platinum unlock full odds matching, helping you maximise bonus retention and minimise
                  qualifying losses across thousands of matched bets. Many users recover their subscription cost within
                  their first few offers.
                </p>
              </div>
              <div className="flex flex-col gap-3">
                <Link href="/pricing" className="btn-primary w-full justify-center flex-wrap text-center">
                  See pricing &amp; upgrade
                  <ArrowUpRight className="h-4 w-4" />
                </Link>
                <Link href={`${appUrl}/sign-up`} className="btn-outline w-full justify-center">
                  Start free
                </Link>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="section">
        <div className="container">
          <div className="max-w-2xl">
            <p className="eyebrow">Premium features</p>
            <h2 className="mt-4 text-3xl md:text-4xl">Premium features built for scale</h2>
            <p className="mt-4 text-[var(--ink-muted)]">
              Premium and Platinum are designed to increase speed, coverage, and profit retention as you scale beyond
              beginner offers.
            </p>
          </div>
          <div className="mt-10 grid gap-6 md:grid-cols-2">
            {premiumFeatures.map((feature) => (
              <div key={feature.title} className="surface p-6">
                <div className="mb-4 h-10 w-10 rounded-2xl bg-[var(--accent-soft)] flex items-center justify-center text-[var(--brand)]">
                  {feature.icon}
                </div>
                <h3 className="text-lg font-semibold">{feature.title}</h3>
                <p className="mt-2 text-sm text-[var(--ink-muted)]">{feature.lead}</p>
                <p className="mt-3 text-sm text-[var(--ink-muted)]">{feature.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="section">
        <div className="container">
          <div className="relative overflow-hidden rounded-[var(--radius)] border border-[var(--border)] bg-[var(--surface)] p-8 md:p-12">
            <div className="absolute -top-16 left-10 h-40 w-40 rounded-full bg-[var(--accent)]/10 blur-3xl" aria-hidden="true" />
            <div
              className="absolute bottom-0 right-0 h-52 w-52 rounded-full bg-[var(--highlight)]/25 blur-3xl"
              aria-hidden="true"
            />
            <div className="relative grid gap-6 md:grid-cols-[1.4fr_0.6fr] md:items-center">
              <div>
                <h2 className="text-3xl md:text-4xl font-semibold">
                  Choose the plan that unlocks more profit opportunities
                </h2>
                <p className="mt-4 text-[var(--ink-muted)] max-w-2xl">
                  Free shows you how it works. Premium and Platinum unlock speed, coverage, and scale.
                </p>
              </div>
              <div className="flex flex-col gap-3">
                <Link href="/pricing" className="btn-primary w-full justify-center flex-wrap text-center">
                  See pricing &amp; upgrade
                  <ArrowUpRight className="h-4 w-4" />
                </Link>
              </div>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
