// apps/web/src/lib/clientApi.ts
'use client';

// Client-side API helper for use in components
export const clientApi = {
  async get(path: string): Promise<unknown> {
    const response = await fetch(`/api/proxy${path}`);
    if (!response.ok) {
      throw new Error(`API request failed: ${response.statusText}`);
    }
    return response.json();
  },

  async post(path: string, data: unknown): Promise<unknown> {
    const response = await fetch(`/api/proxy${path}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    });
    if (!response.ok) {
      throw new Error(`API request failed: ${response.statusText}`);
    }
    return response.json();
  },
};

// For backward compatibility
export const serverApi = clientApi;