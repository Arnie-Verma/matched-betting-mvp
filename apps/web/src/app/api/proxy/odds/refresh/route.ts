import { callApi } from '@/lib/serverApi'

export async function POST(request: Request) {
  const body = await request.json()

  return callApi('/odds/refresh', {
    method: 'POST',
    body: JSON.stringify(body),
    headers: {
      'Content-Type': 'application/json',
    },
  })
}
