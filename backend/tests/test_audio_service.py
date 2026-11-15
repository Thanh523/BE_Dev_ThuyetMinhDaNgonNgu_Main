import io
import json
import tempfile
import unittest
import wave
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.error import HTTPError

import aiohttp
from fastapi import HTTPException, UploadFile

from src.config.settings import Settings
from src.services.audio_service import AudioService
from src.services.translation_service import translate_text


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


class FakeGridFSAudioStorage:
    def __init__(self):
        self.files = {}
        self.next_id = 1

    async def upload_file(self, path, filename):
        file_id = f"{self.next_id:024x}"
        self.next_id += 1
        self.files[file_id] = {
            "filename": filename,
            "content": path.read_bytes(),
        }
        return file_id

    async def delete_file(self, file_id):
        self.files.pop(file_id, None)


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
            deepl_api_key="test-translator-key",
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

    async def test_generates_mp3_from_text_and_records_metadata(self):
        async def fake_generate_tts(path, text, voice):
            path.write_bytes(b"placeholder")

        with patch("src.services.audio_service._generate_tts_audio", new=fake_generate_tts), \
             patch("src.services.audio_service._audio_duration", return_value=12):
            audio = await self.service.generate(
                17,
                "vi",
                "Xin chào",
                title="Mở đầu",
                voice_name="vi-VN-HoaiMyNeural",
            )

        self.assertEqual("Mở đầu", audio["Title"])
        self.assertEqual("Xin chào", audio["SourceText"])
        self.assertEqual("vi-VN-HoaiMyNeural", audio["Voice"])
        self.assertEqual(12, audio["DurationSeconds"])
        self.assertIn("/uploads/audio/17-test-place/", audio["FileUrl"])
        self.assertTrue(self.stored_file(audio["FileUrl"]).exists())

    async def test_generates_tts_into_gridfs_without_leaving_local_audio(self):
        storage = FakeGridFSAudioStorage()
        settings = replace(self.settings, audio_storage_backend="gridfs")
        service = AudioService(self.repository, settings, storage)

        async def fake_generate_tts(path, text, voice):
            path.write_bytes(b"generated audio")

        with patch("src.services.audio_service._generate_tts_audio", new=fake_generate_tts), \
             patch("src.services.audio_service._audio_duration", return_value=12):
            audio = await service.generate(
                17,
                "en",
                "Welcome",
                voice_name="en-US-JennyNeural",
            )

        file_id = audio["GridFSFileId"]
        self.assertEqual(f"/api/audio/files/{file_id}", audio["FileUrl"])
        self.assertEqual(b"generated audio", storage.files[file_id]["content"])
        self.assertEqual([], list((self.storage / "17-test-place").iterdir()))

    async def test_gridfs_upload_replace_and_delete_manage_file_lifecycle(self):
        storage = FakeGridFSAudioStorage()
        settings = replace(self.settings, audio_storage_backend="gridfs")
        service = AudioService(self.repository, settings, storage)

        audio = await service.upload(17, "en", self.audio_upload(), "", "")
        old_file_id = audio["GridFSFileId"]
        self.assertIn(old_file_id, storage.files)
        self.assertEqual([], list((self.storage / "17-test-place").iterdir()))

        updated = await service.replace_file(
            audio["AudioId"],
            self.audio_upload("replacement.wav"),
        )
        new_file_id = updated["GridFSFileId"]
        self.assertNotEqual(old_file_id, new_file_id)
        self.assertNotIn(old_file_id, storage.files)
        self.assertIn(new_file_id, storage.files)

        await service.delete(audio["AudioId"])
        self.assertNotIn(new_file_id, storage.files)
        self.assertNotIn(audio["AudioId"], self.repository.documents)

    async def test_edge_tts_rejection_returns_bad_gateway_and_cleans_up(self):
        error = aiohttp.ClientResponseError(
            request_info=MagicMock(),
            history=(),
            status=403,
        )
        fake_edge_tts = MagicMock()
        fake_edge_tts.Communicate.return_value.save = AsyncMock(side_effect=error)

        with patch("src.services.audio_service.edge_tts", fake_edge_tts):
            with self.assertRaises(HTTPException) as raised:
                await self.service.generate(17, "vi", "Xin chào")

        self.assertEqual(502, raised.exception.status_code)
        self.assertEqual(
            "Edge TTS service rejected the request (HTTP 403).",
            raised.exception.detail,
        )
        self.assertEqual({}, self.repository.documents)
        self.assertEqual([], list((self.storage / "17-test-place").iterdir()))

    async def test_translates_source_text_before_generating_audio(self):
        spoken_text = []

        async def fake_generate_tts(path, text, voice):
            spoken_text.append(text)
            path.write_bytes(b"placeholder")

        with patch("src.services.audio_service._generate_tts_audio", new=fake_generate_tts), \
             patch("src.services.audio_service._audio_duration", return_value=8), \
             patch("src.services.audio_service.translate_text", return_value="Hello there") as translate:
            audio = await self.service.generate(
                17,
                "en",
                "Xin chào",
                source_text="Xin chào",
                source_language="vi",
                title="Greeting",
            )

        self.assertEqual("Xin chào", audio["SourceText"])
        self.assertEqual("Hello there", audio["TranslatedText"])
        self.assertEqual(["Hello there"], spoken_text)
        translate.assert_called_once_with(
            "Xin chào",
            "en",
            "vi",
            "test-translator-key",
        )

    async def test_translates_with_deepl_and_maps_simplified_chinese_code(self):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps(
            {"translations": [{"text": "你好"}]},
        ).encode("utf-8")

        with patch("src.services.translation_service.urlopen", return_value=response) as urlopen_mock:
            translated = translate_text(
                "Xin chào",
                "zh-CN",
                "vi",
                "test-translator-key:fx",
            )

        self.assertEqual("你好", translated)
        request = urlopen_mock.call_args.args[0]
        self.assertEqual(
            "https://api-free.deepl.com/v2/translate",
            request.full_url,
        )
        self.assertEqual(
            "DeepL-Auth-Key test-translator-key:fx",
            request.get_header("Authorization"),
        )
        self.assertEqual(
            {"text": ["Xin chào"], "target_lang": "ZH-HANS", "source_lang": "VI"},
            json.loads(request.data.decode("utf-8")),
        )

    async def test_deepl_translation_requires_api_key(self):
        with self.assertRaises(HTTPException) as raised:
            translate_text("Xin chào", "en", "vi", None)

        self.assertEqual(503, raised.exception.status_code)

    async def test_deepl_pro_key_uses_pro_endpoint(self):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps(
            {"translations": [{"text": "Hello"}]},
        ).encode("utf-8")

        with patch("src.services.translation_service.urlopen", return_value=response) as urlopen_mock:
            translated = translate_text(
                "Xin chào",
                "en",
                "vi",
                "test-pro-key",
            )

        self.assertEqual("Hello", translated)
        self.assertEqual(
            "https://api.deepl.com/v2/translate",
            urlopen_mock.call_args.args[0].full_url,
        )

    async def test_retries_deepl_rate_limit_before_returning_translation(self):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps(
            {"translations": [{"text": "Hello"}]},
        ).encode("utf-8")
        rate_limit = HTTPError(
            "https://api.deepl.com/v2/translate",
            429,
            "Too Many Requests",
            None,
            None,
        )
        self.addCleanup(rate_limit.close)

        with patch(
            "src.services.translation_service.urlopen",
            side_effect=[rate_limit, response],
        ) as urlopen_mock, patch("src.services.translation_service.time.sleep") as sleep_mock:
            translated = translate_text(
                "Xin chào",
                "en",
                "vi",
                "test-pro-key",
            )

        self.assertEqual("Hello", translated)
        self.assertEqual(2, urlopen_mock.call_count)
        sleep_mock.assert_called_once_with(0.5)

    async def test_validates_place_before_translating_text(self):
        self.repository.exists = False

        with patch("src.services.audio_service.translate_text") as translate:
            with self.assertRaises(HTTPException) as raised:
                await self.service.generate(
                    17,
                    "en",
                    "Xin chào",
                    source_language="vi",
                )

        self.assertEqual(404, raised.exception.status_code)
        translate.assert_not_called()

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

    async def test_metadata_update_skips_audio_lookup_without_language_change(self):
        audio = await self.service.upload(17, "en", self.audio_upload(), "", "")
        get_audio = self.repository.get

        with patch.object(
            self.repository,
            "get",
            new_callable=AsyncMock,
            side_effect=get_audio,
        ) as get_mock:
            updated = await self.service.update(
                audio["AudioId"],
                {"title": "Updated guide"},
            )

        self.assertEqual("Updated guide", updated["Title"])
        get_mock.assert_not_awaited()

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
