import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.consultations import router as consultations_router

app = FastAPI(title="DocScribe API", version="1.0.0")
allowed_origins = [origin.strip() for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",") if origin.strip()]
if "*" in allowed_origins:
    raise RuntimeError("ALLOWED_ORIGINS must contain explicit origins when credentials are enabled")
app.add_middleware(CORSMiddleware, allow_origins=allowed_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
async def health():
    return {"status": "ok"}


app.include_router(
    consultations_router,
    prefix="/api/v1",
)
