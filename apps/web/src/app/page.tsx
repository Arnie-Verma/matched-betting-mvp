import { Check, ArrowRight, TrendingUp, Shield, Calculator, Star } from 'lucide-react'
import Link from 'next/link'

export default function Home() {
  const features = [
    {
      icon: <Calculator className="w-6 h-6 text-blue-600" />,
      title: "Professional Calculators",
      description: "Back/lay, dutching, and EV calculators for maximum accuracy"
    },
    {
      icon: <TrendingUp className="w-6 h-6 text-blue-600" />,
      title: "Odds Matching",
      description: "Real-time odds comparison to find the best matched betting opportunities"
    },
    {
      icon: <Shield className="w-6 h-6 text-blue-600" />,
      title: "Risk-Free Profits",
      description: "Mathematical guarantees - no gambling, no risk, just profit"
    }
  ]

  const testimonials = [
    {
      name: "Sarah M.",
      location: "Melbourne",
      earnings: "£2,847",
      quote: "Started with £50 and made over £2,800 in my first 3 months. The academy made it so easy!"
    },
    {
      name: "James T.",
      location: "Sydney",
      earnings: "£5,234",
      quote: "The calculators are incredibly accurate. I've never lost money with this system."
    },
    {
      name: "Emma D.",
      location: "Brisbane",
      earnings: "£1,923",
      quote: "Perfect side income. I spend 2 hours per week and earn consistent profits."
    }
  ]

  const plans = [
    {
      name: "Free",
      price: "£0",
      period: "forever",
      bookmakers: "2",
      features: [
        "Basic calculators",
        "Getting started academy",
        "Email support"
      ]
    },
    {
      name: "Premium",
      price: "£25",
      period: "per month",
      bookmakers: "10",
      popular: true,
      features: [
        "All calculators",
        "Full academy access",
        "Odds matcher",
        "Mobile app",
        "Priority support"
      ]
    },
    {
      name: "Platinum",
      price: "£35",
      period: "per month",
      bookmakers: "100+",
      features: [
        "Everything in Premium",
        "Advanced tools",
        "API access",
        "Custom alerts",
        "1-on-1 coaching calls"
      ]
    }
  ]

  return (
    <div className="min-h-screen bg-white">
      {/* Hero Section */}
      <section className="pt-20 pb-16 bg-gradient-to-br from-blue-50 to-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center">
            <h1 className="text-4xl md:text-6xl font-bold text-gray-900 mb-6">
              Turn Bookmaker Bonuses Into
              <span className="text-blue-600"> Guaranteed Profits</span>
            </h1>
            <p className="text-xl text-gray-600 max-w-3xl mx-auto mb-8">
              Master matched betting with professional tools, step-by-step academy, and real-time odds matching.
              Join thousands earning £500+ per month risk-free.
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center mb-12">
              <Link
                href="/sign-up"
                className="bg-blue-600 text-white px-8 py-4 rounded-lg font-semibold hover:bg-blue-700 transition-colors flex items-center justify-center"
              >
                Start Free Account
                <ArrowRight className="w-5 h-5 ml-2" />
              </Link>
              <Link
                href="/how-it-works"
                className="border-2 border-blue-600 text-blue-600 px-8 py-4 rounded-lg font-semibold hover:bg-blue-50 transition-colors"
              >
                How It Works
              </Link>
            </div>

            {/* Social Proof */}
            <div className="flex items-center justify-center space-x-6 text-sm text-gray-600">
              <div className="flex items-center">
                <div className="flex -space-x-2 mr-2">
                  {[1,2,3,4,5].map(i => (
                    <div key={i} className="w-8 h-8 bg-gray-300 rounded-full border-2 border-white"></div>
                  ))}
                </div>
                <span>10,000+ members</span>
              </div>
              <div className="flex items-center">
                <div className="flex text-yellow-400 mr-1">
                  {[1,2,3,4,5].map(i => (
                    <Star key={i} className="w-4 h-4 fill-current" />
                  ))}
                </div>
                <span>4.9/5 rating</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="py-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold text-gray-900 mb-4">Everything You Need to Succeed</h2>
            <p className="text-lg text-gray-600">Professional-grade tools used by thousands of successful matched bettors</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {features.map((feature, index) => (
              <div key={index} className="text-center p-6 bg-gray-50 rounded-xl">
                <div className="bg-blue-100 w-12 h-12 rounded-lg flex items-center justify-center mx-auto mb-4">
                  {feature.icon}
                </div>
                <h3 className="text-xl font-semibold text-gray-900 mb-2">{feature.title}</h3>
                <p className="text-gray-600">{feature.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Testimonials */}
      <section className="py-16 bg-gray-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold text-gray-900 mb-4">Real Members, Real Results</h2>
            <p className="text-lg text-gray-600">See what our community has achieved</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {testimonials.map((testimonial, index) => (
              <div key={index} className="bg-white p-6 rounded-xl shadow-sm border border-gray-200">
                <div className="flex items-center mb-4">
                  <div className="bg-green-100 text-green-800 px-3 py-1 rounded-full text-sm font-semibold">
                    +{testimonial.earnings}
                  </div>
                </div>
                <p className="text-gray-700 mb-4">"{testimonial.quote}"</p>
                <div className="flex items-center">
                  <div className="w-10 h-10 bg-gray-300 rounded-full mr-3"></div>
                  <div>
                    <div className="font-medium text-gray-900">{testimonial.name}</div>
                    <div className="text-sm text-gray-500">{testimonial.location}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section className="py-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold text-gray-900 mb-4">Start Free, Scale When Ready</h2>
            <p className="text-lg text-gray-600">Choose the plan that fits your matched betting journey</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 max-w-5xl mx-auto">
            {plans.map((plan, index) => (
              <div key={index} className={`bg-white rounded-xl shadow-sm border-2 p-8 relative ${plan.popular ? 'border-blue-500' : 'border-gray-200'}`}>
                {plan.popular && (
                  <div className="absolute top-0 left-1/2 transform -translate-x-1/2 -translate-y-1/2">
                    <span className="bg-blue-500 text-white px-4 py-1 rounded-full text-sm font-medium">
                      Most Popular
                    </span>
                  </div>
                )}

                <div className="text-center mb-8">
                  <h3 className="text-xl font-semibold text-gray-900 mb-2">{plan.name}</h3>
                  <div className="mb-4">
                    <span className="text-4xl font-bold text-gray-900">{plan.price}</span>
                    <span className="text-gray-600">/{plan.period}</span>
                  </div>
                  <p className="text-gray-600">Up to {plan.bookmakers} bookmakers</p>
                </div>

                <ul className="space-y-3 mb-8">
                  {plan.features.map((feature, featureIndex) => (
                    <li key={featureIndex} className="flex items-center">
                      <Check className="w-5 h-5 text-green-500 mr-3 flex-shrink-0" />
                      <span className="text-gray-700">{feature}</span>
                    </li>
                  ))}
                </ul>

                <Link
                  href={plan.name === "Free" ? "/sign-up" : "/billing"}
                  className={`w-full py-3 px-4 rounded-lg font-medium transition-colors block text-center ${
                    plan.popular
                      ? 'bg-blue-600 text-white hover:bg-blue-700'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }`}
                >
                  {plan.name === "Free" ? "Start Free" : "Get Started"}
                </Link>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-16 bg-blue-600">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-3xl font-bold text-white mb-4">
            Ready to Start Earning Risk-Free Profits?
          </h2>
          <p className="text-xl text-blue-100 mb-8">
            Join our community of successful matched bettors today
          </p>
          <Link
            href="/sign-up"
            className="bg-white text-blue-600 px-8 py-4 rounded-lg font-semibold hover:bg-gray-100 transition-colors inline-flex items-center"
          >
            Create Free Account
            <ArrowRight className="w-5 h-5 ml-2" />
          </Link>
        </div>
      </section>
    </div>
  )
}
