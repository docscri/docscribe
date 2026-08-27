import logging
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator
from supabase import Client

from app.supabase_client import supabase

logger = logging.getLogger(__name__)
SpeakerRole = Literal["doctor", "patient", "relative", "nurse", "unknown"]


class ModelSegment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    speaker_id: str = Field(min_length=1)
    speaker_role: SpeakerRole
    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)
    original_text: str
    english_text: str | None = None

    @model_validator(mode="after")
    def validate_times(self):
        if self.end_ms < self.start_ms:
            raise ValueError("end_ms must be greater than or equal to start_ms")
        return self


class ModelOPDNote(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chief_complaint: str
    history: str
    examination: str
    assessment: str
    plan: str


class ModelProcessingResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    segments: list[ModelSegment]
    opd_note: ModelOPDNote


def mark_processing_failed(consultation_id: str, error_message: str = "Audio processing failed", client: Client = supabase) -> None:
    client.table("consultations").update({"status": "failed", "error": error_message}).eq("consultation_id", consultation_id).execute()


def save_processing_result(consultation_id: str, result: ModelProcessingResult, client: Client = supabase) -> None:
    rows = [{"segment_id": f"SEG-{uuid4().hex[:12].upper()}", "consultation_id": consultation_id, **segment.model_dump()} for segment in result.segments]
    try:
        client.table("transcript_segments").delete().eq("consultation_id", consultation_id).execute()
        if rows:
            client.table("transcript_segments").insert(rows).execute()
        client.table("opd_notes").upsert({"consultation_id": consultation_id, **result.opd_note.model_dump()}, on_conflict="consultation_id").execute()
        client.table("consultations").update({"status": "ready_for_review", "error": None}).eq("consultation_id", consultation_id).execute()
    except Exception:
        logger.exception("Failed to save processing result for %s", consultation_id)
        mark_processing_failed(consultation_id, "Could not save the processing result", client)
        raise
