import Link from "next/link";
import type { CSSProperties } from "react";
import {
  ArrowUpRight,
  ShieldCheck,
  Radar,
  Calculator,
  GraduationCap,
  Sparkles,
  TrendingUp,
  CheckCircle2,
  MessageCircle,
  ChevronDown,
} from "lucide-react";
import { appUrl } from "@/lib/site";

const heroBenefits = [
  "No subscription required",
  "No risk (when followed correctly)",
  "Works regardless of the result",
];

const bookmakers = ["TAB", "Sportsbet", "Betfair", "Ladbrokes", "Neds", "Unibet", "+ 90 more"];

const highlights = [
  {
    title: "Odds Matcher",
    description:
      "Lock in profit automatically. Compare bookmaker odds against exchanges in real time so every outcome is covered.",
    icon: <Radar className="h-6 w-6" />,
  },
  {
    title: "Calculator Suite",
    description:
      "Never guess your stakes. Back/lay, dutching, EV, and multi calculators handle all the math instantly.",
    icon: <Calculator className="h-6 w-6" />,
  },
  {
    title: "Academy Playbook",
    description:
      "Know exactly what to do, step by step. Clear lessons show you how to complete each offer safely and correctly.",
    icon: <GraduationCap className="h-6 w-6" />,
  },
  {
    title: "Profit Tracking",
    description:
      "See your real profit clearly. Track every bet, outcome, and return so you always know where you stand.",
    icon: <TrendingUp className="h-6 w-6" />,
  },
];

const steps = [
  {
    title: "Claim a bookmaker offer",
    description: "Start with a welcome bonus from one of our supported Australian bookmakers.",
  },
  {
    title: "Match the odds",
    description: "Use the odds matcher to place a back bet and a lay bet that together cover all outcomes.",
  },
  {
    title: "Lock in profit",
    description: "No matter what happens in the event, your profit is already secured up front.",
  },
];

const trialHighlights = [
  "Guaranteed profit when followed correctly",
  "No subscription or credit card required",
  "Designed for first-timers",
];

const testimonials = [
  {
    name: "Sarah M",
    location: "Melbourne",
    quote:
      "I was skeptical at first, but the step-by-step process made everything clear. I made my first $70 without stress.",
  },
  {
    name: "James T",
    location: "Sydney",
    quote: "I'm not great with numbers, but the calculators do everything for you. It finally clicked.",
  },
  {
    name: "Emma D",
    location: "Brisbane",
    quote: "It feels like a system, not gambling. I spend less time guessing and more time executing.",
  },
];

const faqs = [
  {
    question: "What if my bet loses?",
    answer:
      "In matched betting, you cover both outcomes. This means the result doesn't matter, the profit is built in before the event starts.",
  },
  {
    question: "Is matched betting gambling?",
    answer:
      "No. Matched betting removes chance by covering all outcomes. You're not relying on predictions or luck, so it doesn't feel like gambling at all.",
  },
  {
    question: "Is this legal in Australia?",
    answer:
      "Yes. Matched betting is a legal strategy in Australia. Bookmakers offer bonuses as marketing incentives, we're simply using those offers strategically.",
  },
  {
    question: "Is the $70 really guaranteed?",
    answer:
      "When the system is followed correctly, yes. The profit is mathematically locked in. The only real risk is human error, which is why we guide you step by step to prevent mistakes.",
  },
  {
    question: "How long does it take?",
    answer:
      "Most users spend about 20-30 minutes per offer. The entire free trial (two offers) can be completed in under an hour.",
  },
  {
    question: "Do I need math skills?",
    answer:
      "No. All calculations are handled automatically by the platform, so you won't need to do any math yourself.",
  },
];

const plans = [
  {
    name: "Free",
    price: "$0",
    badge: "Best for beginners",
    description: "Use the free trial to learn the system before upgrading.",
    features: [
      "Odds matcher tool for 2 bookmakers",
      "Make your first ~$70",
      "Learn the basics",
      "Core calculators",
    ],
    ctaLabel: "Start Free",
    ctaHref: `${appUrl}/sign-up`,
  },
  {
    name: "Premium",
    price: "$25/month",
    badge: "Most popular",
    description: "Tools to turn matched betting into a weekly routine.",
    features: [
      "Odds matcher tool for 16 bookmakers",
      "All calculators (incl. advanced)",
      "Priority support",
      "Premium academy courses",
    ],
    ctaLabel: "Upgrade to Premium",
    ctaHref: `${appUrl}/sign-up`,
    accent: true,
  },
  {
    name: "Platinum",
    price: "$35/month",
    badge: "Max coverage",
    description: "Full bookmaker access plus advanced courses to make thousands.",
    features: [
      "Odds matcher tool for 100+ bookmakers (full access)",
      "$1000s of dollars in sign up bonuses",
      "Includes all Premium features",
      "Platinum academy courses",
    ],
    ctaLabel: "Upgrade to Platinum",
    ctaHref: `${appUrl}/sign-up`,
  },
];

export default function HomePage() {
  return (
    <main>
      <section className="hero-bg section">
        <div className="container">
          <div className="grid gap-12 md:grid-cols-[1.1fr_0.9fr] md:items-center">
            <div className="stack-lg">
              <p className="eyebrow reveal" style={{ "--delay": "0s" } as CSSProperties}>
                Make your first $70
              </p>
              <h1 className="display reveal" style={{ "--delay": "0.1s" } as CSSProperties}>
                Make your first $70 guaranteed with matched betting.
              </h1>
              <p className="lead max-w-xl reveal" style={{ "--delay": "0.2s" } as CSSProperties}>
                Turn Australian bookmaker promotions into guaranteed profit by betting on both outcomes, no gambling, no
                guesswork, no experience required.
              </p>
              <div className="flex flex-col gap-3 sm:flex-row reveal" style={{ "--delay": "0.3s" } as CSSProperties}>
                <Link href={`${appUrl}/sign-up`} className="btn-primary btn-hero">
                  Start free - Make your first $70
                  <ArrowUpRight className="h-4 w-4" />
                </Link>
                <Link href="#how-it-works" className="btn-outline btn-hero">
                  See how matched betting works
                </Link>
              </div>
              <div
                className="flex flex-wrap gap-4 text-sm text-[var(--ink-muted)] reveal"
                style={{ "--delay": "0.4s" } as CSSProperties}
              >
                {heroBenefits.map((benefit) => (
                  <div key={benefit} className="flex items-center gap-2">
                    <CheckCircle2 className="h-4 w-4 text-[var(--profit)]" />
                    {benefit}
                  </div>
                ))}
              </div>
              <p className="text-sm text-[var(--ink-muted)] max-w-xl reveal" style={{ "--delay": "0.5s" } as CSSProperties}>
                Matched betting removes risk by covering all outcomes using bookmaker bonuses and exchange bets.
              </p>
            </div>

            <div className="relative">
              <div
                className="absolute -top-8 -left-6 h-32 w-32 rounded-full bg-[var(--accent)]/15 blur-2xl drift"
                aria-hidden="true"
              ></div>
              <div
                className="absolute bottom-0 right-0 h-40 w-40 rounded-full bg-[var(--profit)]/15 blur-2xl float"
                aria-hidden="true"
              ></div>

              <div className="surface p-6 md:p-8 grid-dots reveal" style={{ "--delay": "0.2s" } as CSSProperties}>
                <div className="flex items-start justify-between gap-6">
                  <div>
                    <p className="text-xs text-[var(--ink-muted)]">Bookmaker coverage</p>
                    <p className="text-2xl font-semibold">Access 100+ Australian bookmakers in one system</p>
                  </div>
                  <div className="h-12 w-12 rounded-2xl bg-[var(--brand)] text-white flex items-center justify-center">
                    <Sparkles className="h-5 w-5" />
                  </div>
                </div>

                <p className="mt-4 text-sm text-[var(--ink-muted)]">
                  Use introductory offers from Australia&apos;s major bookmakers and safely turn them into profit using our
                  tools.
                </p>

                <div className="mt-6 grid grid-cols-3 gap-3">
                  {bookmakers.map((bookmaker, index) => (
                    <div
                      key={bookmaker}
                      className="flex items-center justify-center rounded-xl border border-[var(--border)] bg-white/80 px-3 py-3"
                      style={{ animationDelay: `${index * 0.2}s` }}
                    >
                      <span className="text-sm font-semibold text-[var(--ink)]">{bookmaker}</span>
                    </div>
                  ))}
                </div>

                <p className="mt-4 text-xs text-[var(--ink-muted)]">
                  Supported bookmakers include: TAB, Sportsbet, Betfair, Ladbrokes, Neds, Unibet, + 90 more.
                </p>

                <div className="mt-6 rounded-2xl border border-[var(--border)] bg-white/80 px-4 py-3">
                  <div className="flex items-center gap-2 text-sm font-semibold">
                    <ShieldCheck className="h-4 w-4 text-[var(--profit)]" />
                    Free trial starts with 2 bookmakers
                  </div>
                  <p className="mt-2 text-xs text-[var(--ink-muted)]">
                    The free trial starts you off with just 2 bookmakers, letting you learn the system safely before you
                    scale up.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="section">
        <div className="container">
          <div className="flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
            <div>
              <p className="eyebrow">Proof the system works</p>
              <h2 className="mt-4 text-3xl md:text-4xl">Proof the system works.</h2>
            </div>
          </div>
          <div className="mt-8 grid gap-6 md:grid-cols-3">
            {testimonials.map((item, index) => (
              <div key={item.name} className="surface p-6 reveal" style={{ "--delay": `${0.1 * index}s` } as CSSProperties}>
                <div className="mb-4 h-10 w-10 rounded-2xl bg-[var(--accent-soft)] text-[var(--brand)] flex items-center justify-center">
                  <MessageCircle className="h-5 w-5" />
                </div>
                <p className="text-sm text-[var(--ink-muted)]">{item.quote}</p>
                <div className="mt-6 flex items-center justify-between text-sm">
                  <span className="font-semibold">{item.name}</span>
                  <span className="text-[var(--ink-muted)]">{item.location}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="section">
        <div className="container">
          <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
            <div>
              <p className="eyebrow">Everything you need</p>
              <h2 className="mt-4 text-3xl md:text-4xl">Everything you need to profit, nothing you don&apos;t.</h2>
            </div>
          </div>
          <div className="mt-10 grid gap-6 md:grid-cols-2 lg:grid-cols-4">
            {highlights.map((item, index) => (
              <div
                key={item.title}
                className="surface p-6 reveal"
                style={{ "--delay": `${0.1 * index}s` } as CSSProperties}
              >
                <div className="mb-4 h-10 w-10 rounded-2xl bg-[var(--accent-soft)] text-[var(--brand)] flex items-center justify-center">
                  {item.icon}
                </div>
                <h3 className="text-lg font-semibold">{item.title}</h3>
                <p className="mt-2 text-sm text-[var(--ink-muted)]">{item.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="how-it-works" className="section">
        <div className="container">
          <div className="grid gap-10 md:grid-cols-[0.9fr_1.1fr] md:items-center">
            <div>
              <p className="eyebrow">How it works</p>
              <h2 className="mt-4 text-3xl md:text-4xl">A simple, repeatable system you can use every week.</h2>
              <p className="mt-4 text-[var(--ink-muted)]">
                Learn it once, then repeat it whenever new bookmaker offers appear.
              </p>
              <Link href="/features" className="btn-outline mt-6">
                See the full system
                <ArrowUpRight className="h-4 w-4" />
              </Link>
            </div>
            <div className="space-y-4">
              {steps.map((step, index) => (
                <div key={step.title} className="surface p-6 reveal" style={{ "--delay": `${0.1 * index}s` } as CSSProperties}>
                  <div className="flex items-start gap-4">
                    <div className="h-10 w-10 rounded-full bg-[var(--brand)] text-white flex items-center justify-center font-semibold">
                      {index + 1}
                    </div>
                    <div>
                      <h3 className="text-lg font-semibold">{step.title}</h3>
                      <p className="mt-2 text-sm text-[var(--ink-muted)]">{step.description}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="section">
        <div className="container">
          <div className="surface p-8 md:p-10 relative overflow-hidden">
            <div
              className="absolute -top-16 right-0 h-40 w-40 rounded-full bg-[var(--accent)]/20 blur-3xl"
              aria-hidden="true"
            ></div>
            <div
              className="absolute -bottom-20 left-10 h-40 w-40 rounded-full bg-[var(--profit)]/15 blur-3xl"
              aria-hidden="true"
            ></div>
            <div className="relative grid gap-8 md:grid-cols-[1.1fr_0.9fr] md:items-center">
              <div>
                <p className="eyebrow">Free trial</p>
                <h2 className="mt-4 text-3xl md:text-4xl">Make your first $70. No fee. No risk.</h2>
                <p className="mt-4 text-[var(--ink-muted)]">
                  Our free trial walks you through two real bookmaker offers step by step so you can see the proof for
                  yourself before spending a cent. You&apos;ll know exactly how matched betting works before upgrading.
                </p>
              </div>
              <div className="space-y-4">
                {trialHighlights.map((item) => (
                  <div key={item} className="flex items-center gap-2 text-sm text-[var(--ink-muted)]">
                    <CheckCircle2 className="h-4 w-4 text-[var(--profit)]" />
                    {item}
                  </div>
                ))}
                <Link href={`${appUrl}/sign-up`} className="btn-primary w-full justify-center flex-wrap text-center">
                  Start free and make your first $70
                  <ArrowUpRight className="h-4 w-4" />
                </Link>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section id="pricing" className="section">
        <div className="container">
          <div className="flex flex-col gap-8 md:flex-row md:items-end md:justify-between">
            <div>
              <p className="eyebrow">Pricing</p>
              <h2 className="mt-4 text-3xl md:text-4xl">Start free. Upgrade when you&apos;re ready.</h2>
              <p className="mt-4 text-[var(--ink-muted)]">
                No lock-ins, no pressure, and no credit card needed, use the free trial to learn the system first.
              </p>
            </div>
          </div>
          <div className="mt-10 grid gap-6 md:grid-cols-3">
            {plans.map((plan) => (
              <div
                key={plan.name}
                className={`surface p-6 flex h-full flex-col ${
                  plan.accent ? "border-[var(--accent)] shadow-[0_25px_60px_-45px_rgba(41,87,213,0.9)]" : ""
                }`}
              >
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="text-xl font-semibold">{plan.name}</h3>
                    <p className="text-3xl font-semibold mt-3">{plan.price}</p>
                  </div>
                  <span className="badge">{plan.badge}</span>
                </div>
                {plan.description ? (
                  <p className="text-sm text-[var(--ink-muted)] mt-4">{plan.description}</p>
                ) : null}
                <ul className="mt-6 space-y-2 text-sm text-[var(--ink-muted)] flex-1">
                  {plan.features.map((feature) => (
                    <li key={feature} className="flex items-center gap-2">
                      <Sparkles className="h-4 w-4 text-[var(--accent)]" />
                      {feature}
                    </li>
                  ))}
                </ul>
                <Link
                  href={plan.ctaHref}
                  className={`${plan.accent ? "btn-primary" : "btn-outline"} mt-6 w-full justify-center`}
                >
                  {plan.ctaLabel}
                  <ArrowUpRight className="h-4 w-4" />
                </Link>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="faq" className="section">
        <div className="container">
          <div className="max-w-2xl">
            <p className="eyebrow">Frequently asked questions</p>
            <h2 className="mt-4 text-3xl md:text-4xl">Frequently asked questions</h2>
          </div>
          <div className="mt-8 space-y-4">
            {faqs.map((faq) => (
              <details key={faq.question} className="surface-flat p-6 group">
                <summary className="flex cursor-pointer items-center justify-between text-base font-semibold">
                  {faq.question}
                  <ChevronDown className="h-4 w-4 text-[var(--ink-muted)] transition-transform duration-200 group-open:rotate-180" />
                </summary>
                <p className="mt-3 text-sm text-[var(--ink-muted)]">{faq.answer}</p>
              </details>
            ))}
          </div>
        </div>
      </section>

      <section className="section">
        <div className="container">
          <div className="relative overflow-hidden rounded-[var(--radius)] border border-[var(--border)] bg-[var(--brand)] text-white p-8 md:p-12">
            <div
              className="absolute -top-16 left-10 h-40 w-40 rounded-full bg-white/10 blur-3xl"
              aria-hidden="true"
            ></div>
            <div
              className="absolute bottom-0 right-0 h-52 w-52 rounded-full bg-[var(--accent)]/30 blur-3xl"
              aria-hidden="true"
            ></div>
            <div className="relative grid gap-6 md:grid-cols-[1.4fr_0.6fr] md:items-center">
              <div>
                <p className="text-xs uppercase tracking-[0.2em] text-white/70">Start with one offer</p>
                <h2 className="mt-3 text-3xl md:text-4xl font-semibold">
                  Start with one offer. Learn the system. Repeat weekly.
                </h2>
                <p className="mt-4 text-sm text-white/80 max-w-xl">
                  Create a free account and see exactly how matched betting works in Australia, then rinse and repeat
                  for steady side income.
                </p>
              </div>
              <div className="flex flex-col gap-3">
                <Link href={`${appUrl}/sign-up`} className="btn-primary w-full justify-center flex-wrap text-center">
                  Create free account - Make your first $70
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
