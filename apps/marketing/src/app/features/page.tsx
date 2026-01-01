import Link from "next/link";
import type { CSSProperties } from "react";
import {
  Radar,
  Calculator,
  GraduationCap,
  Users,
  ShieldCheck,
  Bell,
  ArrowUpRight,
} from "lucide-react";
import { appUrl } from "@/lib/site";

const featureBlocks = [
  {
    title: "Odds matcher",
    description: "Surface back and lay prices across bookmakers and exchanges so you always know the best edge.",
    icon: <Radar className="h-6 w-6" />,
  },
  {
    title: "Calculator toolbox",
    description: "Back/lay, dutching, multi, and EV calculators tuned for Australian markets.",
    icon: <Calculator className="h-6 w-6" />,
  },
  {
    title: "Academy",
    description: "Guided lessons with real examples, templates, and checklists to keep you on track.",
    icon: <GraduationCap className="h-6 w-6" />,
  },
  {
    title: "Community",
    description: "Stay aligned with a community of matched bettors sharing what is working now.",
    icon: <Users className="h-6 w-6" />,
  },
  {
    title: "Alerts",
    description: "Get notified when high value offers land so you can move fast.",
    icon: <Bell className="h-6 w-6" />,
  },
  {
    title: "Risk guardrails",
    description: "Use bankroll tracking and guardrails to keep every bet measured and consistent.",
    icon: <ShieldCheck className="h-6 w-6" />,
  },
];

export default function FeaturesPage() {
  return (
    <main>
      <section className="hero-bg section">
        <div className="container">
          <div className="grid gap-10 md:grid-cols-[1.1fr_0.9fr] md:items-center">
            <div>
              <p className="eyebrow">Product tour</p>
              <h1 className="mt-4 text-4xl md:text-5xl">Everything you need to run matched betting like a system.</h1>
              <p className="mt-4 text-[var(--ink-muted)]">
                Tools, training, and coverage built for the Australian market. Start free and scale as you go.
              </p>
              <div className="mt-6 flex flex-wrap gap-3">
                <Link href={`${appUrl}/sign-up`} className="btn-primary">
                  Start free
                  <ArrowUpRight className="h-4 w-4" />
                </Link>
                <Link href="/features/bookmakers" className="btn-outline">
                  Bookmaker coverage
                </Link>
              </div>
            </div>
            <div className="surface p-6 md:p-8 grid-dots">
              <div className="text-sm text-[var(--ink-muted)]">Feature stack</div>
              <div className="mt-4 space-y-3 text-sm">
                {[
                  "Odds matcher with exchange coverage",
                  "5 calculators for every bet type",
                  "Academy playbooks and checklists",
                  "Profit tracking dashboard",
                  "Alerts for high value promos",
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
          <div className="grid gap-6 md:grid-cols-3">
            {featureBlocks.map((item, index) => (
              <div
                key={item.title}
                className="surface p-6 reveal"
                style={{ "--delay": `${0.1 * index}s` } as CSSProperties}
              >
                <div className="mb-4 h-10 w-10 rounded-2xl bg-[var(--accent-soft)] flex items-center justify-center text-[var(--brand)]">
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
          <div className="surface p-8 md:p-10 flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
            <div>
              <h2 className="text-2xl md:text-3xl font-semibold">Want to see the bookmaker coverage?</h2>
              <p className="mt-2 text-[var(--ink-muted)]">
                Review tiers, supported platforms, and the roadmap for expanding coverage.
              </p>
            </div>
            <Link href="/features/bookmakers" className="btn-outline">
              View bookmakers
            </Link>
          </div>
        </div>
      </section>
    </main>
  );
}
