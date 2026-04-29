import tempfile
import unittest
from pathlib import Path

from app import transcript_store


class TranscriptStoreTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_dir = transcript_store.TRANSCRIPTS_DIR
        transcript_store.TRANSCRIPTS_DIR = Path(self.temp_dir.name)

    def tearDown(self):
        transcript_store.TRANSCRIPTS_DIR = self.original_dir
        self.temp_dir.cleanup()

    def test_create_and_list_transcript(self):
        created = transcript_store.create_transcript(
            text="Hello world from transcription",
            source_type="manual",
            source_name="manual_note",
            model="small",
            language="en",
            duration_sec=12.345,
        )

        self.assertTrue(created["id"].startswith("tr_"))
        self.assertEqual(created["preview"], "Hello world from transcription")
        self.assertEqual(created["duration_sec"], 12.345)

        items = transcript_store.list_transcripts()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["id"], created["id"])
        self.assertNotIn("text", items[0])

    def test_get_and_update_transcript(self):
        created = transcript_store.create_transcript(
            text="Original text",
            source_type="manual",
        )

        loaded = transcript_store.get_transcript(created["id"])
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["text"], "Original text")

        updated = transcript_store.update_transcript(created["id"], text="Updated content for transcript")
        self.assertIsNotNone(updated)
        self.assertEqual(updated["text"], "Updated content for transcript")
        self.assertIn("Updated", updated["preview"])

    def test_create_rejects_empty_text(self):
        with self.assertRaises(ValueError):
            transcript_store.create_transcript(text="   ")

    def test_delete_transcript(self):
        created = transcript_store.create_transcript(
            text="Delete me",
            source_type="manual",
        )

        deleted = transcript_store.delete_transcript(created["id"])
        self.assertTrue(deleted)
        self.assertIsNone(transcript_store.get_transcript(created["id"]))

        deleted_missing = transcript_store.delete_transcript(created["id"])
        self.assertFalse(deleted_missing)


if __name__ == "__main__":
    unittest.main()
