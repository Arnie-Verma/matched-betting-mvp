import Link from "next/link";
import { Check, ArrowUpRight, Sparkles } from "lucide-react";
import { appUrl } from "@/lib/site";

const plans = [
  {
    name: "Free",
    price: "A$0",
    cadence: "forever",
    description: "Start with the core playbook.",
    features: [
      "Matched betting academy",
      "Core calculators",
      "2 bookmaker offers",
      "Email support",
    ],
  },
  {
    name: "Premium",
    price: "A$25",
    cadence: "per month",
    description: "Scale your weekly matched betting routine.",
    features: [
      "Odds matcher",
      "All calculators",
      "16 bookmakers",
      "Priority support",
    ],
    highlight: true,
  },
  {
    name: "Platinum",
    price: "A$35",
    cadence: "per month",
    description: "Full market access and advanced tools.",
    features: [
      "103+ bookmakers",
      "Advanced tools",
      "Custom alerts",
      "Premium academy modules",
    ],
  },
];

export default function PricingPage() {
  return (
    <main>
      <section className="hero-bg section">
        <div className="container text-center">
          <p className="eyebrow">Pricing</p>
          <h1 className="mt-4 text-4xl md:text-5xl">Choose the plan that fits your pace.</h1>
          <p className="mt-4 text-[var(--ink-muted)] max-w-2xl mx-auto">
            Start free and upgrade when you are ready to unlock more bookmakers, tools, and support.
          </p>
        </div>
      </section>

      <section className="section">
        <div className="container">
          <div className="grid gap-6 md:grid-cols-3">
            {plans.map((plan) => (
              <div
                key={plan.name}
                className={`surface p-8 ${plan.highlight ? "border-[var(--accent)]" : ""}`}
              >
                {plan.highlight && (
                  <div className="badge mb-4">
                    <Sparkles className="h-3 w-3" />
                    Most popular
                  </div>
                )}
                <h2 className="text-2xl font-semibold">{plan.name}</h2>
                <div className="mt-4 flex items-end gap-2">
                  <span className="text-4xl font-semibold">{plan.price}</span>
                  <span className="text-sm text-[var(--ink-muted)]">{plan.cadence}</span>
                </div>
                <p className="mt-3 text-sm text-[var(--ink-muted)]">{plan.description}</p>
                <ul className="mt-6 space-y-3 text-sm">
                  {plan.features.map((feature) => (
                    <li key={feature} className="flex items-center gap-2 text-[var(--ink-muted)]">
                      <Check className="h-4 w-4 text-[var(--accent)]" />
                      {feature}
                    </li>
                  ))}
                </ul>
                <Link
                  href={`${appUrl}/sign-up`}
                  className={plan.highlight ? "btn-primary mt-6 w-full justify-center" : "btn-outline mt-6 w-full justify-center"}
                >
                  Start with {plan.name}
                  <ArrowUpRight className="h-4 w-4" />
                </Link>
              </div>
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}
