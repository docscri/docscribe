"""Orchestrate the DocScribe audio-to-OPD model pipeline."""

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from app.supabase_client import supabase

from .audio_processor import resample_to_16khz, validate_audio_format
from .opd_generator import GroqOPDProvider, OPDGenerator
from .sarvam_client import SarvamClient
from .sarvam_translation import SarvamTranslator
from .transcript_normalizer import normalize_saaras_segments

AUDIO_BUCKET = "consultation-audio"


def process_audio(consultation_id: str, audio_path: str) -> dict[str, Any]:
    """Download, transcribe, translate, and summarize one consultation audio file."""
    if not consultation_id.strip():
        raise ValueError("consultation_id is required")
    if not audio_path.strip():
        raise ValueError("audio_path is required")
    
    audio_data = supabase.storage.from_(AUDIO_BUCKET).download(audio_path)
    if not isinstance(audio_data, bytes) or not audio_data:
        raise RuntimeError("Supabase returned an empty audio file")
    
    suffix = Path(audio_path).suffix.lower() or ".wav"
    
    with TemporaryDirectory(prefix=f"docscribe-{consultation_id}-") as directory:
        # Write downloaded audio to temp file
        local_audio = Path(directory) / f"consultation{suffix}"
        local_audio.write_bytes(audio_data)
        
        # Resample to 16 kHz mono WAV (Sarvam requirement)
        resampled_audio = Path(directory) / "consultation_16khz.wav"
        resample_to_16khz(str(local_audio), str(resampled_audio))
        
        # Validate the resampled audio
        validation = validate_audio_format(str(resampled_audio))
        if not validation["is_valid"]:
            raise RuntimeError(f"Audio validation failed: {', '.join(validation['issues'])}")
        
        # Transcribe the properly formatted audio
        transcription_client = SarvamClient()
        raw_segments = transcription_client.transcribe_batch(str(resampled_audio))
    
    translator = SarvamTranslator()
    segments = normalize_saaras_segments(raw_segments, translator)
    if not segments:
        raise RuntimeError("Transcription produced no usable segments")
    
    turns = [
        {"speaker_id": segment["speaker_id"], "english_text": segment["english_text"]}
        for segment in segments
    ]
    note = OPDGenerator(GroqOPDProvider()).generate(turns)
    return {"segments": segments, "opd_note": note.model_dump()}
