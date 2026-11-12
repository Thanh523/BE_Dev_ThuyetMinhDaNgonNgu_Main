from typing import Any

from pymongo import ReturnDocument

from src.config.settings import Settings
from src.repositories.id_repository import next_integer_id


class NarrationRepository:
    def __init__(self, database: Any, settings: Settings):
        self.database = database
        self.settings = settings
        self.narrations = database[settings.narrations_collection]
        self.audio_files = database[settings.audio_files_collection]
        self.places = database[settings.places_collection]
        self.languages = database[settings.languages_collection]

    async def list_for_place(self, place_id: int) -> list[dict]:
        cursor = self.narrations.find(
            {"PlaceId": place_id},
            {"_id": 0},
        ).sort([("LanguageCode", 1), ("NarrationId", 1)])
        return await cursor.to_list(length=None)

    async def get(self, narration_id: int) -> dict | None:
        return await self.narrations.find_one(
            {"NarrationId": narration_id},
            {"_id": 0},
        )

    async def place_exists(self, place_id: int) -> bool:
        return await self.places.find_one({"PlaceId": place_id}, {"_id": 1}) is not None

    async def language_exists(self, language_code: str) -> bool:
        return await self.languages.find_one(
            {"LanguageCode": language_code},
            {"_id": 1},
        ) is not None

    async def list_languages(self) -> list[dict]:
        cursor = self.languages.find(
            {},
            {"_id": 0, "LanguageCode": 1, "LanguageName": 1},
        ).sort("LanguageCode", 1)
        return await cursor.to_list(length=None)

    async def narration_language_exists(
        self,
        place_id: int,
        language_code: str,
        exclude_narration_id: int | None = None,
    ) -> bool:
        query: dict = {"PlaceId": place_id, "LanguageCode": language_code}
        if exclude_narration_id is not None:
            query["NarrationId"] = {"$ne": exclude_narration_id}
        return await self.narrations.find_one(query, {"_id": 1}) is not None

    async def create(self, fields: dict) -> dict:
        narration_id = await next_integer_id(
            self.database,
            self.settings,
            "narrations",
            self.settings.narrations_collection,
            "NarrationId",
        )
        document = {"NarrationId": narration_id, **fields}
        await self.narrations.insert_one(document)
        return document

    async def update(self, narration_id: int, changes: dict) -> dict | None:
        return await self.narrations.find_one_and_update(
            {"NarrationId": narration_id},
            {"$set": changes},
            return_document=ReturnDocument.AFTER,
            projection={"_id": 0},
        )

    async def has_audio_files(self, narration_id: int) -> bool:
        return await self.audio_files.find_one(
            {"NarrationId": narration_id},
            {"_id": 1},
        ) is not None

    async def delete(self, narration_id: int) -> bool:
        result = await self.narrations.delete_one({"NarrationId": narration_id})
        return result.deleted_count == 1
