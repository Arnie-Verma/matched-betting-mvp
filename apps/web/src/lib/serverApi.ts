// apps/web/src/lib/serverApi.ts
import { auth } from '@clerk/nextjs/server';

const INTERNAL_API_URL = process.env.INTERNAL_API_URL || 'http://api:8000';

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
  const response = await fetch(url, {
    ...init,
    headers,
  });

  return response;
}