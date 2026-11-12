from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError, PyMongoError

from src.repositories.narration_repository import NarrationRepository


class NarrationService:
    def __init__(self, repository: NarrationRepository):
        self.repository = repository

    async def list_for_place(self, place_id: int) -> list[dict]:
        try:
            if not await self.repository.place_exists(place_id):
                raise HTTPException(status_code=404, detail="Place was not found.")
            return await self.repository.list_for_place(place_id)
        except PyMongoError as error:
            raise HTTPException(
                status_code=503,
                detail="Narration list is temporarily unavailable.",
            ) from error

    async def create(
        self,
        place_id: int,
        language_code: str,
        title: str,
        content: str,
    ) -> dict:
        language = language_code.strip()
        title = title.strip()
        content = content.strip()
        if not language:
            raise HTTPException(status_code=422, detail="Language code is required.")
        if not title:
            raise HTTPException(status_code=422, detail="Title is required.")
        if not content:
            raise HTTPException(status_code=422, detail="Content is required.")
        try:
            if not await self.repository.place_exists(place_id):
                raise HTTPException(status_code=404, detail="Place was not found.")
            if await self.repository.language_exists(place_id, language):
                raise HTTPException(
                    status_code=409,
                    detail="This place already has a narration for the selected language.",
                )
            return await self.repository.create(
                {
                    "PlaceId": place_id,
                    "LanguageCode": language,
                    "Title": title,
                    "Content": content,
                }
            )
        except DuplicateKeyError as error:
            raise HTTPException(status_code=409, detail="Narration already exists.") from error
        except PyMongoError as error:
            raise HTTPException(status_code=503, detail="Narration could not be saved.") from error

    async def update(self, narration_id: int, changes: dict) -> dict:
        mapped: dict = {}
        for field, database_field in (
            ("language_code", "LanguageCode"),
            ("title", "Title"),
            ("content", "Content"),
        ):
            if field in changes and changes[field] is not None:
                value = changes[field].strip()
                if not value:
                    raise HTTPException(status_code=422, detail=f"{database_field} is required.")
                mapped[database_field] = value
        if not mapped:
            raise HTTPException(status_code=422, detail="No narration fields were provided.")
        try:
            narration = await self.repository.get(narration_id)
            if narration is None:
                raise HTTPException(status_code=404, detail="Narration was not found.")
            language = mapped.get("LanguageCode")
            if language and await self.repository.language_exists(
                narration["PlaceId"],
                language,
                narration_id,
            ):
                raise HTTPException(status_code=409, detail="Narration already exists.")
            result = await self.repository.update(narration_id, mapped)
        except DuplicateKeyError as error:
            raise HTTPException(status_code=409, detail="Narration already exists.") from error
        except PyMongoError as error:
            raise HTTPException(status_code=503, detail="Narration could not be updated.") from error
        if result is None:
            raise HTTPException(status_code=404, detail="Narration was not found.")
        return result

    async def delete(self, narration_id: int) -> None:
        try:
            if await self.repository.get(narration_id) is None:
                raise HTTPException(status_code=404, detail="Narration was not found.")
            if await self.repository.has_audio_files(narration_id):
                raise HTTPException(
                    status_code=409,
                    detail="Narration cannot be deleted while audio files reference it.",
                )
            if not await self.repository.delete(narration_id):
                raise HTTPException(status_code=404, detail="Narration was not found.")
        except PyMongoError as error:
            raise HTTPException(status_code=503, detail="Narration could not be deleted.") from error
