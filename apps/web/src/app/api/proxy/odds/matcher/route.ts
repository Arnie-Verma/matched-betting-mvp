import { callApi } from '@/lib/serverApi'

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url)
  const queryString = searchParams.toString()

  return callApi(`/odds/matcher?${queryString}`)
}
