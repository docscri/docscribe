import os
import sys
import types
import unittest
from unittest.mock import patch

os.environ.setdefault("SUPABASE_URL", "http://localhost:54321")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-key")

from app.services import model_runner
from app.services.processing import ModelProcessingResult, save_processing_result


VALID_RESULT = {
    "segments": [{"speaker_id": "SPEAKER_00", "speaker_role": "doctor", "start_ms": 0, "end_ms": 1000, "original_text": "Hello", "english_text": None}],
    "opd_note": {"chief_complaint": "Fever", "history": "", "examination": "", "assessment": "", "plan": ""},
}


class Query:
    def __init__(self, log, table):
        self.log, self.table_name = log, table

    def _record(self, action, value=None, **kwargs):
        self.log.append((self.table_name, action, value, kwargs))
        return self

    def delete(self): return self._record("delete")
    def insert(self, value): return self._record("insert", value)
    def upsert(self, value, **kwargs): return self._record("upsert", value, **kwargs)
    def update(self, value): return self._record("update", value)
    def eq(self, key, value): return self._record("eq", (key, value))
    def execute(self): return self._record("execute")


class Client:
    def __init__(self): self.log = []
    def table(self, name): return Query(self.log, name)


class InsertFailingQuery(Query):
    def insert(self, value):
        if self.table_name == "transcript_segments":
            raise RuntimeError("database unavailable")
        return super().insert(value)


class InsertFailingClient(Client):
    def table(self, name): return InsertFailingQuery(self.log, name)


class ProcessingTests(unittest.TestCase):
    def test_valid_result_is_saved_and_marked_ready(self):
        client = Client()
        save_processing_result("CON-1", ModelProcessingResult.model_validate(VALID_RESULT), client)
        self.assertTrue(any(table == "transcript_segments" and action == "insert" for table, action, _, _ in client.log))
        self.assertIn(("consultations", "update", {"status": "ready_for_review", "error": None}, {}), client.log)

    def test_invalid_model_result_is_rejected(self):
        invalid = {**VALID_RESULT, "segments": [{**VALID_RESULT["segments"][0], "end_ms": -1}]}
        with self.assertRaises(ValueError):
            ModelProcessingResult.model_validate(invalid)

    def test_save_failure_marks_consultation_failed(self):
        client = InsertFailingClient()
        with self.assertRaises(RuntimeError), patch("app.services.processing.logger.exception"):
            save_processing_result("CON-1", ModelProcessingResult.model_validate(VALID_RESULT), client)
        self.assertIn(("consultations", "update", {"status": "failed", "error": "Could not save the processing result"}, {}), client.log)

    def test_runner_accepts_model_return(self):
        module = types.ModuleType("app.model.process_audio")
        module.process_audio = lambda consultation_id, audio_path: VALID_RESULT
        with patch.dict(sys.modules, {"app.model.process_audio": module}), patch.object(model_runner, "save_processing_result") as save, patch.object(model_runner, "mark_processing_failed") as fail, patch.object(model_runner.logger, "exception"):
            model_runner.run_model_processing("CON-1", "doctor/CON-1/original.mp3")
        save.assert_called_once()
        fail.assert_not_called()

    def test_runner_marks_invalid_return_failed(self):
        module = types.ModuleType("app.model.process_audio")
        module.process_audio = lambda consultation_id, audio_path: {"bad": "result"}
        with patch.dict(sys.modules, {"app.model.process_audio": module}), patch.object(model_runner, "save_processing_result") as save, patch.object(model_runner, "mark_processing_failed") as fail, patch.object(model_runner.logger, "exception"):
            model_runner.run_model_processing("CON-1", "doctor/CON-1/original.mp3")
        save.assert_not_called()
        fail.assert_called_once_with("CON-1")


if __name__ == "__main__":
    unittest.main()
