from datetime import datetime, timezone
from typing import Any

from pymongo import ReturnDocument


class PlaceAudioRepository:
    def __init__(
        self,
        database: Any,
        places_collection: str,
        audios_collection: str,
        narrations_collection: str = "Narrations",
    ):
        self.places = database[places_collection]
        self.audios = database[audios_collection]
        self.narrations = database[narrations_collection]

    async def place_exists(self, place_id: int | str) -> bool:
        return await self.places.find_one({"PlaceId": place_id}, {"_id": 1}) is not None

    async def get_place(self, place_id: int | str) -> dict | None:
        return await self.places.find_one(
            {"PlaceId": place_id},
            {"_id": 0, "PlaceId": 1, "PlaceName": 1, "Slug": 1},
        )

    async def list_for_place(self, place_id: int | str) -> list[dict]:
        cursor = self.audios.find({"PlaceId": place_id}).sort(
            [("Language", 1), ("CreatedAt", 1)]
        )
        return await cursor.to_list(length=None)

    async def language_exists(
        self,
        place_id: int | str,
        language: str,
        exclude_audio_id: str | None = None,
    ) -> bool:
        query: dict = {"PlaceId": place_id, "Language": language}
        if exclude_audio_id is not None:
            query["AudioId"] = {"$ne": exclude_audio_id}
        return await self.audios.find_one(query, {"_id": 1}) is not None

    async def insert(self, document: dict) -> dict:
        await self.audios.insert_one(document)
        return document

    async def get(self, audio_id: str) -> dict | None:
        return await self.audios.find_one({"AudioId": audio_id})

    async def update(self, audio_id: str, changes: dict) -> dict | None:
        return await self.audios.find_one_and_update(
            {"AudioId": audio_id},
            {
                "$set": {
                    **changes,
                    "UpdatedAt": datetime.now(timezone.utc),
                }
            },
            return_document=ReturnDocument.AFTER,
        )

    async def get_narration(self, narration_id: int) -> dict | None:
        return await self.narrations.find_one(
            {"NarrationId": narration_id},
            {"_id": 0, "NarrationId": 1, "PlaceId": 1, "LanguageCode": 1},
        )

    async def has_narration_audio(self, narration_id: int, exclude_audio_id: str) -> bool:
        return await self.audios.find_one(
            {
                "NarrationId": narration_id,
                "AudioId": {"$ne": exclude_audio_id},
            },
            {"_id": 1},
        ) is not None

    async def link_narration(
        self,
        audio_id: str,
        narration_id: int | None,
    ) -> dict | None:
        changes = {"NarrationId": narration_id} if narration_id is not None else {}
        if narration_id is None:
            return await self.audios.find_one_and_update(
                {"AudioId": audio_id},
                {"$unset": {"NarrationId": ""}},
                return_document=ReturnDocument.AFTER,
            )
        return await self.audios.find_one_and_update(
            {"AudioId": audio_id},
            {"$set": changes},
            return_document=ReturnDocument.AFTER,
        )

    async def delete(self, audio_id: str) -> dict | None:
        return await self.audios.find_one_and_delete({"AudioId": audio_id})

    async def ensure_indexes(self) -> None:
        await self.audios.create_index("AudioId", unique=True)
        await self.audios.create_index(
            [("PlaceId", 1), ("Language", 1)],
            unique=True,
        )
