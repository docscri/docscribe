"""Audio format normalization for Sarvam compatibility."""

from pathlib import Path
from typing import Any

import librosa
import numpy as np
import soundfile as sf


def resample_to_16khz(audio_path: str, output_path: str) -> None:
    """
    Resample audio to 16 kHz mono WAV format required by Sarvam Saaras v3.
    
    Args:
        audio_path: Path to input audio file (WAV, MP3, M4A supported)
        output_path: Path to write 16 kHz mono WAV file
    
    Raises:
        RuntimeError: If audio cannot be loaded or processed
    """
    try:
        # Load audio with automatic format detection
        # librosa resamples to the target_sr automatically
        audio_data, original_sr = librosa.load(audio_path, sr=16000, mono=True)
    except Exception as error:
        raise RuntimeError(f"Could not load audio file: {error}") from error
    
    if not isinstance(audio_data, np.ndarray) or audio_data.size == 0:
        raise RuntimeError("Audio data is empty or invalid")
    
    # Clamp values to valid range for 16-bit PCM
    audio_data = np.clip(audio_data, -1.0, 1.0)
    
    try:
        # Write as 16-bit PCM WAV (Sarvam requirement)
        sf.write(output_path, audio_data, 16000, subtype='PCM_16')
    except Exception as error:
        raise RuntimeError(f"Could not write audio file: {error}") from error


def validate_audio_format(audio_path: str) -> dict[str, Any]:
    """
    Validate audio meets Sarvam requirements: 16 kHz, mono, 16-bit PCM.
    
    Args:
        audio_path: Path to audio file to validate
    
    Returns:
        Dict with validation results and metadata
    
    Raises:
        RuntimeError: If audio is invalid
    """
    try:
        info = sf.info(audio_path)
    except Exception as error:
        raise RuntimeError(f"Could not read audio metadata: {error}") from error
    
    validation = {
        "sample_rate": info.samplerate,
        "channels": info.channels,
        "duration_seconds": info.duration,
        "is_valid": True,
        "issues": [],
    }
    
    # Check sample rate
    if info.samplerate != 16000:
        validation["is_valid"] = False
        validation["issues"].append(f"Sample rate is {info.samplerate} Hz, expected 16000 Hz")
    
    # Check channels
    if info.channels != 1:
        validation["is_valid"] = False
        validation["issues"].append(f"Audio has {info.channels} channels, expected 1 (mono)")
    
    # Check duration (practical minimum/maximum)
    if info.duration < 1:
        validation["is_valid"] = False
        validation["issues"].append("Audio is less than 1 second")
    
    if info.duration > 3600:  # 1 hour max
        validation["is_valid"] = False
        validation["issues"].append("Audio exceeds 1 hour maximum duration")
    
    return validation
