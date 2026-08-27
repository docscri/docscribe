import os
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("SUPABASE_URL", "http://localhost:54321")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-key")

from app.model import process_audio as process_audio_module
from app.model.transcript_normalizer import normalize_saaras_segments


class ModelIntegrationTests(unittest.TestCase):
    def test_normalizer_accepts_sarvam_client_output(self):
        raw_segments = [{"speaker_id": "SPEAKER_00", "start_ms": 0, "end_ms": 1250, "original_text": "Namaskaram"}]
        result = normalize_saaras_segments(raw_segments, lambda text: "Hello")
        self.assertEqual(result, [{"speaker_id": "SPEAKER_00", "speaker_role": "unknown", "start_ms": 0, "end_ms": 1250, "original_text": "Namaskaram", "english_text": "Hello"}])

    @patch.object(process_audio_module, "OPDGenerator")
    @patch.object(process_audio_module, "GroqOPDProvider")
    @patch.object(process_audio_module, "SarvamTranslator")
    @patch.object(process_audio_module, "SarvamClient")
    @patch.object(process_audio_module, "supabase")
    def test_process_audio_returns_backend_contract(self, supabase, sarvam_client, translator, groq_provider, opd_generator):
        supabase.storage.from_.return_value.download.return_value = b"audio"
        sarvam_client.return_value.transcribe_batch.return_value = [{"speaker_id": "SPEAKER_00", "start_ms": 0, "end_ms": 1000, "original_text": "Hello"}]
        translator.return_value.side_effect = lambda text: text
        note = MagicMock()
        note.model_dump.return_value = {"chief_complaint": "Fever", "history": "", "examination": "", "assessment": "", "plan": ""}
        opd_generator.return_value.generate.return_value = note
        result = process_audio_module.process_audio("CON-1", "doctor/CON-1/original.wav")
        self.assertEqual(result["segments"][0]["english_text"], "Hello")
        self.assertEqual(result["opd_note"]["chief_complaint"], "Fever")
        supabase.storage.from_.assert_called_once_with("consultation-audio")
        groq_provider.assert_called_once_with()

if __name__ == "__main__":
    unittest.main()
