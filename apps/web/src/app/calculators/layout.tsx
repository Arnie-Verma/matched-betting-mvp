'use client'

import { useUser } from '@clerk/nextjs'
import { redirect } from 'next/navigation'
import { ReactNode } from 'react'

interface CalculatorsLayoutProps {
  children: ReactNode
}

export default function CalculatorsLayout({ children }: CalculatorsLayoutProps) {
  const { isSignedIn, isLoaded } = useUser()

  // Wait for Clerk to load
  if (!isLoaded) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    )
  }

  // Redirect to sign-in if not authenticated
  if (!isSignedIn) {
    redirect('/sign-in')
  }

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-4xl mx-auto px-4 py-8">
        {children}
      </div>
    </div>
  )
}
