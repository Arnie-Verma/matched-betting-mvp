import { callApi } from '@/lib/serverApi'

// Force dynamic rendering - no caching
export const dynamic = 'force-dynamic'
export const revalidate = 0
export const maxDuration = 30

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url)
  const jobId = searchParams.get('job_id')

  if (!jobId) {
    return new Response(JSON.stringify({ error: 'job_id is required' }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' },
    })
  }

  try {
    const response = await callApi(`/odds/refresh/status?job_id=${encodeURIComponent(jobId)}`)
    const text = await response.text()

    return new Response(text, {
      status: response.status,
      headers: {
        'Content-Type': 'application/json',
        'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0',
      },
    })
  } catch (error) {
    return new Response(
      JSON.stringify({
        error: 'Refresh status proxy failed',
        detail: error instanceof Error ? error.message : String(error),
      }),
      {
        status: 502,
        headers: {
          'Content-Type': 'application/json',
          'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0',
        },
      }
    )
  }
}
