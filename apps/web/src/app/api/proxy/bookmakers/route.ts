import { callApi } from '@/lib/serverApi'

// Force dynamic rendering - no caching
export const dynamic = 'force-dynamic'
export const revalidate = 0

export async function GET() {
  const response = await callApi(`/metadata/bookmakers`)

  if (!response.ok) {
    const text = await response.text()
    console.error('[bookmakers/route] API error:', response.status, text)
    return new Response(JSON.stringify({ error: text }), {
      status: response.status,
      headers: { 'Content-Type': 'application/json' },
    })
  }

  const data = await response.json()

  // Return response
  return new Response(JSON.stringify(data), {
    status: response.status,
    headers: {
      'Content-Type': 'application/json',
      'Cache-Control': 'public, max-age=300', // Cache for 5 minutes since bookmakers don't change often
    },
  })
}
