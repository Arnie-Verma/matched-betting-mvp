import { callApi } from '@/lib/serverApi'

// Force dynamic rendering - no caching
export const dynamic = 'force-dynamic'
export const revalidate = 0

export async function GET(request: Request) {
  const response = await callApi(`/metadata/sports`)

  const data = await response.json()

  // Return response
  return new Response(JSON.stringify(data), {
    status: response.status,
    headers: {
      'Content-Type': 'application/json',
      'Cache-Control': 'public, max-age=300', // Cache for 5 minutes since sports don't change often
    },
  })
}
