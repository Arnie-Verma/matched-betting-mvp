'use client'

import { useUser } from '@clerk/nextjs'
import PreLoginHeader from './PreLoginHeader'
import PostLoginHeader from './PostLoginHeader'

export default function Navigation() {
  const { isSignedIn, isLoaded } = useUser()

  // Don't render anything until Clerk has loaded
  if (!isLoaded) {
    return null
  }

  return (
    <>
      {isSignedIn ? <PostLoginHeader /> : <PreLoginHeader />}
    </>
  )
}