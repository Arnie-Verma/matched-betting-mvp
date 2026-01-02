import { auth } from '@clerk/nextjs/server'
import { redirect } from 'next/navigation'
import { BookOpen, Play, Award, Shield, TrendingUp, Users } from 'lucide-react'
import Link from 'next/link'

export default async function AcademyPage() {
  const { userId } = await auth()

  if (!userId) {
    redirect('/sign-in?redirect_url=/academy')
  }

  const modules = [
    {
      id: 1,
      title: "Getting Started",
      description: "Complete introduction to matched betting fundamentals",
      lessons: 8,
      duration: "45 min",
      level: "Beginner",
      icon: <BookOpen className="w-6 h-6" />,
      completed: false,
      href: "/academy/getting-started"
    },
    {
      id: 2,
      title: "How Matched Betting Works",
      description: "Deep dive into the mathematics behind guaranteed profits",
      lessons: 6,
      duration: "30 min",
      level: "Beginner",
      icon: <Play className="w-6 h-6" />,
      completed: false,
      href: "/academy/how-it-works"
    },
    {
      id: 3,
      title: "Your First £70 Tutorial",
      description: "Step-by-step guide to earning your first profits",
      lessons: 12,
      duration: "90 min",
      level: "Beginner",
      icon: <Award className="w-6 h-6" />,
      completed: false,
      href: "/academy/first-70"
    },
    {
      id: 4,
      title: "Advanced Strategies",
      description: "Scaling techniques and advanced profit opportunities",
      lessons: 15,
      duration: "120 min",
      level: "Advanced",
      icon: <TrendingUp className="w-6 h-6" />,
      completed: false,
      href: "/academy/advanced-strategies"
    },
    {
      id: 5,
      title: "Risk Management",
      description: "Protecting your accounts and managing bankroll",
      lessons: 10,
      duration: "60 min",
      level: "Intermediate",
      icon: <Shield className="w-6 h-6" />,
      completed: false,
      href: "/academy/risk-management"
    },
    {
      id: 6,
      title: "Account Sustainability",
      description: "Long-term strategies for maintaining profitable accounts",
      lessons: 8,
      duration: "45 min",
      level: "Advanced",
      icon: <Users className="w-6 h-6" />,
      completed: false,
      href: "/academy/sustainability"
    }
  ]

  const getLevelColor = (level: string) => {
    switch (level) {
      case 'Beginner': return 'bg-green-100 text-green-800'
      case 'Intermediate': return 'bg-yellow-100 text-yellow-800'
      case 'Advanced': return 'bg-red-100 text-red-800'
      default: return 'bg-gray-100 text-gray-800'
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        {/* Header */}
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold text-gray-900 mb-4">
            Matched Betting Academy
          </h1>
          <p className="text-xl text-gray-600 max-w-3xl mx-auto">
            Master the art of matched betting with our comprehensive course library.
            From complete beginner to advanced strategies - we&apos;ve got you covered.
          </p>
        </div>

        {/* Progress Overview */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-8">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold text-gray-900">Your Progress</h2>
            <span className="text-sm text-gray-500">0 of {modules.length} modules completed</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div className="bg-blue-600 h-2 rounded-full" style={{ width: '0%' }}></div>
          </div>
          <p className="text-sm text-gray-600 mt-2">
            Complete your first module to start earning!
          </p>
        </div>

        {/* Featured Module */}
        <div className="bg-gradient-to-br from-blue-600 to-blue-700 rounded-xl text-white p-8 mb-8">
          <div className="flex items-center mb-4">
            <Award className="w-8 h-8 mr-3" />
            <span className="bg-blue-500 text-white px-3 py-1 rounded-full text-sm font-medium">
              Recommended Start
            </span>
          </div>
          <h3 className="text-2xl font-bold mb-2">Getting Started</h3>
          <p className="text-blue-100 mb-6">
            Perfect for complete beginners. Learn the fundamentals and complete your first matched bet
            with our step-by-step guidance.
          </p>
          <Link
            href="/academy/getting-started"
            className="bg-white text-blue-600 px-6 py-3 rounded-lg font-semibold hover:bg-gray-100 transition-colors inline-block"
          >
            Start Learning
          </Link>
        </div>

        {/* All Modules */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {modules.map((module) => (
            <div key={module.id} className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden hover:shadow-md transition-shadow">
              <div className="p-6">
                <div className="flex items-center justify-between mb-4">
                  <div className="bg-blue-100 p-2 rounded-lg">
                    {module.icon}
                  </div>
                  <span className={`px-2 py-1 rounded-full text-xs font-medium ${getLevelColor(module.level)}`}>
                    {module.level}
                  </span>
                </div>

                <h3 className="text-lg font-semibold text-gray-900 mb-2">{module.title}</h3>
                <p className="text-gray-600 text-sm mb-4">{module.description}</p>

                <div className="flex items-center justify-between text-sm text-gray-500 mb-4">
                  <span>{module.lessons} lessons</span>
                  <span>{module.duration}</span>
                </div>

                {module.completed ? (
                  <div className="flex items-center text-green-600 text-sm font-medium">
                    <Award className="w-4 h-4 mr-1" />
                    Completed
                  </div>
                ) : (
                  <Link
                    href={module.href}
                    className="block w-full text-center bg-blue-600 text-white py-2 rounded-lg hover:bg-blue-700 transition-colors"
                  >
                    Start Module
                  </Link>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* Help Section */}
        <div className="mt-12 bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Need Help?</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="text-center">
              <BookOpen className="w-8 h-8 text-blue-600 mx-auto mb-2" />
              <h3 className="font-medium text-gray-900 mb-1">Video Tutorials</h3>
              <p className="text-sm text-gray-600">Watch step-by-step video guides for every concept</p>
            </div>
            <div className="text-center">
              <Users className="w-8 h-8 text-blue-600 mx-auto mb-2" />
              <h3 className="font-medium text-gray-900 mb-1">Community Support</h3>
              <p className="text-sm text-gray-600">Get help from experienced matched bettors</p>
            </div>
            <div className="text-center">
              <Shield className="w-8 h-8 text-blue-600 mx-auto mb-2" />
              <h3 className="font-medium text-gray-900 mb-1">Expert Guidance</h3>
              <p className="text-sm text-gray-600">Access to professional matched betting advisors</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
