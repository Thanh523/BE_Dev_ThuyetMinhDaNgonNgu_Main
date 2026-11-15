import re
from typing import Any

from pymongo import ReturnDocument

from src.config.settings import Settings


class LanguageRepository:
    def __init__(self, database: Any, settings: Settings):
        self.languages = database[settings.languages_collection]
        self.narrations = database[settings.narrations_collection]
        self.audios = database[settings.audio_collection]
        self.audio_files = database[settings.audio_files_collection]

    async def list(self, search: str | None = None) -> list[dict]:
        query: dict = {}
        if search and search.strip():
            escaped = re.escape(search.strip())
            query = {
                "$or": [
                    {"LanguageCode": {"$regex": escaped, "$options": "i"}},
                    {"LanguageName": {"$regex": escaped, "$options": "i"}},
                ]
            }
        cursor = self.languages.find(query, {"_id": 0}).sort("LanguageCode", 1)
        return await cursor.to_list(length=None)

    async def get(self, language_code: str) -> dict | None:
        return await self.languages.find_one(
            {"LanguageCode": language_code},
            {"_id": 0},
        )

    async def exists_by_code(self, language_code: str, exclude_code: str | None = None) -> bool:
        if exclude_code is not None and language_code == exclude_code:
            return False
        return await self.languages.find_one(
            {"LanguageCode": language_code},
            {"_id": 1},
        ) is not None

    async def exists_by_name(self, language_name: str, exclude_code: str | None = None) -> bool:
        query: dict = {
            "LanguageName": {
                "$regex": f"^{re.escape(language_name)}$",
                "$options": "i",
            }
        }
        if exclude_code is not None:
            query["LanguageCode"] = {"$ne": exclude_code}
        return await self.languages.find_one(query, {"_id": 1}) is not None

    async def create(self, language_code: str, language_name: str) -> dict:
        document = {
            "LanguageCode": language_code,
            "LanguageName": language_name,
            "IsActive": True,
        }
        await self.languages.insert_one(document)
        return document

    async def update(self, language_code: str, changes: dict) -> dict | None:
        return await self.languages.find_one_and_update(
            {"LanguageCode": language_code},
            {"$set": changes},
            return_document=ReturnDocument.AFTER,
            projection={"_id": 0},
        )

    async def has_references(self, language_code: str) -> bool:
        for collection, field in (
            (self.narrations, "LanguageCode"),
            (self.audios, "Language"),
            (self.audio_files, "LanguageCode"),
        ):
            if await collection.find_one({field: language_code}, {"_id": 1}):
                return True
        return False

    async def delete(self, language_code: str) -> bool:
        result = await self.languages.delete_one({"LanguageCode": language_code})
        return result.deleted_count == 1
