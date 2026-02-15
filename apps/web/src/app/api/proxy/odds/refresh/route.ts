import { callApi } from '@/lib/serverApi'

// CRITICAL: Extend timeout for scraping operations (default is 10s, we need 60s for scraping)
export const maxDuration = 60; // 60 seconds for Vercel/Next.js

export async function POST(request: Request) {
  console.log('[refresh/route.ts] === POST /api/proxy/odds/refresh ===')
  console.time('[refresh/route.ts] Total time')
  try {
    const body = await request.json()

    const response = await callApi('/odds/refresh', {
      method: 'POST',
      body: JSON.stringify(body),
      headers: {
        'Content-Type': 'application/json',
      },
    })

    console.timeEnd('[refresh/route.ts] Total time')
    console.log('[refresh/route.ts] Response status:', response.status)

    return response
  } catch (error) {
    console.timeEnd('[refresh/route.ts] Total time')
    console.error('[refresh/route.ts] Proxy error:', error)
    return new Response(
      JSON.stringify({
        error: 'Refresh proxy failed',
        detail: error instanceof Error ? error.message : String(error),
      }),
      {
        status: 502,
        headers: { 'Content-Type': 'application/json' },
      }
    )
  }
}
