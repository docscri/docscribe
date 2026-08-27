# Deployment Handoff

Development and local end-to-end integration are complete. The deployment developer owns the remaining work below.

## Before deployment

1. Confirm both Supabase migrations and the private `consultation-audio` bucket.
2. Rotate previously shared Sarvam and Groq keys.
3. Configure custom SMTP and test a confirmation email.
4. Run backend tests, frontend lint, and frontend build.

## Backend

Deploy `backend/` using:

```text
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Set:

```env
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
SARVAM_API_KEY=
GROQ_API_KEY=
ALLOWED_ORIGINS=https://your-frontend.vercel.app
```

Confirm `/health` returns `{"status":"ok"}`.

## Frontend

Deploy `frontend/` to Vercel as a Next.js project and set:

```env
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=
NEXT_PUBLIC_API_URL=https://your-backend.example.com
NEXT_PUBLIC_SITE_URL=https://your-frontend.vercel.app
```

Add the production frontend URL to Supabase Authentication URL Configuration and backend `ALLOWED_ORIGINS`.

## Final test

Using synthetic audio, verify signup, upload, processing, editing, playback, and deletion. Check backend logs on failure.

Never commit `.env` files or place backend secrets in Vercel.
