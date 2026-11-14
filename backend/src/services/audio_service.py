import asyncio
import math
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException, UploadFile
from mutagen import File as MutagenFile
from mutagen import MutagenError
from pymongo.errors import DuplicateKeyError, PyMongoError

from src.config.settings import Settings
from src.repositories.place_audio_repository import PlaceAudioRepository


AUDIO_URL_PREFIX = "/uploads/audio/"
SAFE_PLACE_SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
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
SUPPORTED_AUDIO_EXTENSIONS = {".mp3", ".wav", ".ogg", ".oga", ".m4a", ".flac"}
UPLOAD_CHUNK_SIZE = 1024 * 1024


def _place_audio_folder_name(place_id: int | str, slug: str) -> str:
    place_id_value = str(place_id)
    if not place_id_value.isdecimal() or SAFE_PLACE_SLUG.fullmatch(slug) is None:
        raise ValueError("Place ID or slug is invalid for audio storage.")
    return f"{place_id_value}-{slug}"


def _remove_file(path: Path) -> None:
    path.unlink(missing_ok=True)


def _audio_duration(path: Path) -> int:
    try:
        audio = MutagenFile(str(path))
    except (OSError, MutagenError, ValueError) as error:
        raise HTTPException(
            status_code=415,
            detail="The selected file is not a supported audio format.",
        ) from error
    if audio is None or audio.info is None:
        raise HTTPException(
            status_code=415,
            detail="The selected file is not a supported audio format.",
        )
    duration = audio.info.length
    if not math.isfinite(duration) or duration <= 0:
        raise HTTPException(
            status_code=415,
            detail="The audio file has no valid duration.",
        )
    return max(1, round(duration))


def _stored_file_path(storage_dir: Path, file_url: str) -> Path:
    if not file_url.startswith(AUDIO_URL_PREFIX):
        raise HTTPException(
            status_code=500,
            detail="Stored audio path is invalid.",
        )

    relative_url = file_url.removeprefix(AUDIO_URL_PREFIX)
    if "\\" in relative_url or not relative_url:
        raise HTTPException(
            status_code=500,
            detail="Stored audio path is invalid.",
        )

    path = (storage_dir / relative_url).resolve()
    try:
        path.relative_to(storage_dir.resolve())
    except ValueError as error:
        raise HTTPException(
            status_code=500,
            detail="Stored audio path is invalid.",
        ) from error
    return path


class AudioService:
    def __init__(self, repository: PlaceAudioRepository, settings: Settings):
        self.repository = repository
        self.settings = settings
        self.settings.audio_storage_dir.mkdir(parents=True, exist_ok=True)

    async def list_for_place(self, place_id: int | str) -> list[dict]:
        try:
            if not await self.repository.place_exists(place_id):
                raise HTTPException(status_code=404, detail="Place was not found.")
            return await self.repository.list_for_place(place_id)
        except PyMongoError as error:
            raise HTTPException(
                status_code=503,
                detail="Audio list is temporarily unavailable.",
            ) from error

    async def upload(
        self,
        place_id: int | str,
        language: str,
        upload: UploadFile,
        title: str,
        voice_name: str,
    ) -> dict:
        language = language.strip()
        title = title.strip()
        voice_name = voice_name.strip() or VOICES.get(language, "")
        if language not in LANGUAGE_NAMES:
            raise HTTPException(status_code=422, detail="Unsupported audio language.")
        if len(title) > 200:
            raise HTTPException(status_code=422, detail="Title is too long.")
        if len(voice_name) > 100:
            raise HTTPException(status_code=422, detail="Voice name is too long.")
        place = await self._validate_place_and_language(place_id, language)

        extension = Path(upload.filename or "").suffix.lower()
        if extension not in SUPPORTED_AUDIO_EXTENSIONS:
            raise HTTPException(
                status_code=415,
                detail="Use an MP3, WAV, OGG, M4A, or FLAC audio file.",
            )
        audio_id = uuid.uuid4().hex
        staging_path = self.settings.audio_storage_dir / f".{audio_id}.upload"
        audio_directory = await self._place_audio_directory(place)
        final_path = audio_directory / f"{audio_id}{extension}"
        try:
            size = await self._save_upload(upload, staging_path)
            if size == 0:
                raise HTTPException(status_code=422, detail="The audio file is empty.")
            duration_seconds = await asyncio.to_thread(_audio_duration, staging_path)
            await asyncio.to_thread(os.replace, staging_path, final_path)
            now = datetime.now(timezone.utc)
            document = {
                "AudioId": audio_id,
                "PlaceId": place_id,
                "Language": language,
                "Title": title or f"Thuyết minh {LANGUAGE_NAMES[language]}",
                "SourceText": "",
                "TranslatedText": "",
                "FileUrl": f"{AUDIO_URL_PREFIX}{audio_directory.name}/{final_path.name}",
                "Voice": voice_name,
                "VoiceName": voice_name,
                "DurationSeconds": duration_seconds,
                "IsActive": True,
                "CreatedAt": now,
                "UpdatedAt": now,
            }
            await self.repository.insert(document)
            return document
        except DuplicateKeyError as error:
            await self._remove_files(staging_path, final_path)
            raise HTTPException(
                status_code=409,
                detail="Audio already exists for this place and language.",
            ) from error
        except HTTPException:
            await self._remove_files(staging_path, final_path)
            raise
        except PyMongoError as error:
            await self._remove_files(staging_path, final_path)
            raise HTTPException(status_code=503, detail="Audio could not be saved.") from error
        except OSError as error:
            await self._remove_files(staging_path, final_path)
            raise HTTPException(status_code=503, detail="Audio file could not be saved.") from error

    async def _save_upload(self, upload: UploadFile, path: Path) -> int:
        size = 0
        try:
            with path.open("wb") as target:
                while chunk := await upload.read(UPLOAD_CHUNK_SIZE):
                    size += len(chunk)
                    if size > self.settings.max_audio_size_bytes:
                        raise HTTPException(
                            status_code=413,
                            detail=(
                                "Audio file exceeds the "
                                f"{self.settings.max_audio_size_bytes // (1024 * 1024)} MB limit."
                            ),
                        )
                    target.write(chunk)
            return size
        except (OSError, HTTPException):
            await self._remove_files(path)
            raise
        finally:
            await upload.close()

    async def _validate_place_and_language(
        self,
        place_id: int | str,
        language: str,
        exclude_audio_id: str | None = None,
    ) -> dict:
        try:
            place = await self.repository.get_place(place_id)
            if place is None:
                raise HTTPException(status_code=404, detail="Place was not found.")
            if await self.repository.language_exists(
                place_id,
                language,
                exclude_audio_id,
            ):
                raise HTTPException(
                    status_code=409,
                    detail="This place already has audio for the selected language.",
                )
            return place
        except PyMongoError as error:
            raise HTTPException(
                status_code=503,
                detail="Place or audio information is temporarily unavailable.",
            ) from error

    async def _place_audio_directory(self, place: dict) -> Path:
        folder_name = _place_audio_folder_name(
            place["PlaceId"],
            place.get("Slug") or str(place["PlaceId"]),
        )
        audio_directory = self.settings.audio_storage_dir / folder_name
        try:
            await asyncio.to_thread(
                audio_directory.mkdir,
                parents=True,
                exist_ok=True,
            )
        except OSError as error:
            raise HTTPException(
                status_code=503,
                detail="Place audio folder could not be created.",
            ) from error
        return audio_directory

    async def update(self, audio_id: str, changes: dict) -> dict:
        audio = await self._get(audio_id)
        mapped: dict = {}
        if "title" in changes:
            title = changes["title"].strip()
            if not title:
                raise HTTPException(status_code=422, detail="Title is required.")
            mapped["Title"] = title
        if "language" in changes:
            language = changes["language"].strip()
            if language not in LANGUAGE_NAMES:
                raise HTTPException(status_code=422, detail="Unsupported audio language.")
            if language != audio.get("Language"):
                await self._validate_place_and_language(
                    audio["PlaceId"],
                    language,
                    audio_id,
                )
            mapped["Language"] = language
        if "voice_name" in changes:
            voice_name = changes["voice_name"].strip()
            if not voice_name or len(voice_name) > 100:
                raise HTTPException(
                    status_code=422,
                    detail="Voice name must contain 1-100 characters.",
                )
            mapped["VoiceName"] = voice_name
            mapped["Voice"] = voice_name
        if "is_active" in changes:
            mapped["IsActive"] = changes["is_active"]
        if not mapped:
            raise HTTPException(status_code=422, detail="No audio fields were provided.")

        try:
            updated = await self.repository.update(audio_id, mapped)
        except DuplicateKeyError as error:
            raise HTTPException(
                status_code=409,
                detail="Audio already exists for this place and language.",
            ) from error
        except PyMongoError as error:
            raise HTTPException(status_code=503, detail="Audio could not be updated.") from error
        if updated is None:
            raise HTTPException(status_code=404, detail="Audio was not found.")
        return updated

    async def link_narration(self, audio_id: str, narration_id: int | None) -> dict:
        audio = await self._get(audio_id)
        try:
            if narration_id is not None:
                narration = await self.repository.get_narration(narration_id)
                if narration is None:
                    raise HTTPException(status_code=404, detail="Narration was not found.")
                if (
                    narration.get("PlaceId") != audio.get("PlaceId")
                    or narration.get("LanguageCode") != audio.get("Language")
                ):
                    raise HTTPException(
                        status_code=409,
                        detail="Audio and narration must use the same place and language.",
                    )
                if await self.repository.has_narration_audio(narration_id, audio_id):
                    raise HTTPException(
                        status_code=409,
                        detail="This narration already has another audio file.",
                    )
            result = await self.repository.link_narration(audio_id, narration_id)
        except PyMongoError as error:
            raise HTTPException(
                status_code=503,
                detail="Audio narration link could not be updated.",
            ) from error
        if result is None:
            raise HTTPException(status_code=404, detail="Audio was not found.")
        return result

    async def replace_file(self, audio_id: str, upload: UploadFile) -> dict:
        audio = await self._get(audio_id)
        place = await self._get_place(audio["PlaceId"])
        extension = Path(upload.filename or "").suffix.lower()
        if extension not in SUPPORTED_AUDIO_EXTENSIONS:
            raise HTTPException(
                status_code=415,
                detail="Use an MP3, WAV, OGG, M4A, or FLAC audio file.",
            )

        replacement_id = uuid.uuid4().hex
        staging_path = self.settings.audio_storage_dir / f".{replacement_id}.upload"
        audio_directory = await self._place_audio_directory(place)
        final_path = audio_directory / f"{replacement_id}{extension}"
        try:
            size = await self._save_upload(upload, staging_path)
            if size == 0:
                raise HTTPException(status_code=422, detail="The audio file is empty.")
            duration_seconds = await asyncio.to_thread(_audio_duration, staging_path)
            await asyncio.to_thread(os.replace, staging_path, final_path)
            updated = await self.repository.update(
                audio_id,
                {
                    "FileUrl": f"{AUDIO_URL_PREFIX}{audio_directory.name}/{final_path.name}",
                    "DurationSeconds": duration_seconds,
                },
            )
        except HTTPException:
            await self._remove_files(staging_path, final_path)
            raise
        except (PyMongoError, OSError) as error:
            await self._remove_files(staging_path, final_path)
            raise HTTPException(
                status_code=503,
                detail="Audio file could not be replaced.",
            ) from error
        if updated is None:
            await self._remove_files(final_path)
            raise HTTPException(status_code=404, detail="Audio was not found.")

        old_path = _stored_file_path(
            self.settings.audio_storage_dir,
            audio.get("FileUrl", ""),
        )
        try:
            await asyncio.to_thread(_remove_file, old_path)
        except OSError as error:
            raise HTTPException(
                status_code=503,
                detail="Audio was replaced, but the previous file could not be removed.",
            ) from error
        return updated

    async def delete(self, audio_id: str) -> None:
        audio = await self._get(audio_id)
        try:
            deleted = await self.repository.delete(audio_id)
        except PyMongoError as error:
            raise HTTPException(status_code=503, detail="Audio could not be deleted.") from error
        if deleted is None:
            raise HTTPException(status_code=404, detail="Audio was not found.")
        path = _stored_file_path(self.settings.audio_storage_dir, audio.get("FileUrl", ""))
        try:
            await asyncio.to_thread(_remove_file, path)
        except OSError as error:
            raise HTTPException(
                status_code=503,
                detail="Audio metadata was deleted, but its file could not be removed.",
            ) from error

    async def _get(self, audio_id: str) -> dict:
        try:
            audio = await self.repository.get(audio_id)
        except PyMongoError as error:
            raise HTTPException(
                status_code=503,
                detail="Audio information is temporarily unavailable.",
            ) from error
        if audio is None:
            raise HTTPException(status_code=404, detail="Audio was not found.")
        return audio

    async def _get_place(self, place_id: int | str) -> dict:
        try:
            place = await self.repository.get_place(place_id)
        except PyMongoError as error:
            raise HTTPException(
                status_code=503,
                detail="Place information is temporarily unavailable.",
            ) from error
        if place is None:
            raise HTTPException(status_code=404, detail="Place was not found.")
        return place

    async def _remove_files(self, *paths: Path) -> None:
        for path in paths:
            try:
                await asyncio.to_thread(_remove_file, path)
            except OSError as error:
                raise HTTPException(
                    status_code=503,
                    detail="Temporary audio files could not be cleaned up.",
                ) from error
