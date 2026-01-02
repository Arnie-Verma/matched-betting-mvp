'use client'

import { useState, useRef, useEffect } from 'react'
import Link from 'next/link'
import { useUser, UserButton } from '@clerk/nextjs'
import {
  Home,
  GraduationCap,
  Calculator,
  Wrench,
  ChevronDown,
  Menu,
  X,
  Lock,
  CreditCard,
  Star
} from 'lucide-react'
import { useSubscription } from '@/hooks/useSubscription'
import { clientApi } from '@/lib/clientApi'
import { useRouter } from 'next/navigation'

export default function PostLoginHeader() {
  const [isMenuOpen, setIsMenuOpen] = useState(false)
  const [activeDropdown, setActiveDropdown] = useState<string | null>(null)
  const { isSignedIn } = useUser()
  const { isPremium, plan } = useSubscription()
  const dropdownRef = useRef<HTMLDivElement>(null)
  const router = useRouter()
  const manageLabel = plan === 'free' ? 'Upgrade now' : 'Manage Subscription'
  const manageIcon = plan === 'free'
    ? <Star className="w-4 h-4 upgrade-cta-icon" fill="currentColor" />
    : <CreditCard className="w-4 h-4" />
  const userButtonElements = {
    avatarBox: "w-8 h-8",
    ...(plan === 'free'
      ? {
          userButtonPopoverCustomItemButton: 'upgrade-cta',
          userButtonPopoverCustomItemButtonIconBox: 'upgrade-cta-icon',
          userButtonPopoverActionItemButtonIcon: 'upgrade-cta-icon',
        }
      : {})
  }

  useEffect(() => {
    if (plan === 'free') {
      document.body.classList.add('free-plan')
    } else {
      document.body.classList.remove('free-plan')
    }
    return () => document.body.classList.remove('free-plan')
  }, [plan])

  const goToPortal = async () => {
    // If user is on free plan, send them to the billing page to upgrade
    if (plan === 'free') {
      router.push('/billing')
      return
    }

    try {
      const res = await clientApi.post('/billing/create-portal-session', {
        return_url: window.location.origin + '/dashboard'
      }) as { portal_url: string }

      if (res.portal_url) {
        window.location.href = res.portal_url
      }
    } catch (err) {
      console.error('Failed to open billing portal', err)
      alert('Could not open billing portal. Please try again.')
    }
  }

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setActiveDropdown(null)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [])

  // Don't show post-login header if user is not signed in
  if (!isSignedIn) return null

  const toggleDropdown = (dropdownName: string) => {
    setActiveDropdown(activeDropdown === dropdownName ? null : dropdownName)
  }

  const calculators = [
    { name: 'Back/Lay', href: '/calculators/back-lay', description: 'Calculate lay stakes for back bets', isPremium: false },
    { name: 'Dutching', href: '/calculators/dutching', description: 'Split stakes across multiple outcomes', isPremium: false },
    { name: 'Multi', href: '/calculators/multi', description: 'Calculate multi-bet EV', isPremium: true },
    { name: 'True Odds', href: '/calculators/true-odds', description: 'Remove bookmaker margin', isPremium: false },
    { name: 'Long Term EV', href: '/calculators/ev', description: 'Simulate EV over many bets', isPremium: true },
  ]

  const tools = [
    { name: 'Odds Matcher', href: '/dashboard/odds-matcher', description: 'Find matched betting opportunities' },
    { name: 'Dutching Opportunities', href: '/tools/dutching', description: 'Discover profitable dutching bets' },
  ]

  return (
    <header className="bg-background/90 border-b border-border sticky top-0 z-50 backdrop-blur">
      <nav className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          {/* Logo */}
          <div className="flex-shrink-0">
            <Link href="/dashboard" className="flex items-center">
              <span className="text-2xl font-bold text-[var(--brand)]">MatchedBetting</span>
            </Link>
          </div>

          {/* Desktop Navigation */}
          <div className="hidden md:block" ref={dropdownRef}>
            <div className="ml-10 flex items-center space-x-8">
              <Link
                href="/dashboard"
                className="text-foreground hover:text-primary px-3 py-2 text-sm font-medium transition-colors flex items-center"
              >
                <Home className="w-4 h-4 mr-2" />
                Dashboard
              </Link>

              <Link
                href="/academy"
                className="text-foreground hover:text-primary px-3 py-2 text-sm font-medium transition-colors flex items-center"
              >
                <GraduationCap className="w-4 h-4 mr-2" />
                Academy
              </Link>

              {/* Calculators Dropdown */}
              <div className="relative">
                <button
                  onClick={() => toggleDropdown('calculators')}
                  className="text-foreground hover:text-primary px-3 py-2 text-sm font-medium transition-colors flex items-center"
                >
                  <Calculator className="w-4 h-4 mr-2" />
                  Calculators
                  <ChevronDown className="w-4 h-4 ml-1" />
                </button>

                {activeDropdown === 'calculators' && (
                  <div className="absolute top-full left-0 mt-1 w-64 bg-card rounded-xl shadow-lg border border-border py-2 z-50">
                    {calculators.map((calc) => {
                      const isLocked = calc.isPremium && !isPremium
                      return (
                        <Link
                          key={calc.href}
                          href={calc.href}
                          className={`block px-4 py-3 text-sm hover:bg-muted ${
                            isLocked ? 'text-muted-foreground/60' : 'text-foreground hover:text-primary'
                          }`}
                          onClick={() => setActiveDropdown(null)}
                        >
                          <div className="flex items-center justify-between">
                            <span className="font-medium">{calc.name}</span>
                            {isLocked && <Lock className="w-3.5 h-3.5 text-muted-foreground/60" />}
                          </div>
                        </Link>
                      )
                    })}
                  </div>
                )}
              </div>

              {/* Tools Dropdown */}
              <div className="relative">
                <button
                  onClick={() => toggleDropdown('tools')}
                  className="text-foreground hover:text-primary px-3 py-2 text-sm font-medium transition-colors flex items-center"
                >
                  <Wrench className="w-4 h-4 mr-2" />
                  Tools
                  <ChevronDown className="w-4 h-4 ml-1" />
                </button>

                {activeDropdown === 'tools' && (
                  <div className="absolute top-full left-0 mt-1 w-64 bg-card rounded-xl shadow-lg border border-border py-2 z-50">
                    {tools.map((tool) => (
                      <Link
                        key={tool.href}
                        href={tool.href}
                        className="block px-4 py-3 text-sm text-foreground hover:bg-muted hover:text-primary"
                        onClick={() => setActiveDropdown(null)}
                      >
                        <div className="font-medium">{tool.name}</div>
                        <div className="text-xs text-muted-foreground">{tool.description}</div>
                      </Link>
                    ))}
                  </div>
                )}
              </div>

              {/* User Profile */}
              <div className="flex items-center">
                <UserButton
                  appearance={{
                    elements: {
                      ...userButtonElements
                    }
                  }}
                  userProfileProps={{
                    additionalOAuthScopes: {
                      google: ['profile', 'email']
                    }
                  }}
                >
                  <UserButton.MenuItems>
                    {plan === 'free' && (
                      <UserButton.Action
                        label={manageLabel}
                        labelIcon={manageIcon}
                        onClick={goToPortal}
                      />
                    )}
                    {plan === 'free' ? (
                      <>
                        <UserButton.Action label="manageAccount" />
                        <UserButton.Action label="signOut" />
                      </>
                    ) : (
                      <UserButton.Action
                        label={manageLabel}
                        labelIcon={manageIcon}
                        onClick={goToPortal}
                      />
                    )}
                  </UserButton.MenuItems>
                </UserButton>
              </div>
            </div>
          </div>

          {/* Mobile menu button */}
          <div className="md:hidden flex items-center space-x-4">
            <UserButton
              appearance={{
                elements: {
                  ...userButtonElements
                }
              }}
            >
              <UserButton.MenuItems>
                {plan === 'free' && (
                  <UserButton.Action
                    label={manageLabel}
                    labelIcon={manageIcon}
                    onClick={goToPortal}
                  />
                )}
                {plan === 'free' ? (
                  <>
                    <UserButton.Action label="manageAccount" />
                    <UserButton.Action label="signOut" />
                  </>
                ) : (
                  <UserButton.Action
                    label={manageLabel}
                    labelIcon={manageIcon}
                    onClick={goToPortal}
                  />
                )}
              </UserButton.MenuItems>
            </UserButton>
            <button
              onClick={() => setIsMenuOpen(!isMenuOpen)}
              className="text-muted-foreground hover:text-foreground inline-flex items-center justify-center p-2 rounded-md focus:outline-none focus:ring-2 focus:ring-inset focus:ring-primary/30"
            >
              {isMenuOpen ? (
                <X className="block h-6 w-6" />
              ) : (
                <Menu className="block h-6 w-6" />
              )}
            </button>
          </div>
        </div>

        {/* Mobile Navigation */}
        {isMenuOpen && (
          <div className="md:hidden">
            <div className="px-2 pt-2 pb-3 space-y-1 sm:px-3 bg-background border-t border-border">
              <Link
                href="/dashboard"
                className="text-foreground hover:text-primary block px-3 py-2 text-base font-medium flex items-center"
                onClick={() => setIsMenuOpen(false)}
              >
                <Home className="w-5 h-5 mr-2" />
                Dashboard
              </Link>

              <Link
                href="/academy"
                className="text-foreground hover:text-primary block px-3 py-2 text-base font-medium flex items-center"
                onClick={() => setIsMenuOpen(false)}
              >
                <GraduationCap className="w-5 h-5 mr-2" />
                Academy
              </Link>

              {/* Mobile Calculators */}
              <div className="px-3 py-2">
                <div className="text-muted-foreground font-medium text-sm mb-2 flex items-center">
                  <Calculator className="w-4 h-4 mr-2" />
                  Calculators
                </div>
                {calculators.map((calc) => {
                  const isLocked = calc.isPremium && !isPremium
                  return (
                    <Link
                      key={calc.href}
                      href={calc.href}
                      className={`block pl-6 py-2 text-sm flex items-center justify-between ${
                        isLocked ? 'text-muted-foreground/60' : 'text-muted-foreground hover:text-primary'
                      }`}
                      onClick={() => setIsMenuOpen(false)}
                    >
                      <span>{calc.name}</span>
                      {isLocked && <Lock className="w-3.5 h-3.5" />}
                    </Link>
                  )
                })}
              </div>

              {/* Mobile Tools */}
              <div className="px-3 py-2">
                <div className="text-muted-foreground font-medium text-sm mb-2 flex items-center">
                  <Wrench className="w-4 h-4 mr-2" />
                  Tools
                </div>
                {tools.map((tool) => (
                  <Link
                    key={tool.href}
                    href={tool.href}
                    className="block pl-6 py-2 text-sm text-muted-foreground hover:text-primary"
                    onClick={() => setIsMenuOpen(false)}
                  >
                    {tool.name}
                  </Link>
                ))}
              </div>
            </div>
          </div>
        )}
      </nav>
    </header>
  )
}
