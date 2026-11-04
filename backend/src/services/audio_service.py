import asyncio
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import edge_tts
from deep_translator import GoogleTranslator
from fastapi import HTTPException, status
from pymongo.errors import DuplicateKeyError, PyMongoError

from src.config.settings import Settings
from src.repositories.place_audio_repository import PlaceAudioRepository


LANGUAGE_NAMES = {
    "vi": "Vietnamese",
    "en": "English",
    "zh-CN": "Chinese (Simplified)",
    "ja": "Japanese",
    "ko": "Korean",
    "fr": "French",
}
VOICES = {
    "vi": "vi-VN-HoaiMyNeural",
    "en": "en-US-JennyNeural",
    "zh-CN": "zh-CN-XiaoxiaoNeural",
    "ja": "ja-JP-NanamiNeural",
    "ko": "ko-KR-SunHiNeural",
    "fr": "fr-FR-DeniseNeural",
}


def _remove_file(path: Path) -> None:
    path.unlink(missing_ok=True)


class AudioService:
    def __init__(self, repository: PlaceAudioRepository, settings: Settings):
        self.repository = repository
        self.settings = settings
        self.settings.audio_storage_dir.mkdir(parents=True, exist_ok=True)

    async def list_for_place(self, place_id: int | str) -> list[dict]:
        if not await self.repository.place_exists(place_id):
            raise HTTPException(status_code=404, detail="Place was not found.")
        return await self.repository.list_for_place(place_id)

    async def create(
        self,
        place_id: int | str,
        source_text: str,
        language: str,
        title: str,
    ) -> dict:
        source_text = source_text.strip()
        language = language.strip()
        title = title.strip()
        if not source_text:
            raise HTTPException(status_code=422, detail="Text is required.")
        if len(source_text) > 10000:
            raise HTTPException(status_code=422, detail="Text must be no longer than 10000 characters.")
        if language not in LANGUAGE_NAMES:
            raise HTTPException(status_code=422, detail="Unsupported audio language.")
        if not await self.repository.place_exists(place_id):
            raise HTTPException(status_code=404, detail="Place was not found.")
        if await self.repository.language_exists(place_id, language):
            raise HTTPException(
                status_code=409,
                detail="This place already has audio for the selected language.",
            )

        try:
            translated_text = source_text
            if language != "vi":
                translated_text = await asyncio.to_thread(
                    GoogleTranslator(source="vi", target=language).translate,
                    source_text,
                )
            audio_id = uuid.uuid4().hex
            filename = f"{audio_id}.mp3"
            audio_path = self.settings.audio_storage_dir / filename
            communicate = edge_tts.Communicate(translated_text, VOICES[language])
            await communicate.save(str(audio_path))
            now = datetime.now(timezone.utc)
            document = {
                "AudioId": audio_id,
                "PlaceId": place_id,
                "Language": language,
                "Title": title or f"Thuyết minh {LANGUAGE_NAMES[language]}",
                "SourceText": source_text,
                "TranslatedText": translated_text,
                "FileUrl": f"/uploads/audio/{filename}",
                "Voice": VOICES[language],
                "CreatedAt": now,
                "UpdatedAt": now,
            }
            await self.repository.insert(document)
            return document
        except DuplicateKeyError as error:
            if "audio_path" in locals():
                await asyncio.to_thread(_remove_file, audio_path)
            raise HTTPException(status_code=409, detail="Audio already exists for this language.") from error
        except (PyMongoError, OSError, edge_tts.exceptions.NoAudioReceived) as error:
            if "audio_path" in locals():
                await asyncio.to_thread(_remove_file, audio_path)
            raise HTTPException(status_code=503, detail="Audio could not be generated or saved.") from error

    async def update(self, audio_id: str, title: str) -> dict:
        audio = await self.repository.get(audio_id)
        if audio is None:
            raise HTTPException(status_code=404, detail="Audio was not found.")
        updated = await self.repository.update(audio_id, {"Title": title.strip()})
        if updated is None:
            raise HTTPException(status_code=404, detail="Audio was not found.")
        return updated

    async def delete(self, audio_id: str) -> None:
        audio = await self.repository.delete(audio_id)
        if audio is None:
            raise HTTPException(status_code=404, detail="Audio was not found.")
        file_url = audio.get("FileUrl", "")
        filename = os.path.basename(file_url)
        path = (self.settings.audio_storage_dir / filename).resolve()
        if path.parent != self.settings.audio_storage_dir.resolve():
            raise HTTPException(status_code=500, detail="Stored audio path is invalid.")
        await asyncio.to_thread(_remove_file, path)
