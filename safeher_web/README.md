# SafeHer Contact Track Page

Static page for emergency contacts — opens from WhatsApp link:
`https://safeher.app/track?token={signed_jwt}`

## Deploy to production

1. Upload `track/index.html` to your static host for `safeher.app`.
2. Configure SPA rewrite: `/track` → `/track/index.html` (preserve query string).
3. Ensure CORS on `api.safeher.app` allows `https://safeher.app` (already set in backend for production).

## Local development

The backend serves this page at `http://localhost:8000/track/` when the monorepo layout is intact.

For a custom API during local testing, set before load:
```html
<script>window.SAFEHER_API_BASE = "http://10.0.2.2:8000";</script>
```

## Behaviour

- Polls `GET /api/v1/location/live?token=` every 7 seconds
- Shows Google Maps embed when coordinates are available
- Hides location when alert status is `cancelled`
