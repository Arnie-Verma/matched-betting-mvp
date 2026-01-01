import Link from "next/link";
import { ArrowUpRight, Menu } from "lucide-react";
import { appUrl } from "@/lib/site";

const navLinks = [
  { href: "/", label: "Home" },
  { href: "/features", label: "Features" },
  { href: "/pricing", label: "Pricing" },
  { href: "/blog", label: "Blog" },
];

export default function SiteHeader() {
  return (
    <header className="sticky top-0 z-50 border-b border-black/5 bg-[rgba(247,243,234,0.92)] backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
        <Link href="/" className="flex items-center gap-3">
          <span className="h-10 w-10 rounded-2xl bg-[var(--ink)] text-white flex items-center justify-center text-lg font-semibold">
            MB
          </span>
          <div className="leading-tight">
            <div className="text-lg font-semibold">MatchedBetting</div>
            <div className="text-xs text-[var(--ink-muted)]">Australian matched betting platform</div>
          </div>
        </Link>

        <nav className="hidden items-center gap-6 md:flex">
          {navLinks.map((link) => (
            <Link key={link.href} href={link.href} className="nav-link">
              {link.label}
            </Link>
          ))}
        </nav>

        <div className="hidden items-center gap-3 md:flex">
          <Link href={`${appUrl}/sign-in`} className="btn-ghost">
            Log in
          </Link>
          <Link href={`${appUrl}/sign-up`} className="btn-primary">
            Start free
            <ArrowUpRight className="h-4 w-4" />
          </Link>
        </div>

        <details className="relative md:hidden">
          <summary className="flex items-center gap-2 rounded-full border border-black/10 px-3 py-2 text-sm font-medium">
            <Menu className="h-4 w-4" />
            Menu
          </summary>
          <div className="absolute right-0 mt-3 w-56 space-y-2 rounded-2xl border border-black/10 bg-white p-4 shadow-lg">
            {navLinks.map((link) => (
              <Link key={link.href} href={link.href} className="block text-sm font-medium text-[var(--ink-muted)]">
                {link.label}
              </Link>
            ))}
            <div className="pt-2 border-t border-black/10 space-y-2">
              <Link href={`${appUrl}/sign-in`} className="block text-sm font-medium text-[var(--ink)]">
                Log in
              </Link>
              <Link href={`${appUrl}/sign-up`} className="btn-primary w-full justify-center">
                Start free
                <ArrowUpRight className="h-4 w-4" />
              </Link>
            </div>
          </div>
        </details>
      </div>
    </header>
  );
}
