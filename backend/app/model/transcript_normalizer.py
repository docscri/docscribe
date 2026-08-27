"""Convert Saaras v3 diarized output into frozen DocScribe transcript segments."""

from __future__ import annotations

import math
from collections.abc import Callable
from numbers import Real
from typing import Any


class TranscriptNormalizationError(ValueError):
    """Raised when Saaras output cannot form a valid DocScribe segment."""


def normalize_saaras_segments(
    raw_result: dict[str, Any] | list[dict[str, Any]], translator: Callable[[str], str]
) -> list[dict[str, Any]]:
    """Normalize retained diarized entries and translate each one independently."""
    entries = _entries(raw_result)
    segments: list[dict[str, Any]] = []

    for entry in entries:
        if not isinstance(entry, dict):
            raise TranscriptNormalizationError("Saaras diarized entry must be an object")

        original_text = _transcript(entry)
        if not original_text:
            continue

        speaker_id = _speaker_id(entry)
        start_ms = _milliseconds(entry, "start_time_seconds")
        end_ms = _milliseconds(entry, "end_time_seconds")
        if end_ms < start_ms:
            raise TranscriptNormalizationError("end_time_seconds precedes start_time_seconds")

        translated_text = translator(original_text)
        if not isinstance(translated_text, str) or not translated_text.strip():
            raise TranscriptNormalizationError("Translator returned an empty translation")

        segments.append(
            {
                "speaker_id": speaker_id,
                "speaker_role": "unknown",
                "start_ms": start_ms,
                "end_ms": end_ms,
                "original_text": original_text,
                "english_text": translated_text.strip(),
            }
        )

    return sorted(segments, key=lambda segment: segment["start_ms"])


def _entries(raw_result: dict[str, Any] | list[dict[str, Any]]) -> list[Any]:
    if isinstance(raw_result, list):
        return [_expand_normalized_entry(entry) for entry in raw_result]
    try:
        entries = raw_result["diarized_transcript"]["entries"]
    except (KeyError, TypeError) as error:
        raise TranscriptNormalizationError(
            "Saaras result is missing diarized_transcript.entries"
        ) from error
    if not isinstance(entries, list):
        raise TranscriptNormalizationError("Saaras diarized_transcript.entries must be a list")
    return entries


def _expand_normalized_entry(entry: Any) -> Any:
    if not isinstance(entry, dict):
        return entry
    if not {"speaker_id", "start_ms", "end_ms", "original_text"}.issubset(entry):
        return entry
    return {
        "speaker_id": entry["speaker_id"],
        "start_time_seconds": entry["start_ms"] / 1000,
        "end_time_seconds": entry["end_ms"] / 1000,
        "transcript": entry["original_text"],
    }


def _speaker_id(entry: dict[str, Any]) -> str:
    if "speaker_id" not in entry or entry["speaker_id"] is None:
        raise TranscriptNormalizationError("Saaras entry is missing speaker_id")
    speaker_id = str(entry["speaker_id"])
    if not speaker_id.strip():
        raise TranscriptNormalizationError("Saaras entry has an empty speaker_id")
    return speaker_id


def _milliseconds(entry: dict[str, Any], field: str) -> int:
    if field not in entry:
        raise TranscriptNormalizationError(f"Saaras entry is missing {field}")
    seconds = entry[field]
    if isinstance(seconds, bool) or not isinstance(seconds, Real) or not math.isfinite(seconds):
        raise TranscriptNormalizationError(f"Saaras entry has an invalid {field}")
    if seconds < 0:
        raise TranscriptNormalizationError(f"Saaras entry has a negative {field}")
    return round(seconds * 1000)


def _transcript(entry: dict[str, Any]) -> str:
    if "transcript" not in entry:
        raise TranscriptNormalizationError("Saaras entry is missing transcript")
    transcript = entry["transcript"]
    if not isinstance(transcript, str):
        raise TranscriptNormalizationError("Saaras entry has an invalid transcript")
    return transcript.strip()
