export function getApiBaseUrl() {
  // Server-side (SSR / route handlers / RSC)
  if (typeof window === "undefined") {
    return process.env.INTERNAL_API_URL!;
  }
  // Browser
  return process.env.NEXT_PUBLIC_API_URL!;
}
