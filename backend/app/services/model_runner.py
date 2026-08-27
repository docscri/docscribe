import asyncio
import inspect
import logging

from app.services.processing import ModelProcessingResult, mark_processing_failed, save_processing_result

logger = logging.getLogger(__name__)


def run_model_processing(consultation_id: str, audio_path: str) -> None:
    try:
        from app.model.process_audio import process_audio
        result = process_audio(consultation_id, audio_path)
        if inspect.isawaitable(result):
            result = asyncio.run(result)
        validated = ModelProcessingResult.model_validate(result)
    except Exception:
        logger.exception("Model processing failed for %s", consultation_id)
        try:
            mark_processing_failed(consultation_id)
        except Exception:
            logger.exception("Could not mark %s as failed", consultation_id)
        return
    try:
        save_processing_result(consultation_id, validated)
    except Exception:
        pass
