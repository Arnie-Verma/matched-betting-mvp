import Link from "next/link";
import { appUrl } from "@/lib/site";

const footerLinks = [
  { href: "/features", label: "Features" },
  { href: "/pricing", label: "Pricing" },
  { href: "/blog", label: "Blog" },
  { href: "/features/bookmakers", label: "Bookmakers" },
];

const legalLinks = [
  { href: "/terms", label: "Terms of Service" },
  { href: "/privacy", label: "Privacy Policy" },
];

export default function SiteFooter() {
  return (
    <footer className="border-t border-[var(--border)] bg-white">
      <div className="container py-12">
        <div className="grid gap-8 md:grid-cols-[1.2fr_1fr_1fr_1fr_1fr]">
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
                <Link
                  key={link.href}
                  href={link.href}
                  className="block text-sm text-[var(--ink-muted)] hover:text-[var(--ink)]"
                >
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
          <div>
            <div className="text-sm font-semibold">Legal</div>
            <div className="mt-3 space-y-2">
              {legalLinks.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  className="block text-sm text-[var(--ink-muted)] hover:text-[var(--ink)]"
                >
                  {link.label}
                </Link>
              ))}
            </div>
          </div>
          <div>
            <div className="text-sm font-semibold">Contact Us</div>
            <div className="mt-3 space-y-2">
              <a href="mailto:placeholder@gmail.com" className="block text-sm text-[var(--ink-muted)] hover:text-[var(--ink)]">
                placeholder@gmail.com
              </a>
            </div>
          </div>
        </div>

        <div className="mt-12 space-y-2 text-xs text-[var(--ink-muted)]">
          <p>
            Disclaimer: SureStake provides matched betting and educational content. Gambling can be addictive. Please
            gamble responsibly and only bet what you can afford to lose. If you or someone you know has a gambling
            problem, help is available. Call 1800 858 858 or visit gamblinghelponline.org.au.
          </p>
          <p>&copy; 2026 placeholder. All rights reserved.</p>
        </div>
      </div>
    </footer>
  );
}
