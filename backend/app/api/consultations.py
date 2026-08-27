from pathlib import Path
from uuid import uuid4
from typing import Literal, Optional
from pydantic import BaseModel, Field
from supabase_auth.errors import AuthApiError
from fastapi import BackgroundTasks

from app.services.model_runner import run_model_processing
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
)

from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from app.supabase_client import supabase

MAX_AUDIO_SIZE = 50 * 1024 * 1024  # 50 MB
ALLOWED_AUDIO_FORMATS = {
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".m4a": "audio/mp4",
}
router = APIRouter(prefix="/consultations")
bearer = HTTPBearer()
SpeakerRole = Literal["doctor", "patient", "relative", "nurse", "unknown"]

class TranscriptSegmentUpdate(BaseModel):
    segment_id: str = Field(min_length=1, max_length=64)
    speaker_role: Optional[SpeakerRole] = None
    edited_text: Optional[str] = Field(default=None, max_length=50000)


class TranscriptUpdate(BaseModel):
    segments: list[TranscriptSegmentUpdate]
class OPDNoteUpdate(BaseModel):
    chief_complaint: Optional[str] = Field(default=None, max_length=50000)
    history: Optional[str] = Field(default=None, max_length=50000)
    examination: Optional[str] = Field(default=None, max_length=50000)
    assessment: Optional[str] = Field(default=None, max_length=50000)
    plan: Optional[str] = Field(default=None, max_length=50000)


def audio_content_matches(extension: str, audio_data: bytes) -> bool:
    if extension == ".wav":
        return len(audio_data) >= 12 and audio_data[:4] == b"RIFF" and audio_data[8:12] == b"WAVE"
    if extension == ".m4a":
        return len(audio_data) >= 12 and audio_data[4:8] == b"ftyp"
    if extension == ".mp3":
        return audio_data.startswith(b"ID3") or (len(audio_data) >= 2 and audio_data[0] == 0xFF and audio_data[1] & 0xE0 == 0xE0)
    return False

def get_doctor_id(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
) -> str:
    try:
        response = supabase.auth.get_user(
            credentials.credentials
        )
    except AuthApiError as error:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired login token",
        ) from error

    if response.user is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired login token",
        )

    return str(response.user.id)

@router.post("/")
async def create_consultation(
    background_tasks: BackgroundTasks,
    audio: UploadFile = File(...),
    patient_name: str = Form(""),
    patient_id: str = Form(""),
    doctor_id: str = Depends(get_doctor_id),
):
    if not audio.filename:
        raise HTTPException(
            status_code=400,
            detail="Audio file is required",
        )

    extension = Path(audio.filename).suffix.lower()
    mime_type = ALLOWED_AUDIO_FORMATS.get(extension)

    if mime_type is None:
        raise HTTPException(
            status_code=400,
            detail="Only MP3, WAV, and M4A files are allowed",
        )

    audio_data = await audio.read(MAX_AUDIO_SIZE + 1)

    if not audio_data:
        raise HTTPException(
            status_code=400,
            detail="Audio file is empty",
        )

    if len(audio_data) > MAX_AUDIO_SIZE:
        raise HTTPException(
            status_code=413,
            detail="Audio file must be 50 MB or smaller",
        )

    if not audio_content_matches(extension, audio_data):
        raise HTTPException(
            status_code=400,
            detail="Audio content does not match the file format",
        )

    consultation_id = f"CON-{uuid4().hex[:8].upper()}"
    storage_path = (
        f"{doctor_id}/{consultation_id}/original{extension}"
    )

    supabase.storage.from_("consultation-audio").upload(
        storage_path,
        audio_data,
        {
            "content-type": mime_type,
            "upsert": "false",
        },
    )

    try:
        supabase.table("consultations").insert({
            "consultation_id": consultation_id,
            "doctor_id": doctor_id,
            "patient_name": patient_name.strip(),
            "patient_id": patient_id.strip(),
            "status": "processing",
            "audio_path": storage_path,
            "audio_mime_type": mime_type,
        }).execute()
    except Exception:
        # Remove uploaded audio if database creation fails.
        supabase.storage.from_(
            "consultation-audio"
        ).remove([storage_path])
        raise

    background_tasks.add_task(
        run_model_processing,
        consultation_id,
        storage_path,
    )

    return {
        "consultationId": consultation_id,
        "status": "processing",
    }

@router.get("/")
async def list_consultations(
    doctor_id: str = Depends(get_doctor_id),
):
    result = (
        supabase
        .table("consultations")
        .select(
            "consultation_id, patient_id, patient_name, "
            "status, error, created_at, updated_at"
        )
        .eq("doctor_id", doctor_id)
        .order("created_at", desc=True)
        .execute()
    )

    return {
        "consultations": result.data,
    }

@router.get("/{consultation_id}")
async def get_consultation(
    consultation_id: str,
    doctor_id: str = Depends(get_doctor_id),
):
    consultation_result = (
        supabase
        .table("consultations")
        .select("*")
        .eq("consultation_id", consultation_id)
        .eq("doctor_id", doctor_id)
        .limit(1)
        .execute()
    )

    if not consultation_result.data:
        raise HTTPException(
            status_code=404,
            detail="Consultation not found",
        )

    consultation = consultation_result.data[0]

    segments_result = (
        supabase
        .table("transcript_segments")
        .select("*")
        .eq("consultation_id", consultation_id)
        .order("start_ms")
        .execute()
    )

    note_result = (
        supabase
        .table("opd_notes")
        .select("*")
        .eq("consultation_id", consultation_id)
        .limit(1)
        .execute()
    )

    return {
        "consultation": consultation,
        "segments": segments_result.data,
        "opdNote": note_result.data[0] if note_result.data else None,
    }


@router.delete("/{consultation_id}")
async def delete_consultation(
    consultation_id: str,
    doctor_id: str = Depends(get_doctor_id),
):
    result = (
        supabase
        .table("consultations")
        .select("audio_path")
        .eq("consultation_id", consultation_id)
        .eq("doctor_id", doctor_id)
        .limit(1)
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=404,
            detail="Consultation not found",
        )

    audio_path = result.data[0].get("audio_path")

    if audio_path:
        supabase.storage.from_("consultation-audio").remove([audio_path])

    (
        supabase
        .table("consultations")
        .delete()
        .eq("consultation_id", consultation_id)
        .eq("doctor_id", doctor_id)
        .execute()
    )

    return {
        "consultationId": consultation_id,
        "deleted": True,
    }

@router.get("/{consultation_id}/status")
async def get_consultation_status(
    consultation_id: str,
    doctor_id: str = Depends(get_doctor_id),
):
    result = (
        supabase
        .table("consultations")
        .select("consultation_id, status, error")
        .eq("consultation_id", consultation_id)
        .eq("doctor_id", doctor_id)
        .limit(1)
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=404,
            detail="Consultation not found",
        )

    consultation = result.data[0]

    return {
        "consultationId": consultation["consultation_id"],
        "status": consultation["status"],
        "error": consultation["error"],
    }

@router.get("/{consultation_id}/transcript")
async def get_transcript(
    consultation_id: str,
    doctor_id: str = Depends(get_doctor_id),
):
    # Check that this consultation belongs to the logged-in doctor
    consultation = (
        supabase
        .table("consultations")
        .select("consultation_id")
        .eq("consultation_id", consultation_id)
        .eq("doctor_id", doctor_id)
        .limit(1)
        .execute()
    )

    if not consultation.data:
        raise HTTPException(
            status_code=404,
            detail="Consultation not found",
        )

    # Load transcript segments
    result = (
        supabase
        .table("transcript_segments")
        .select("*")
        .eq("consultation_id", consultation_id)
        .order("start_ms")
        .execute()
    )

    return {
        "consultationId": consultation_id,
        "segments": result.data,
    }

@router.patch("/{consultation_id}/transcript")
async def update_transcript(
    consultation_id: str,
    payload: TranscriptUpdate,
    doctor_id: str = Depends(get_doctor_id),
):
    # Check that the consultation belongs to this doctor
    consultation = (
        supabase
        .table("consultations")
        .select("consultation_id")
        .eq("consultation_id", consultation_id)
        .eq("doctor_id", doctor_id)
        .limit(1)
        .execute()
    )

    if not consultation.data:
        raise HTTPException(
            status_code=404,
            detail="Consultation not found",
        )

    # Save each edited segment
    for segment in payload.segments:
        updates = {}

        if segment.speaker_role is not None:
            updates["speaker_role"] = segment.speaker_role

        if segment.edited_text is not None:
            updates["edited_text"] = segment.edited_text

        if updates:
            (
                supabase
                .table("transcript_segments")
                .update(updates)
                .eq("segment_id", segment.segment_id)
                .eq("consultation_id", consultation_id)
                .execute()
            )

    return {
        "consultationId": consultation_id,
        "saved": True,
    }

@router.patch("/{consultation_id}/opd-note")
async def update_opd_note(
    consultation_id: str,
    payload: OPDNoteUpdate,
    doctor_id: str = Depends(get_doctor_id),
):
    consultation = (
        supabase
        .table("consultations")
        .select("consultation_id")
        .eq("consultation_id", consultation_id)
        .eq("doctor_id", doctor_id)
        .limit(1)
        .execute()
    )

    if not consultation.data:
        raise HTTPException(
            status_code=404,
            detail="Consultation not found",
        )

    updates = payload.model_dump(exclude_none=True)

    if not updates:
        raise HTTPException(
            status_code=400,
            detail="No OPD note changes provided",
        )

    existing_note = (
        supabase
        .table("opd_notes")
        .select("consultation_id")
        .eq("consultation_id", consultation_id)
        .limit(1)
        .execute()
    )

    if existing_note.data:
        result = (
            supabase
            .table("opd_notes")
            .update(updates)
            .eq("consultation_id", consultation_id)
            .execute()
        )
    else:
        result = (
            supabase
            .table("opd_notes")
            .insert({
                "consultation_id": consultation_id,
                **updates,
            })
            .execute()
        )

    return {
        "consultationId": consultation_id,
        "opdNote": result.data[0],
    }

@router.get("/{consultation_id}/audio")
async def get_consultation_audio(
    consultation_id: str,
    doctor_id: str = Depends(get_doctor_id),
):
    consultation = (
        supabase
        .table("consultations")
        .select("audio_path, audio_mime_type")
        .eq("consultation_id", consultation_id)
        .eq("doctor_id", doctor_id)
        .limit(1)
        .execute()
    )

    if not consultation.data:
        raise HTTPException(
            status_code=404,
            detail="Consultation not found",
        )

    audio_path = consultation.data[0].get("audio_path")

    if not audio_path:
        raise HTTPException(
            status_code=404,
            detail="Audio not found",
        )

    signed_url = (
        supabase.storage
        .from_("consultation-audio")
        .create_signed_url(audio_path, 300)
    )

    audio_url = (
        signed_url.get("signedURL")
        or signed_url.get("signedUrl")
        or signed_url.get("signed_url")
    )

    if not audio_url:
        raise HTTPException(
            status_code=500,
            detail="Could not create audio URL",
        )

    return {
        "consultationId": consultation_id,
        "audioUrl": audio_url,
        "mimeType": consultation.data[0].get("audio_mime_type"),
        "expiresIn": 300,
    }
