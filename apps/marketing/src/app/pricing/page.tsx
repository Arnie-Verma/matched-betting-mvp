import Link from "next/link";
import { Check, ArrowUpRight, Sparkles } from "lucide-react";
import { appUrl } from "@/lib/site";

const plans = [
  {
    name: "Free",
    price: "$0",
    cadence: "/ month",
    badge: "Best for learning the system",
    tagline: "Start learning matched betting risk-free",
    sectionLabel: "What you get",
    features: [
      "Odds matcher with limited bookmaker coverage",
      "Core calculators (back & lay)",
      "Academy fundamentals",
      "Make your first ~$70",
      "No credit card required",
    ],
    cta: "Start free",
    ctaHref: `${appUrl}/sign-up`,
    ctaVariant: "btn-outline",
  },
  {
    name: "Premium",
    price: "$25",
    cadence: "/ month",
    badge: "Most Popular",
    tagline: "Built to scale profit efficiently",
    sectionLabel: "What you unlock",
    features: [
      "Odds matcher with expanded bookmaker coverage",
      "Advanced calculators",
      "Premium academy modules",
      "Earn 20x your subscription fee in deposit bonuses",
      "Priority support",
    ],
    highlight: true,
    cta: "Upgrade to Premium",
    ctaHref: `${appUrl}/sign-up`,
    ctaVariant: "btn-primary",
  },
  {
    name: "Platinum",
    price: "$35",
    cadence: "/ month",
    badge: "Most Profitable",
    tagline: "Maximum coverage. Maximum opportunity.",
    sectionLabel: "What you unlock",
    features: [
      "Odds matcher with full market coverage (100+ bookmakers)",
      "Access to niche and high-value bookmakers",
      "More sign-up and reload offers",
      "Higher long-term profit potential",
      "Everything in Premium",
    ],
    cta: "Upgrade to Platinum",
    ctaHref: `${appUrl}/sign-up`,
    ctaVariant: "btn-outline",
  },
];

export default function PricingPage() {
  return (
    <main>
      <section className="hero-bg section">
        <div className="container text-center">
          <p className="eyebrow">Pricing</p>
          <h1 className="mt-4 text-4xl md:text-5xl">
            Simple, transparent pricing.
            <span className="block mt-2">Start free. Upgrade when you’re ready to scale.</span>
          </h1>
          <p className="mt-4 text-[var(--ink-muted)] max-w-2xl mx-auto">
            No lock-ins. No hidden fees.
            <span className="block mt-2">Prove the system first, then unlock more profit opportunities.</span>
          </p>
        </div>
      </section>

      <section id="plans" className="section">
        <div className="container">
          <div className="grid gap-6 md:grid-cols-3">
            {plans.map((plan) => (
              <div
                key={plan.name}
                className={`surface p-8 flex flex-col ${plan.highlight ? "border-[var(--accent)]" : ""}`}
              >
                {plan.badge ? (
                  <div className="badge mb-4 w-fit">
                    {plan.highlight ? <Sparkles className="h-3 w-3" /> : null}
                    {plan.badge}
                  </div>
                ) : null}
                <h2 className="text-2xl font-semibold">{plan.name}</h2>
                <div className="mt-4 flex items-end gap-2">
                  <span className="text-4xl font-semibold">{plan.price}</span>
                  <span className="text-sm text-[var(--ink-muted)]">{plan.cadence}</span>
                </div>
                <p className="mt-3 text-sm text-[var(--ink-muted)]">{plan.tagline}</p>

                <div className="mt-6 text-sm font-semibold">{plan.sectionLabel}</div>
                <ul className="mt-4 space-y-3 text-sm flex-1">
                  {plan.features.map((feature) => (
                    <li key={feature} className="flex items-center gap-2 text-[var(--ink-muted)]">
                      <Check className="h-4 w-4 shrink-0 text-[var(--accent)]" />
                      {feature}
                    </li>
                  ))}
                </ul>

                <Link
                  href={plan.ctaHref}
                  className={`${plan.ctaVariant} mt-6 w-full justify-center`}
                >
                  {plan.cta}
                  <ArrowUpRight className="h-4 w-4" />
                </Link>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="section">
        <div className="container">
          <div className="max-w-2xl">
            <p className="eyebrow">Plan Comparison</p>
            <h2 className="mt-4 text-3xl md:text-4xl">Still deciding? Here’s exactly what’s included</h2>
            <p className="mt-4 text-[var(--ink-muted)]">
              All plans use the same core matched betting system. Premium and Platinum unlock speed, coverage, and
              scale.
            </p>
          </div>

          <div className="mt-8 overflow-x-auto">
            <table className="min-w-[860px] w-full border-separate border-spacing-0">
              <thead>
                <tr>
                  <th className="text-left text-xs uppercase tracking-[0.18em] text-[var(--ink-muted)] pb-3 pr-4">
                    Feature / Outcome
                  </th>
                  <th className="text-left text-xs uppercase tracking-[0.18em] text-[var(--ink-muted)] pb-3 pr-4">
                    Free ($0)
                  </th>
                  <th className="text-left text-xs uppercase tracking-[0.18em] text-[var(--ink-muted)] pb-3 pr-4">
                    Premium ($25)
                  </th>
                  <th className="text-left text-xs uppercase tracking-[0.18em] text-[var(--ink-muted)] pb-3">
                    Platinum ($35)
                  </th>
                </tr>
              </thead>
              <tbody>
                {[
                  {
                    label: "Profit opportunities (bookmakers)",
                    free: "Limited",
                    premium: "Expanded (16)",
                    platinum: "100+ full coverage",
                  },
                  { label: "Odds matcher", free: "Limited", premium: "✔ Advanced", platinum: "✔ Advanced" },
                  { label: "Advanced calculators", free: "—", premium: "✔", platinum: "✔" },
                  {
                    label: "Academy access",
                    free: "Fundamentals",
                    premium: "✔ Advanced modules",
                    platinum: "✔ Advanced modules",
                  },
                  { label: "Priority support", free: "—", premium: "✔", platinum: "✔" },
                  {
                    label: "Best for",
                    free: "Learning the system",
                    premium: "Scaling weekly profit",
                    platinum: "Maximum profit ceiling",
                  },
                  { label: "Discord Community", free: "✔", premium: "✔", platinum: "✔" },
                ].map((row) => (
                  <tr key={row.label}>
                    <td className="py-4 pr-4 border-t border-[var(--border)] font-semibold">{row.label}</td>
                    <td className="py-4 pr-4 border-t border-[var(--border)] text-[var(--ink-muted)]">{row.free}</td>
                    <td className="py-4 pr-4 border-t border-[var(--border)] text-[var(--ink-muted)]">{row.premium}</td>
                    <td className="py-4 border-t border-[var(--border)] text-[var(--ink-muted)]">{row.platinum}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <section className="section">
        <div className="container">
          <div className="surface p-8 md:p-10 flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
            <div className="max-w-2xl">
              <h2 className="text-2xl md:text-3xl font-semibold">Not sure which plan is right for you?</h2>
              <p className="mt-3 text-[var(--ink-muted)]">
                Start free, make your first profit, and upgrade when you want to move faster and access more
                bookmakers. You can upgrade, downgrade, or cancel anytime.
              </p>
            </div>
            <div className="flex flex-col gap-3 w-full md:w-auto">
              <Link href={`${appUrl}/sign-up`} className="btn-primary w-full md:w-auto justify-center">
                Start free
                <ArrowUpRight className="h-4 w-4" />
              </Link>
              <Link href="#plans" className="btn-outline w-full md:w-auto justify-center">
                See pricing &amp; upgrade
              </Link>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
