import unittest

from app.model.sarvam_client import SarvamClient


class SarvamClientTests(unittest.TestCase):
    def test_entries_accepts_diarized_transcript_object(self):
        entries = [{"speaker_id": 0, "transcript": "hello"}]
        payload = {"diarized_transcript": {"entries": entries}}

        self.assertIs(SarvamClient._entries(payload), entries)

    def test_entries_accepts_top_level_segments(self):
        segments = [{"speaker": 0, "text": "hello"}]

        self.assertIs(SarvamClient._entries({"segments": segments}), segments)

    def test_entries_rejects_missing_entries(self):
        with self.assertRaisesRegex(RuntimeError, "did not contain"):
            SarvamClient._entries({"diarized_transcript": {}})


if __name__ == "__main__":
    unittest.main()
