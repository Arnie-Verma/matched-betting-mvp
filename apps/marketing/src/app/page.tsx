import Link from "next/link";
import type { CSSProperties } from "react";
import {
  ArrowUpRight,
  ShieldCheck,
  Radar,
  Calculator,
  GraduationCap,
  Users,
  Sparkles,
  TrendingUp,
  Star,
} from "lucide-react";
import { appUrl } from "@/lib/site";

const highlights = [
  {
    title: "Odds matcher",
    description: "Compare bookmaker and exchange prices in real time to lock in profit.",
    icon: <Radar className="h-6 w-6" />,
  },
  {
    title: "Calculator suite",
    description: "Back/lay, dutching, EV, and multi calculators with instant outputs.",
    icon: <Calculator className="h-6 w-6" />,
  },
  {
    title: "Academy playbook",
    description: "Step-by-step lessons that show you exactly how to execute each offer.",
    icon: <GraduationCap className="h-6 w-6" />,
  },
  {
    title: "Profit tracking",
    description: "See every bet, outcome, and return so you always know your edge.",
    icon: <TrendingUp className="h-6 w-6" />,
  },
];

const steps = [
  {
    title: "Claim a bookmaker offer",
    description: "Start with an intro bonus from one of our supported Australian bookmakers.",
  },
  {
    title: "Match the odds",
    description: "Use the odds matcher to place a back and lay bet that covers all outcomes.",
  },
  {
    title: "Bank guaranteed profit",
    description: "No gambling, just math. Track profit in your dashboard as you scale.",
  },
];

const testimonials = [
  {
    name: "Sarah M",
    location: "Melbourne",
    quote: "The academy and calculators are crystal clear. I finally know exactly what to do.",
  },
  {
    name: "James T",
    location: "Sydney",
    quote: "I made my first A$420 in two weeks and the workflow felt safe the whole time.",
  },
  {
    name: "Emma D",
    location: "Brisbane",
    quote: "It feels like a system. I spend less time hunting offers and more time banking profit.",
  },
];

const plans = [
  {
    name: "Free",
    price: "A$0",
    description: "Get started with the essentials.",
    features: ["Academy access", "Core calculators", "2 bookmaker offers"],
  },
  {
    name: "Premium",
    price: "A$25",
    description: "Everything you need to scale weekly profit.",
    features: ["Odds matcher", "All calculators", "16 bookmakers", "Priority support"],
    accent: true,
  },
  {
    name: "Diamond",
    price: "A$35",
    description: "Full market coverage and power tools.",
    features: ["103+ bookmakers", "Advanced tools", "Custom alerts"],
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
                Built for Australia
              </p>
              <h1 className="display reveal" style={{ "--delay": "0.1s" } as CSSProperties}>
                Make matched betting feel simple, calm, and profitable.
              </h1>
              <p className="lead max-w-xl reveal" style={{ "--delay": "0.2s" } as CSSProperties}>
                MatchedBetting gives you the odds matcher, calculators, and academy to turn bookmaker promos
                into predictable profit. No guesswork, no gambling.
              </p>
              <div className="flex flex-col gap-3 sm:flex-row reveal" style={{ "--delay": "0.3s" } as CSSProperties}>
                <Link href={`${appUrl}/sign-up`} className="btn-primary">
                  Start free
                  <ArrowUpRight className="h-4 w-4" />
                </Link>
                <Link href="/features" className="btn-outline">
                  Explore features
                </Link>
              </div>
              <div className="flex flex-wrap gap-6 text-sm text-[var(--ink-muted)] reveal" style={{ "--delay": "0.4s" } as CSSProperties}>
                <div className="flex items-center gap-2">
                  <ShieldCheck className="h-4 w-4" />
                  Risk managed strategies
                </div>
                <div className="flex items-center gap-2">
                  <Users className="h-4 w-4" />
                  10,000+ members
                </div>
                <div className="flex items-center gap-2">
                  <Star className="h-4 w-4" />
                  4.9 average rating
                </div>
              </div>
            </div>

            <div className="relative">
              <div className="absolute -top-8 -left-6 h-32 w-32 rounded-full bg-[var(--accent)]/15 blur-2xl drift" aria-hidden="true"></div>
              <div className="absolute bottom-0 right-0 h-40 w-40 rounded-full bg-[var(--profit)]/15 blur-2xl float" aria-hidden="true"></div>

              <div className="surface p-6 md:p-8 grid-dots reveal" style={{ "--delay": "0.2s" } as CSSProperties}>
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs text-[var(--ink-muted)]">Bookmaker coverage</p>
                    <p className="text-2xl font-semibold">100+ brands</p>
                  </div>
                  <div className="h-12 w-12 rounded-2xl bg-[var(--brand)] text-white flex items-center justify-center">
                    <Sparkles className="h-5 w-5" />
                  </div>
                </div>

                <div className="mt-6 grid grid-cols-3 gap-3 text-center text-xs">
                  {["TAB", "Sportsbet", "Betfair", "Neds", "Ladbrokes", "Unibet"].map((label, index) => (
                    <div
                      key={label}
                      className="rounded-xl border border-[var(--border)] bg-white/80 py-4 font-semibold text-[var(--ink-muted)]"
                      style={{ animationDelay: `${index * 0.2}s` }}
                    >
                      {label}
                    </div>
                  ))}
                </div>

                <div className="mt-6 flex items-center justify-between rounded-2xl border border-[var(--border)] bg-white/80 px-4 py-3">
                  <div>
                    <p className="text-xs text-[var(--ink-muted)]">Average weekly profit</p>
                    <p className="text-lg font-semibold">A$420 - A$850</p>
                  </div>
                  <div className="text-xs text-[var(--ink-muted)]">Based on member results</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="section">
        <div className="container">
          <div className="grid gap-6 md:grid-cols-4">
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

      <section className="section">
        <div className="container">
          <div className="grid gap-10 md:grid-cols-[0.9fr_1.1fr] md:items-center">
            <div>
              <p className="eyebrow">How it works</p>
              <h2 className="mt-4 text-3xl md:text-4xl">A calm, repeatable workflow that pays out.</h2>
              <p className="mt-4 text-[var(--ink-muted)]">
                We guide you through each step so you never feel lost. Learn once, repeat weekly.
              </p>
              <Link href="/features" className="btn-outline mt-6">
                See the full system
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
          <div className="flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
            <div>
              <p className="eyebrow">Member stories</p>
              <h2 className="mt-4 text-3xl md:text-4xl">Proof that the process works.</h2>
            </div>
            <Link href={`${appUrl}/sign-up`} className="btn-ghost">
              Join the community
            </Link>
          </div>
          <div className="mt-8 grid gap-6 md:grid-cols-3">
            {testimonials.map((item, index) => (
              <div key={item.name} className="surface p-6 reveal" style={{ "--delay": `${0.1 * index}s` } as CSSProperties}>
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
          <div className="flex flex-col gap-8 md:flex-row md:items-end md:justify-between">
            <div>
              <p className="eyebrow">Pricing</p>
              <h2 className="mt-4 text-3xl md:text-4xl">Plans that match your pace.</h2>
              <p className="mt-4 text-[var(--ink-muted)]">Start free, then unlock more bookmakers when you are ready.</p>
            </div>
            <Link href="/pricing" className="btn-outline">
              View full pricing
            </Link>
          </div>
          <div className="mt-10 grid gap-6 md:grid-cols-3">
            {plans.map((plan) => (
              <div
                key={plan.name}
                className={`surface p-6 ${plan.accent ? "border-[var(--accent)]" : ""}`}
              >
                <h3 className="text-xl font-semibold">{plan.name}</h3>
                <p className="text-3xl font-semibold mt-3">{plan.price}</p>
                <p className="text-sm text-[var(--ink-muted)] mt-2">{plan.description}</p>
                <ul className="mt-6 space-y-2 text-sm text-[var(--ink-muted)]">
                  {plan.features.map((feature) => (
                    <li key={feature} className="flex items-center gap-2">
                      <Sparkles className="h-4 w-4 text-[var(--accent)]" />
                      {feature}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}
