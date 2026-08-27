"""Provider-agnostic OPD note generation with strict response validation."""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, ValidationError

from .opd_prompt import build_messages


class OPDGenerationError(RuntimeError):
    """Raised when an OPD note cannot be safely generated."""


class OPDInputError(OPDGenerationError, ValueError):
    """Raised when transcript turns cannot form a usable OPD input."""


class TranscriptTurn(BaseModel):
    """The frozen OPD input contract; no roles, timing, or original text enter the provider."""

    model_config = ConfigDict(extra="forbid", strict=True)

    speaker_id: str
    english_text: str


class OPDNote(BaseModel):
    """The exact five-field DocScribe OPD output contract."""

    model_config = ConfigDict(extra="forbid", strict=True)

    chief_complaint: str
    history: str
    examination: str
    assessment: str
    plan: str


class OPDProvider(Protocol):
    """Provider boundary: return one completed structured-output payload per call."""

    def generate(
        self, *, messages: Sequence[Mapping[str, str]], response_schema: Mapping[str, Any]
    ) -> Any: ...


def opd_json_schema() -> dict[str, Any]:
    """Derive the strict provider schema from the same model used for local validation."""
    schema = OPDNote.model_json_schema()
    schema.pop("title", None)
    for property_schema in schema["properties"].values():
        property_schema.pop("title", None)
    return schema


class GroqOPDProvider:
    """MVP-only Groq adapter; production provider selection is deliberately outside it."""

    model = "openai/gpt-oss-120b"

    def __init__(self, client: Any | None = None, api_key: str | None = None) -> None:
        self._client = client or self._build_client(api_key)

    def generate(
        self, *, messages: Sequence[Mapping[str, str]], response_schema: Mapping[str, Any]
    ) -> Any:
        response = self._client.chat.completions.create(
            model=self.model,
            messages=list(messages),
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "docsribe_opd_note",
                    "strict": True,
                    "schema": dict(response_schema),
                },
            },
            temperature=0,
        )
        try:
            return response.choices[0].message.content
        except (AttributeError, IndexError, TypeError) as error:
            raise OPDGenerationError("Groq returned no completed message content") from error

    @staticmethod
    def _build_client(api_key: str | None) -> Any:
        api_key = api_key or os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY is not set")
        try:
            from groq import Groq
        except ImportError as error:
            raise RuntimeError("The groq package is required to use GroqOPDProvider") from error
        return Groq(api_key=api_key)


class OPDGenerator:
    """Generate and validate an OPD note without changing any external consultation state."""

    def __init__(
        self,
        provider: OPDProvider,
        *,
        max_transport_attempts: int = 3,
        retry_delay_seconds: float = 0.25,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if max_transport_attempts < 1:
            raise ValueError("max_transport_attempts must be at least 1")
        self._provider = provider
        self._max_transport_attempts = max_transport_attempts
        self._retry_delay_seconds = retry_delay_seconds
        self._sleep = sleep

    def generate(self, turns: Sequence[TranscriptTurn | Mapping[str, Any]]) -> OPDNote:
        """Make at most two fresh generations, each with bounded transport retries."""
        validated_turns = _validate_turns(turns)
        messages = build_messages(validated_turns)
        schema = opd_json_schema()

        for generation_attempt in range(2):
            payload = self._generate_with_transport_retries(messages, schema)
            try:
                return _validate_and_normalize_note(payload)
            except (ValidationError, TypeError, ValueError, json.JSONDecodeError) as error:
                if generation_attempt == 1:
                    raise OPDGenerationError(
                        "Provider returned an invalid OPD structured response twice"
                    ) from error

        raise AssertionError("unreachable")

    def _generate_with_transport_retries(
        self, messages: Sequence[Mapping[str, str]], schema: Mapping[str, Any]
    ) -> Any:
        for attempt in range(self._max_transport_attempts):
            try:
                return self._provider.generate(messages=messages, response_schema=schema)
            except Exception as error:
                if not _is_transient_provider_error(error) or attempt == self._max_transport_attempts - 1:
                    raise
                self._sleep(self._retry_delay_seconds * (2**attempt))
        raise AssertionError("unreachable")


def _validate_turns(turns: Sequence[TranscriptTurn | Mapping[str, Any]]) -> list[TranscriptTurn]:
    try:
        validated = [
            turn if isinstance(turn, TranscriptTurn) else TranscriptTurn.model_validate(turn, strict=True)
            for turn in turns
        ]
    except (ValidationError, TypeError) as error:
        raise OPDInputError("Each OPD turn must contain only string speaker_id and english_text") from error
    usable_turns = [turn for turn in validated if turn.english_text.strip()]
    if not usable_turns:
        raise OPDInputError("No usable English transcript turn exists")
    return usable_turns


def _validate_and_normalize_note(payload: Any) -> OPDNote:
    if isinstance(payload, str):
        payload = json.loads(payload)
    if not isinstance(payload, Mapping):
        raise TypeError("OPD provider response must be a JSON object")
    note = OPDNote.model_validate(payload, strict=True)
    return OPDNote(**{field: value.strip() for field, value in note.model_dump().items()})


def _is_transient_provider_error(error: Exception) -> bool:
    status_code = _status_code(error)
    if status_code in (408, 429) or status_code is not None and 500 <= status_code <= 599:
        return True
    if isinstance(error, (TimeoutError, ConnectionError)):
        return True
    name = type(error).__name__.lower()
    message = str(error).lower()
    return (
        "timeout" in name
        or "timeout" in message
        or "connection" in name
        or "connection" in message
        or "connect" in name
        or "network" in name
        or "network" in message
    )


def _status_code(error: Exception) -> int | None:
    for value in (getattr(error, "status_code", None), getattr(error, "status", None)):
        if isinstance(value, int):
            return value
    response = getattr(error, "response", None)
    value = getattr(response, "status_code", None)
    return value if isinstance(value, int) else None
