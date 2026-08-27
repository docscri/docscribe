"""Small Sarvam Batch transcription and text-translation adapter."""

from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any


class SarvamClient:
    """Wrap only the Sarvam operations needed by future orchestration."""

    def __init__(self, client: Any | None = None, api_key: str | None = None) -> None:
        if client is not None:
            self._client = client
            return

        api_key = api_key or os.environ.get("SARVAM_API_KEY")
        if not api_key:
            raise ValueError("SARVAM_API_KEY is not set")

        try:
            from sarvamai import SarvamAI
        except ImportError as error:
            raise RuntimeError("The sarvamai package is required to use SarvamClient") from error

        self._client = SarvamAI(api_subscription_key=api_key)

    def transcribe_batch(self, audio_path: str) -> list[dict[str, Any]]:
        """Transcribe one local audio file with Saaras v3 diarization enabled."""
        job = self._client.speech_to_text_job.create_job(
            model="saaras:v3",
            mode="transcribe",
            with_diarization=True,
        )
        job.upload_files(file_paths=[audio_path])
        job.start()
        status = job.wait_until_complete()
        self._raise_if_failed(status)

        with TemporaryDirectory() as output_dir:
            result = job.download_outputs(output_dir=output_dir)
            self._raise_if_failed(result)
            payload = self._result_payload(result, Path(output_dir))

        return [self._normalize_entry(entry) for entry in self._entries(payload)]

    def translate_to_english(self, transcript: str) -> str:
        """Translate one transcript string to English using Sarvam text translation."""
        response = self._client.text.translate(
            input=transcript,
            target_language_code="en-IN",
        )
        translated = self._field(response, "translated_text")
        if not isinstance(translated, str) or not translated.strip():
            raise RuntimeError("Sarvam returned an empty translation")
        return translated

    @classmethod
    def _normalize_entry(cls, entry: Any) -> dict[str, Any]:
        return {
            "speaker_id": cls._speaker_id(cls._field(entry, "speaker_id", "speaker")),
            "start_ms": round(cls._field(entry, "start_time_seconds", "start") * 1000),
            "end_ms": round(cls._field(entry, "end_time_seconds", "end") * 1000),
            "original_text": cls._field(entry, "transcript", "text"),
        }

    @staticmethod
    def _speaker_id(value: Any) -> str:
        speaker = str(value)
        if speaker.startswith("SPEAKER_"):
            return speaker
        try:
            return f"SPEAKER_{int(speaker):02d}"
        except ValueError:
            return speaker

    @classmethod
    def _entries(cls, payload: Any) -> list[Any]:
        diarized = cls._field(payload, "diarized_transcript", default=None)
        entries = cls._field(diarized, "entries", "segments", default=None)
        if entries is None:
            entries = cls._field(payload, "entries", "segments", default=None)
        if not isinstance(entries, list):
            raise RuntimeError("Sarvam result did not contain diarized transcript entries")
        return entries

    @classmethod
    def _result_payload(cls, result: Any, output_dir: Path) -> Any:
        if isinstance(result, (dict, list)) or hasattr(result, "diarized_transcript"):
            return result
        json_files = list(output_dir.rglob("*.json"))
        if len(json_files) != 1:
            raise RuntimeError("Sarvam did not produce exactly one transcript result")
        with json_files[0].open(encoding="utf-8") as result_file:
            return json.load(result_file)

    @classmethod
    def _raise_if_failed(cls, response: Any) -> None:
        state = cls._field(response, "job_state", "state", default=None)
        if isinstance(state, str) and state.lower() in {"failed", "cancelled", "canceled"}:
            message = cls._field(response, "error_message", "error", default="unknown error")
            raise RuntimeError(f"Sarvam Batch job failed: {message}")

    @staticmethod
    def _field(value: Any, *names: str, default: Any = None) -> Any:
        for name in names:
            if isinstance(value, dict) and name in value:
                return value[name]
            if hasattr(value, name):
                return getattr(value, name)
        return default
