import { Check, ArrowRight, BookOpen, Calculator, TrendingUp } from 'lucide-react'
import Link from 'next/link'

export default function HowItWorksPage() {
  const steps = [
    {
      number: 1,
      title: "Sign Up & Get Started",
      description: "Create your free account and access our comprehensive matched betting academy.",
      icon: <BookOpen className="w-8 h-8 text-blue-600" />,
    },
    {
      number: 2,
      title: "Learn the Basics",
      description: "Follow our step-by-step tutorials to understand matched betting fundamentals.",
      icon: <Calculator className="w-8 h-8 text-blue-600" />,
    },
    {
      number: 3,
      title: "Use Our Tools",
      description: "Access professional calculators and odds matching tools to find profitable opportunities.",
      icon: <TrendingUp className="w-8 h-8 text-blue-600" />,
    },
  ]

  const benefits = [
    "100% risk-free profits",
    "No gambling - mathematical certainty",
    "Works with any bookmaker",
    "Scalable income source",
    "Community support",
    "Professional tools included"
  ]

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Hero Section */}
      <section className="bg-white py-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center">
            <h1 className="text-4xl md:text-6xl font-bold text-gray-900 mb-6">
              How Matched Betting
              <span className="text-blue-600"> Actually Works</span>
            </h1>
            <p className="text-xl text-gray-600 max-w-3xl mx-auto mb-8">
              Matched betting isn't gambling - it's a mathematical technique that guarantees profit
              by covering all possible outcomes of a sporting event using free bets and bonuses.
            </p>
          </div>
        </div>
      </section>

      {/* The Process */}
      <section className="py-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold text-gray-900 mb-4">The Simple 3-Step Process</h2>
            <p className="text-lg text-gray-600">
              Get started with matched betting in minutes, not hours
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {steps.map((step, index) => (
              <div key={step.number} className="bg-white rounded-xl p-8 shadow-sm border border-gray-200">
                <div className="flex items-center mb-6">
                  <div className="bg-blue-100 p-3 rounded-lg mr-4">
                    {step.icon}
                  </div>
                  <div className="bg-blue-600 text-white rounded-full w-8 h-8 flex items-center justify-center text-sm font-bold">
                    {step.number}
                  </div>
                </div>
                <h3 className="text-xl font-semibold text-gray-900 mb-3">{step.title}</h3>
                <p className="text-gray-600">{step.description}</p>
                {index < steps.length - 1 && (
                  <div className="hidden md:block absolute right-0 top-1/2 transform translate-x-4 -translate-y-1/2">
                    <ArrowRight className="w-6 h-6 text-gray-400" />
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Example Calculation */}
      <section className="py-16 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold text-gray-900 mb-4">Real Example: £10 Free Bet</h2>
            <p className="text-lg text-gray-600">
              See how you can turn a £10 free bet into guaranteed profit
            </p>
          </div>

          <div className="bg-gray-50 rounded-xl p-8 max-w-4xl mx-auto">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
              <div>
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Step 1: Back Bet (Bookmaker)</h3>
                <div className="space-y-2">
                  <div className="flex justify-between">
                    <span>Bet:</span>
                    <span className="font-semibold">Chelsea to win @ 3.0</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Stake:</span>
                    <span className="font-semibold">£10 (free bet)</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Potential Win:</span>
                    <span className="font-semibold">£30</span>
                  </div>
                </div>
              </div>

              <div>
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Step 2: Lay Bet (Exchange)</h3>
                <div className="space-y-2">
                  <div className="flex justify-between">
                    <span>Bet:</span>
                    <span className="font-semibold">Chelsea NOT to win @ 3.0</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Liability:</span>
                    <span className="font-semibold">£20</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Potential Win:</span>
                    <span className="font-semibold">£10</span>
                  </div>
                </div>
              </div>
            </div>

            <div className="mt-8 p-4 bg-green-100 rounded-lg">
              <h4 className="font-semibold text-green-800 mb-2">Guaranteed Outcome:</h4>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                <div>
                  <strong>If Chelsea wins:</strong> Win £30 at bookmaker, lose £20 at exchange = <span className="text-green-600 font-bold">£10 profit</span>
                </div>
                <div>
                  <strong>If Chelsea doesn't win:</strong> Lose £0 at bookmaker (free bet), win £10 at exchange = <span className="text-green-600 font-bold">£10 profit</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Benefits */}
      <section className="py-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold text-gray-900 mb-4">Why Matched Betting Works</h2>
            <p className="text-lg text-gray-600">
              The key advantages that make this a reliable income source
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {benefits.map((benefit, index) => (
              <div key={index} className="flex items-center space-x-3 bg-white p-4 rounded-lg shadow-sm border border-gray-200">
                <Check className="w-5 h-5 text-green-500 flex-shrink-0" />
                <span className="text-gray-800">{benefit}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-16 bg-blue-600">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-3xl font-bold text-white mb-4">
            Ready to Start Making Risk-Free Profits?
          </h2>
          <p className="text-xl text-blue-100 mb-8 max-w-2xl mx-auto">
            Join thousands of successful matched bettors and start your journey today
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link
              href="/sign-up"
              className="bg-white text-blue-600 px-8 py-4 rounded-lg font-semibold hover:bg-gray-100 transition-colors"
            >
              Start Free Account
            </Link>
            <Link
              href="/billing"
              className="border-2 border-white text-white px-8 py-4 rounded-lg font-semibold hover:bg-white hover:text-blue-600 transition-colors"
            >
              View Pricing
            </Link>
          </div>
        </div>
      </section>
    </div>
  )
}