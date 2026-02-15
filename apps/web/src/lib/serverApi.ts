// apps/web/src/lib/serverApi.ts
import 'server-only';
import { auth } from '@clerk/nextjs/server';

const INTERNAL_API_URL = process.env.INTERNAL_API_URL || 'http://api:8000';
const API_TIMEOUT_MS = Number(process.env.INTERNAL_API_TIMEOUT_MS || 60000);

export async function callApi(
  path: string,
  init?: RequestInit
): Promise<Response> {
  console.log('[serverApi] path:', path);

  const url = `${INTERNAL_API_URL}${path}`;
  const headers = new Headers(init?.headers);

  try {
    // Get auth context (works with cookies from request)
    const { getToken, userId } = await auth();
    console.log('[serverApi] userId:', userId);

    if (getToken) {
      const token = await getToken({ template: 'mb-api' });
      const hasToken = !!token;
      console.log('[serverApi] path:', path, 'mintedToken?', hasToken);

      if (token) {
        headers.set('Authorization', `Bearer ${token}`);
        console.log('[serverApi] auth hdr:', `Bearer ${token.substring(0, 30)}...`);
      }
    }
  } catch (error) {
    console.error('[serverApi] Auth error:', error);
  }

  console.log('[serverApi] fetch →', url);

  const timeoutController = new AbortController();
  const timeoutId = setTimeout(() => timeoutController.abort(), API_TIMEOUT_MS);

  try {
    const response = await fetch(url, {
      ...init,
      headers,
      signal: timeoutController.signal,
    });
    return response;
  } catch (error) {
    const isTimeout =
      error instanceof DOMException && error.name === 'AbortError';
    const message = isTimeout
      ? `Upstream API timeout after ${API_TIMEOUT_MS}ms`
      : 'Upstream API request failed';
    console.error('[serverApi] Fetch error:', message, error);

    return new Response(
      JSON.stringify({
        error: message,
        detail: error instanceof Error ? error.message : String(error),
      }),
      {
        status: isTimeout ? 504 : 503,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  } finally {
    clearTimeout(timeoutId);
  }
}
