import { Calendar, Clock, User, ArrowRight } from 'lucide-react'
import Link from 'next/link'

export default function BlogPage() {
  const posts = [
    {
      id: 1,
      title: "Complete Beginner's Guide to Matched Betting in 2024",
      excerpt: "Everything you need to know to start matched betting from scratch, including the best bookmakers and exchanges to use.",
      author: "Sarah Mitchell",
      date: "2024-01-15",
      readTime: "8 min read",
      category: "Beginner Guide",
      image: "/blog/beginners-guide.jpg"
    },
    {
      id: 2,
      title: "Top 10 Matched Betting Mistakes and How to Avoid Them",
      excerpt: "Learn from common pitfalls that cost matched bettors money and discover how to protect your profits.",
      author: "James Thompson",
      date: "2024-01-12",
      readTime: "6 min read",
      category: "Tips & Tricks",
      image: "/blog/mistakes.jpg"
    },
    {
      id: 3,
      title: "2024 Bookmaker Bonus Round-Up: Best Offers This Month",
      excerpt: "A comprehensive list of the most profitable sign-up bonuses and ongoing promotions available right now.",
      author: "Emma Davis",
      date: "2024-01-10",
      readTime: "5 min read",
      category: "Bonuses",
      image: "/blog/bonuses.jpg"
    },
    {
      id: 4,
      title: "Advanced Strategy: Multi-Accounting for Maximum Profits",
      excerpt: "How experienced matched bettors scale their earnings through strategic account management.",
      author: "Michael Chen",
      date: "2024-01-08",
      readTime: "10 min read",
      category: "Advanced",
      image: "/blog/advanced.jpg"
    },
    {
      id: 5,
      title: "Tax Implications of Matched Betting: What You Need to Know",
      excerpt: "Understanding the legal and tax considerations of matched betting profits in different countries.",
      author: "Legal Team",
      date: "2024-01-05",
      readTime: "7 min read",
      category: "Legal",
      image: "/blog/tax.jpg"
    },
    {
      id: 6,
      title: "Building Your Matched Betting Bank: Bankroll Management 101",
      excerpt: "Essential strategies for managing your betting bank and reinvesting profits for maximum growth.",
      author: "Sarah Mitchell",
      date: "2024-01-03",
      readTime: "9 min read",
      category: "Strategy",
      image: "/blog/bankroll.jpg"
    }
  ]

  const categories = [
    { name: "All Posts", count: posts.length },
    { name: "Beginner Guide", count: 1 },
    { name: "Tips & Tricks", count: 1 },
    { name: "Bonuses", count: 1 },
    { name: "Advanced", count: 1 },
    { name: "Legal", count: 1 },
    { name: "Strategy", count: 1 }
  ]

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <section className="bg-white py-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center">
            <h1 className="text-4xl md:text-5xl font-bold text-gray-900 mb-6">
              Matched Betting Blog
            </h1>
            <p className="text-xl text-gray-600 max-w-3xl mx-auto">
              Expert insights, strategies, and the latest updates from the world of matched betting.
              Learn from professionals and stay ahead of the game.
            </p>
          </div>
        </div>
      </section>

      {/* Main Content */}
      <section className="py-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col lg:flex-row gap-8">
            {/* Sidebar */}
            <div className="lg:w-1/4">
              <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 sticky top-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Categories</h3>
                <div className="space-y-2">
                  {categories.map((category) => (
                    <div key={category.name} className="flex items-center justify-between">
                      <span className="text-gray-700 hover:text-blue-600 cursor-pointer">
                        {category.name}
                      </span>
                      <span className="text-sm text-gray-500">({category.count})</span>
                    </div>
                  ))}
                </div>

                {/* Newsletter Signup */}
                <div className="mt-8 pt-6 border-t border-gray-200">
                  <h4 className="text-md font-semibold text-gray-900 mb-2">Stay Updated</h4>
                  <p className="text-sm text-gray-600 mb-4">
                    Get the latest matched betting tips and strategies delivered to your inbox.
                  </p>
                  <div className="space-y-2">
                    <input
                      type="email"
                      placeholder="Your email"
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                    <button className="w-full bg-blue-600 text-white py-2 rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors">
                      Subscribe
                    </button>
                  </div>
                </div>
              </div>
            </div>

            {/* Blog Posts */}
            <div className="lg:w-3/4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                {posts.map((post) => (
                  <article key={post.id} className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden hover:shadow-md transition-shadow">
                    <div className="h-48 bg-gray-200 flex items-center justify-center">
                      <span className="text-gray-500">Blog Image</span>
                    </div>

                    <div className="p-6">
                      <div className="flex items-center space-x-2 mb-3">
                        <span className="bg-blue-100 text-blue-800 text-xs font-medium px-2 py-1 rounded">
                          {post.category}
                        </span>
                      </div>

                      <h2 className="text-xl font-semibold text-gray-900 mb-3 hover:text-blue-600 cursor-pointer">
                        {post.title}
                      </h2>

                      <p className="text-gray-600 mb-4 line-clamp-3">
                        {post.excerpt}
                      </p>

                      <div className="flex items-center justify-between text-sm text-gray-500 mb-4">
                        <div className="flex items-center space-x-4">
                          <div className="flex items-center">
                            <User className="w-4 h-4 mr-1" />
                            {post.author}
                          </div>
                          <div className="flex items-center">
                            <Calendar className="w-4 h-4 mr-1" />
                            {new Date(post.date).toLocaleDateString()}
                          </div>
                          <div className="flex items-center">
                            <Clock className="w-4 h-4 mr-1" />
                            {post.readTime}
                          </div>
                        </div>
                      </div>

                      <Link
                        href={`/blog/${post.id}`}
                        className="inline-flex items-center text-blue-600 hover:text-blue-700 font-medium"
                      >
                        Read More
                        <ArrowRight className="w-4 h-4 ml-1" />
                      </Link>
                    </div>
                  </article>
                ))}
              </div>

              {/* Load More */}
              <div className="text-center mt-12">
                <button className="bg-gray-200 text-gray-700 px-6 py-3 rounded-lg hover:bg-gray-300 transition-colors">
                  Load More Posts
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-16 bg-blue-600">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-3xl font-bold text-white mb-4">
            Ready to Start Your Matched Betting Journey?
          </h2>
          <p className="text-xl text-blue-100 mb-8">
            Join thousands of successful matched bettors and start earning today
          </p>
          <Link
            href="/sign-up"
            className="bg-white text-blue-600 px-8 py-4 rounded-lg font-semibold hover:bg-gray-100 transition-colors"
          >
            Get Started Free
          </Link>
        </div>
      </section>
    </div>
  )
}