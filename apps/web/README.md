# Web

Next.js frontend for dashboard and odds matcher.

## Responsibilities
- Render matcher UI and filters
- Trigger background refresh requests
- Poll refresh status and show progress/degraded states
- Proxy selected API routes to backend

## Common Commands
```bash
# Run web app locally
npm run dev --workspace apps/web
```

## Key Paths
- `src/app/dashboard/odds-matcher` - matcher page
- `src/components/odds-matcher` - matcher UI components
- `src/app/api/proxy` - server-side proxy routes to API
