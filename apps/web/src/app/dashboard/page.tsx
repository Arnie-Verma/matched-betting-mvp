'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { MessageCircle, Calculator, GraduationCap, DollarSign, X, ChevronRight, TrendingUp, Zap } from 'lucide-react'

export default function DashboardPage() {
  const [showTutorialPopup, setShowTutorialPopup] = useState(false)

  // Show tutorial popup after 2 minutes (120000ms)
  useEffect(() => {
    const timer = setTimeout(() => {
      // Check if user has dismissed it before
      const dismissed = localStorage.getItem('tutorialPopupDismissed')
      if (!dismissed) {
        setShowTutorialPopup(true)
      }
    }, 120000) // 2 minutes

    return () => clearTimeout(timer)
  }, [])

  const dismissPopup = () => {
    setShowTutorialPopup(false)
    localStorage.setItem('tutorialPopupDismissed', 'true')
  }

  return (
    <main className="max-w-5xl mx-auto py-8 px-4 space-y-6">
      <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>

      {/* Main Feature Cards */}
      <div className="space-y-4">
        {/* Discord Community */}
        <div className="flex bg-white rounded-xl shadow-sm overflow-hidden border">
          <div className="w-64 bg-indigo-500 flex items-center justify-center p-8">
            <MessageCircle className="w-20 h-20 text-white" strokeWidth={1.5} />
          </div>
          <div className="flex-1 p-6">
            <h2 className="text-xl font-bold text-gray-900 mb-2">Join our Discord Community</h2>
            <p className="text-gray-600 mb-4">
              Learn from other matched bettors and discuss everything matched betting related on our Discord.
              If you need help from Outmatched, you can contact us here too!
            </p>
            <a
              href="https://discord.gg/your-invite"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-block bg-red-500 hover:bg-red-600 text-white font-medium px-5 py-2 rounded-lg transition-colors"
            >
              Join the Discord
            </a>
          </div>
        </div>

        {/* Odds Matcher */}
        <div className="flex bg-white rounded-xl shadow-sm overflow-hidden border">
          <div className="w-64 bg-gradient-to-br from-orange-400 to-red-400 flex items-center justify-center p-8">
            <Calculator className="w-20 h-20 text-white" strokeWidth={1.5} />
          </div>
          <div className="flex-1 p-6">
            <h2 className="text-xl font-bold text-gray-900 mb-2">Odds Matcher</h2>
            <p className="text-gray-600 mb-4">
              Use the most up to date bookmaker to find the best odds and convert bonus bets or place mug bets.
            </p>
            <Link
              href="/dashboard/odds-matcher"
              className="inline-block bg-red-500 hover:bg-red-600 text-white font-medium px-5 py-2 rounded-lg transition-colors"
            >
              Open odds matcher
            </Link>
          </div>
        </div>

        {/* Learn the fundamentals */}
        <div className="flex bg-white rounded-xl shadow-sm overflow-hidden border">
          <div className="w-64 bg-blue-500 flex items-center justify-center p-8">
            <GraduationCap className="w-20 h-20 text-white" strokeWidth={1.5} />
          </div>
          <div className="flex-1 p-6">
            <h2 className="text-xl font-bold text-gray-900 mb-2">Learn the fundamentals</h2>
            <p className="text-gray-600 mb-4">
              Learn everything you need to know to start gaining the edge on bookies and making consistent profits.
            </p>
            <Link
              href="/academy"
              className="inline-block bg-red-500 hover:bg-red-600 text-white font-medium px-5 py-2 rounded-lg transition-colors"
            >
              Visit the academy
            </Link>
          </div>
        </div>

        {/* Invite Friends */}
        <div className="flex bg-white rounded-xl shadow-sm overflow-hidden border">
          <div className="w-64 bg-gradient-to-br from-purple-400 to-pink-400 flex items-center justify-center p-8">
            <DollarSign className="w-20 h-20 text-white" strokeWidth={1.5} />
          </div>
          <div className="flex-1 p-6">
            <h2 className="text-xl font-bold text-gray-900 mb-2">Invite Friends</h2>
            <p className="text-gray-600 mb-4">
              Earn a referral for everyone that joins you on your matched betting journey.
            </p>
            <span className="inline-block bg-gray-200 text-gray-600 font-medium px-5 py-2 rounded-lg cursor-not-allowed">
              Coming soon
            </span>
          </div>
        </div>
      </div>

      {/* Coming Soon Section */}
      <div className="bg-white rounded-xl border shadow-sm p-6">
        <h2 className="text-xl font-semibold mb-4">Coming Soon</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="text-center p-4 bg-gray-50 rounded-lg">
            <div className="text-2xl mb-2">
              <TrendingUp className="w-8 h-8 mx-auto text-blue-500" />
            </div>
            <div className="font-medium">Dutching Software</div>
            <div className="text-sm text-gray-600">Find profitable dutching opportunities</div>
          </div>
          <div className="text-center p-4 bg-gray-50 rounded-lg">
            <div className="text-2xl mb-2">
              <DollarSign className="w-8 h-8 mx-auto text-green-500" />
            </div>
            <div className="font-medium">Referral Program</div>
            <div className="text-sm text-gray-600">Earn rewards for inviting friends</div>
          </div>
          <div className="text-center p-4 bg-gray-50 rounded-lg">
            <div className="text-2xl mb-2">
              <Zap className="w-8 h-8 mx-auto text-yellow-500" />
            </div>
            <div className="font-medium">Live Horse Racing Odds</div>
            <div className="text-sm text-gray-600">Real-time racing odds from all bookmakers</div>
          </div>
        </div>
      </div>

      {/* Tutorial Popup */}
      {showTutorialPopup && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-gradient-to-r from-indigo-900 to-purple-900 rounded-2xl max-w-lg w-full p-6 relative">
            <button
              onClick={dismissPopup}
              className="absolute top-4 right-4 text-white/70 hover:text-white"
            >
              <X className="w-6 h-6" />
            </button>

            <h3 className="text-xl font-bold text-white mb-2">Not sure where to start?</h3>
            <p className="text-white/90 mb-6">
              Our 10 minute tutorial will teach you everything you need to know about matched betting
              to get started and you&apos;ll make your first $70 in the process.
            </p>

            <Link
              href="/academy/getting-started"
              onClick={dismissPopup}
              className="inline-flex items-center bg-white text-indigo-900 font-semibold px-6 py-3 rounded-lg hover:bg-gray-100 transition-colors"
            >
              View the tutorial
              <ChevronRight className="w-5 h-5 ml-1" />
            </Link>
          </div>
        </div>
      )}
    </main>
  )
}
