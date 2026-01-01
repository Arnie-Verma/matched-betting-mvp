import Link from "next/link";
import type { CSSProperties } from "react";
import { ArrowUpRight, Calendar, Clock, User } from "lucide-react";

const posts = [
  {
    id: 1,
    title: "Matched betting for beginners: your first week",
    excerpt: "A day-by-day playbook for getting your first offers completed without stress.",
    author: "MatchedBetting Team",
    date: "2026-01-01",
    readTime: "7 min read",
  },
  {
    id: 2,
    title: "How to evaluate bookmaker promos safely",
    excerpt: "A checklist for spotting real value and avoiding confusing promo terms.",
    author: "Sarah Mitchell",
    date: "2025-12-20",
    readTime: "6 min read",
  },
  {
    id: 3,
    title: "Bankroll systems that keep profit steady",
    excerpt: "Reduce variance and protect cash flow using measured staking and guardrails.",
    author: "James Thompson",
    date: "2025-12-10",
    readTime: "5 min read",
  },
  {
    id: 4,
    title: "Matched betting vs bonus hunting",
    excerpt: "When to use each approach and how to combine them for better returns.",
    author: "Emma Davis",
    date: "2025-11-30",
    readTime: "8 min read",
  },
];

export default function BlogPage() {
  return (
    <main>
      <section className="section-padding hero-bg">
        <div className="mx-auto max-w-6xl px-6">
          <p className="badge">Blog</p>
          <h1 className="mt-4 text-4xl md:text-5xl">Strategy notes and matched betting guides.</h1>
          <p className="mt-4 text-[var(--ink-muted)] max-w-2xl">
            Learn how to execute matched betting confidently with walkthroughs, checklists, and strategy tips.
          </p>
        </div>
      </section>

      <section className="section-padding">
        <div className="mx-auto max-w-6xl px-6">
          <div className="grid gap-6 md:grid-cols-2">
            {posts.map((post, index) => (
              <article
                key={post.id}
                className="surface p-6 reveal"
                style={{ "--delay": `${0.1 * index}s` } as CSSProperties}
              >
                <div className="flex flex-wrap items-center gap-3 text-xs text-[var(--ink-muted)]">
                  <span className="flex items-center gap-1">
                    <Calendar className="h-3.5 w-3.5" />
                    {post.date}
                  </span>
                  <span className="flex items-center gap-1">
                    <Clock className="h-3.5 w-3.5" />
                    {post.readTime}
                  </span>
                </div>
                <h2 className="mt-4 text-xl font-semibold">{post.title}</h2>
                <p className="mt-3 text-sm text-[var(--ink-muted)]">{post.excerpt}</p>
                <div className="mt-4 flex items-center justify-between text-sm text-[var(--ink-muted)]">
                  <span className="flex items-center gap-2">
                    <User className="h-4 w-4" />
                    {post.author}
                  </span>
                  <Link href="/blog" className="inline-flex items-center gap-2 text-[var(--ink)]">
                    Read more
                    <ArrowUpRight className="h-4 w-4" />
                  </Link>
                </div>
              </article>
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}
