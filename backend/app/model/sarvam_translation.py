"""Small retrying Sarvam text-translation adapter for transcript segments."""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from typing import Any


class SarvamTranslationError(RuntimeError):
    """Raised when Sarvam cannot produce a usable English translation."""


class SarvamTranslator:
    """Translate Malayalam transcript segments with the frozen Chat 03 settings."""

    def __init__(
        self,
        client: Any | None = None,
        api_key: str | None = None,
        *,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._client = client or self._build_client(api_key)
        self._sleep = sleep

    def __call__(self, original_text: str) -> str:
        return self.translate(original_text)

    def translate(self, original_text: str) -> str:
        """Return a stripped English translation after at most three attempts."""
        for attempt in range(3):
            try:
                response = self._client.text.translate(
                    input=original_text,
                    model="sarvam-translate:v1",
                    source_language_code="ml-IN",
                    target_language_code="en-IN",
                )
                translated_text = _field(response, "translated_text")
                if not isinstance(translated_text, str) or not translated_text.strip():
                    raise SarvamTranslationError("Sarvam returned an empty translation")
                return translated_text.strip()
            except Exception as error:
                if isinstance(error, SarvamTranslationError) or not _is_transient(error):
                    raise
                if attempt == 2:
                    raise
                self._sleep(0.1 * (attempt + 1))

        raise AssertionError("unreachable")

    @staticmethod
    def _build_client(api_key: str | None) -> Any:
        api_key = api_key or os.environ.get("SARVAM_API_KEY")
        if not api_key:
            raise ValueError("SARVAM_API_KEY is not set")
        try:
            from sarvamai import SarvamAI
        except ImportError as error:
            raise RuntimeError("The sarvamai package is required to use SarvamTranslator") from error
        return SarvamAI(api_subscription_key=api_key)


def translate_to_english(transcript: str, client: Any, *, sleep: Callable[[float], None] = time.sleep) -> str:
    """Convenience function for callers that already own a configured Sarvam client."""
    return SarvamTranslator(client=client, sleep=sleep).translate(transcript)


def _field(value: Any, name: str) -> Any:
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _is_transient(error: Exception) -> bool:
    status_code = _status_code(error)
    if status_code == 429 or status_code is not None and 500 <= status_code <= 599:
        return True
    if isinstance(error, (TimeoutError, ConnectionError)):
        return True
    name = type(error).__name__.lower()
    message = str(error).lower()
    return "timeout" in name or "timeout" in message or "connection" in name


def _status_code(error: Exception) -> int | None:
    for value in (getattr(error, "status_code", None), getattr(error, "status", None)):
        if isinstance(value, int):
            return value
    response = getattr(error, "response", None)
    value = getattr(response, "status_code", None)
    return value if isinstance(value, int) else None
