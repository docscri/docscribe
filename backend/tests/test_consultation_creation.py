import asyncio
import os
import unittest
from io import BytesIO
from unittest.mock import MagicMock, patch

os.environ.setdefault("SUPABASE_URL", "http://localhost:54321")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-key")

from fastapi import BackgroundTasks, HTTPException, UploadFile

from app.api import consultations


class ConsultationCreationTests(unittest.TestCase):
    @patch.object(consultations, "supabase")
    def test_successful_creation_schedules_model_processing(self, supabase):
        supabase.storage.from_.return_value.upload.return_value = None
        supabase.table.return_value.insert.return_value.execute.return_value = None
        background_tasks = BackgroundTasks()
        audio = UploadFile(filename="visit.wav", file=BytesIO(b"RIFF\x00\x00\x00\x00WAVEaudio-data"))
        result = asyncio.run(consultations.create_consultation(background_tasks, audio, " Patient ", " PT-1 ", "doctor-1"))
        self.assertEqual(result["status"], "processing")
        self.assertEqual(len(background_tasks.tasks), 1)
        task = background_tasks.tasks[0]
        self.assertIs(task.func, consultations.run_model_processing)
        self.assertEqual(task.args[0], result["consultationId"])
        self.assertEqual(task.args[1], f"doctor-1/{result['consultationId']}/original.wav")
        inserted = supabase.table.return_value.insert.call_args.args[0]
        self.assertEqual(inserted["patient_name"], "Patient")
        self.assertEqual(inserted["patient_id"], "PT-1")

    @patch.object(consultations, "supabase")
    def test_mismatched_audio_content_is_rejected_before_upload(self, supabase):
        audio = UploadFile(filename="visit.wav", file=BytesIO(b"not-a-wave-file"))
        with self.assertRaises(HTTPException) as raised:
            asyncio.run(consultations.create_consultation(BackgroundTasks(), audio, "", "", "doctor-1"))
        self.assertEqual(raised.exception.status_code, 400)
        self.assertEqual(raised.exception.detail, "Audio content does not match the file format")
        supabase.storage.from_.assert_not_called()


if __name__ == "__main__":
    unittest.main()
