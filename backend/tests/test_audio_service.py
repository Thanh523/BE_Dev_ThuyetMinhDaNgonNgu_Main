import io
import tempfile
import unittest
import wave
from copy import deepcopy
from pathlib import Path

from fastapi import HTTPException, UploadFile

from src.config.settings import Settings
from src.services.audio_service import AudioService


class FakeRepository:
    def __init__(self):
        self.documents: dict[str, dict] = {}
        self.exists = True

    async def place_exists(self, place_id):
        return self.exists

    async def get_place(self, place_id):
        if not self.exists:
            return None
        return {
            "PlaceId": place_id,
            "PlaceName": "Test Place",
            "Slug": "test-place",
        }

    async def language_exists(self, place_id, language, exclude_audio_id=None):
        return any(
            audio_id != exclude_audio_id
            and document["PlaceId"] == place_id
            and document["Language"] == language
            for audio_id, document in self.documents.items()
        )

    async def list_for_place(self, place_id):
        return [
            document
            for document in self.documents.values()
            if document["PlaceId"] == place_id
        ]

    async def insert(self, document):
        self.documents[document["AudioId"]] = deepcopy(document)
        return deepcopy(document)

    async def get(self, audio_id):
        document = self.documents.get(audio_id)
        return deepcopy(document) if document is not None else None

    async def update(self, audio_id, changes):
        document = self.documents.get(audio_id)
        if document is None:
            return None
        document.update(changes)
        return deepcopy(document)

    async def delete(self, audio_id):
        document = self.documents.pop(audio_id, None)
        return deepcopy(document) if document is not None else None


def wav_bytes() -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(8000)
        audio.writeframes(b"\0\0" * 8000)
    return output.getvalue()


class AudioServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.storage = Path(self.temporary_directory.name) / "audio"
        self.repository = FakeRepository()
        self.settings = Settings(
            mongodb_uri="mongodb://localhost:27017",
            mongodb_database="test",
            places_collection="Places",
            place_images_collection="PlaceImages",
            jwt_key="test-key",
            jwt_algorithm="HS256",
            jwt_role_claim="role",
            jwt_issuer=None,
            jwt_audience=None,
            cors_origins=[],
            image_storage_dir=Path(self.temporary_directory.name) / "images",
            audio_storage_dir=self.storage,
        )
        self.service = AudioService(self.repository, self.settings)

    async def asyncTearDown(self):
        self.temporary_directory.cleanup()

    def audio_upload(self, filename="guide.wav", content=None):
        return UploadFile(
            filename=filename,
            file=io.BytesIO(wav_bytes() if content is None else content),
        )

    def stored_file(self, file_url):
        return self.storage / file_url.removeprefix("/uploads/audio/")

    async def test_uploads_valid_audio_with_duration_and_metadata(self):
        audio = await self.service.upload(
            17,
            "en",
            self.audio_upload(),
            "  City guide  ",
            "  Sample voice  ",
        )

        self.assertEqual("City guide", audio["Title"])
        self.assertEqual("Sample voice", audio["VoiceName"])
        self.assertEqual(1, audio["DurationSeconds"])
        self.assertIn("/uploads/audio/17-test-place/", audio["FileUrl"])
        self.assertTrue(self.stored_file(audio["FileUrl"]).is_file())
        self.assertEqual(audio, self.repository.documents[audio["AudioId"]])

    async def test_rejects_unsupported_extensions_and_invalid_audio_content(self):
        with self.assertRaises(HTTPException) as raised:
            await self.service.upload(
                17, "en", self.audio_upload("guide.exe"), "", ""
            )
        self.assertEqual(415, raised.exception.status_code)

        with self.assertRaises(HTTPException) as raised:
            await self.service.upload(
                17, "en", self.audio_upload(content=b"not an audio file"), "", ""
            )
        self.assertEqual(415, raised.exception.status_code)
        self.assertEqual([], list((self.storage / "17-test-place").iterdir()))
        self.assertEqual({}, self.repository.documents)

    async def test_rejects_uploads_over_configured_limit_and_cleans_up(self):
        self.settings = Settings(
            mongodb_uri="mongodb://localhost:27017",
            mongodb_database="test",
            places_collection="Places",
            place_images_collection="PlaceImages",
            jwt_key="test-key",
            jwt_algorithm="HS256",
            jwt_role_claim="role",
            jwt_issuer=None,
            jwt_audience=None,
            cors_origins=[],
            image_storage_dir=Path(self.temporary_directory.name) / "images",
            audio_storage_dir=self.storage,
            max_audio_size_bytes=8,
        )
        self.service = AudioService(self.repository, self.settings)

        with self.assertRaises(HTTPException) as raised:
            await self.service.upload(
                17, "en", self.audio_upload(content=b"123456789"), "", ""
            )

        self.assertEqual(413, raised.exception.status_code)
        self.assertEqual([], list((self.storage / "17-test-place").iterdir()))

    async def test_replaces_audio_file_and_removes_previous_file(self):
        audio = await self.service.upload(17, "en", self.audio_upload(), "", "")
        old_file_url = audio["FileUrl"]
        old_path = self.stored_file(old_file_url)

        updated = await self.service.replace_file(
            audio["AudioId"],
            self.audio_upload("replacement.wav"),
        )

        new_path = self.stored_file(updated["FileUrl"])
        self.assertNotEqual(old_file_url, updated["FileUrl"])
        self.assertFalse(old_path.exists())
        self.assertTrue(new_path.is_file())
        self.assertEqual(1, updated["DurationSeconds"])

    async def test_updates_metadata_and_rejects_duplicate_place_language(self):
        audio = await self.service.upload(17, "en", self.audio_upload(), "", "")
        await self.service.upload(17, "vi", self.audio_upload(), "", "")

        updated = await self.service.update(
            audio["AudioId"],
            {
                "title": " Updated guide ",
                "language": "fr",
                "voice_name": " French voice ",
                "is_active": False,
            },
        )
        self.assertEqual("Updated guide", updated["Title"])
        self.assertEqual("fr", updated["Language"])
        self.assertEqual("French voice", updated["VoiceName"])
        self.assertFalse(updated["IsActive"])

        with self.assertRaises(HTTPException) as raised:
            await self.service.update(audio["AudioId"], {"language": "vi"})
        self.assertEqual(409, raised.exception.status_code)

    async def test_deletes_audio_metadata_and_file(self):
        audio = await self.service.upload(17, "en", self.audio_upload(), "", "")
        stored_path = self.stored_file(audio["FileUrl"])

        await self.service.delete(audio["AudioId"])

        self.assertFalse(stored_path.exists())
        self.assertNotIn(audio["AudioId"], self.repository.documents)

    async def test_rejects_upload_for_missing_place(self):
        self.repository.exists = False

        with self.assertRaises(HTTPException) as raised:
            await self.service.upload(17, "en", self.audio_upload(), "", "")

        self.assertEqual(404, raised.exception.status_code)
        self.assertEqual([], list(self.storage.iterdir()))


if __name__ == "__main__":
    unittest.main()
