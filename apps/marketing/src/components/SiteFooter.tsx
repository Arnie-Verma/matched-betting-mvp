import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import { appUrl } from "@/lib/site";

const footerLinks = [
  { href: "/features", label: "Features" },
  { href: "/pricing", label: "Pricing" },
  { href: "/blog", label: "Blog" },
  { href: "/features/bookmakers", label: "Bookmakers" },
];

export default function SiteFooter() {
  return (
    <footer className="border-t border-black/10 bg-white">
      <div className="mx-auto max-w-6xl px-6 py-12">
        <div className="surface p-8 md:p-10 flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="badge">Ready to start</p>
            <h3 className="text-2xl md:text-3xl font-semibold mt-3">
              Turn bookmaker promos into steady profit.
            </h3>
            <p className="text-sm text-[var(--ink-muted)] mt-2 max-w-xl">
              Use the odds matcher, calculators, and academy to follow a proven matched betting playbook.
            </p>
          </div>
          <Link href={`${appUrl}/sign-up`} className="btn-primary">
            Create free account
            <ArrowUpRight className="h-4 w-4" />
          </Link>
        </div>

        <div className="mt-12 grid gap-8 md:grid-cols-[1.4fr_1fr_1fr]">
          <div>
            <div className="text-lg font-semibold">MatchedBetting</div>
            <p className="text-sm text-[var(--ink-muted)] mt-2">
              Matched betting tools built for Australia. Learn, calculate, and execute with confidence.
            </p>
          </div>
          <div>
            <div className="text-sm font-semibold">Explore</div>
            <div className="mt-3 space-y-2">
              {footerLinks.map((link) => (
                <Link key={link.href} href={link.href} className="block text-sm text-[var(--ink-muted)] hover:text-[var(--ink)]">
                  {link.label}
                </Link>
              ))}
            </div>
          </div>
          <div>
            <div className="text-sm font-semibold">Account</div>
            <div className="mt-3 space-y-2">
              <Link href={`${appUrl}/sign-in`} className="block text-sm text-[var(--ink-muted)] hover:text-[var(--ink)]">
                Log in
              </Link>
              <Link href={`${appUrl}/sign-up`} className="block text-sm text-[var(--ink-muted)] hover:text-[var(--ink)]">
                Sign up
              </Link>
            </div>
          </div>
        </div>

        <div className="mt-12 text-xs text-[var(--ink-muted)]">
          Matched betting is a strategy, not financial advice. Please check local regulations before betting.
        </div>
      </div>
    </footer>
  );
}
