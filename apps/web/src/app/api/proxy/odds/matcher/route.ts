import { callApi } from '@/lib/serverApi'

// Force dynamic rendering - no caching
export const dynamic = 'force-dynamic'
export const revalidate = 0

export async function GET(request: Request) {
  console.log('[matcher/route.ts] === GET /api/proxy/odds/matcher ===')
  const { searchParams } = new URL(request.url)
  const queryString = searchParams.toString()
  console.log('[matcher/route.ts] Query params:', queryString)

  const response = await callApi(`/odds/matcher?${queryString}`)
  console.log('[matcher/route.ts] Response status:', response.status)

  const text = await response.text()
  console.log('[matcher/route.ts] Response body length:', text.length)
  console.log('[matcher/route.ts] Response preview:', text.substring(0, 200))

  // Return response with no-cache headers
  return new Response(text, {
    status: response.status,
    headers: {
      'Content-Type': 'application/json',
      'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0',
      'Pragma': 'no-cache',
      'Expires': '0',
    },
  })
}
