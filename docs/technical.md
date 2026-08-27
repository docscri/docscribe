# Technical Notes

## Flow

`Frontend -> FastAPI -> Supabase Storage -> Sarvam -> Groq -> Supabase`

The backend verifies Supabase authentication, stores private audio, runs transcription and OPD generation, validates the results, and saves them to Supabase.

Local integration is complete: authentication, upload, processing, result retrieval, editing, playback, and deletion were verified.

## API

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/health` | API process health |
| `POST/GET` | `/api/v1/consultations/` | Create or list consultations |
| `GET/DELETE` | `/api/v1/consultations/{id}` | Read or delete a consultation |
| `GET` | `/api/v1/consultations/{id}/status` | Read processing status |
| `GET/PATCH` | `/api/v1/consultations/{id}/transcript` | Read or edit transcript |
| `PATCH` | `/api/v1/consultations/{id}/opd-note` | Edit OPD note |
| `GET` | `/api/v1/consultations/{id}/audio` | Create a temporary audio URL |

## Limits

- Malayalam input and English output only.
- MP3, WAV, and M4A; maximum 50 MB.
- A backend restart can interrupt processing.
- Failed jobs are not retried automatically.
- Patient use requires approved privacy and consent procedures.
