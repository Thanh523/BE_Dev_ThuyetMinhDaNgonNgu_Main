import re
from typing import Any

from pymongo import ReturnDocument

from src.config.settings import Settings
from src.repositories.id_repository import next_integer_id


class CategoryRepository:
    def __init__(self, database: Any, settings: Settings):
        self.database = database
        self.settings = settings
        self.categories = database[settings.categories_collection]
        self.places = database[settings.places_collection]

    async def list(self) -> list[dict]:
        cursor = self.categories.find({}, {"_id": 0}).sort("CategoryName", 1)
        return await cursor.to_list(length=None)

    async def get(self, category_id: int) -> dict | None:
        return await self.categories.find_one({"CategoryId": category_id}, {"_id": 0})

    async def exists(self, category_id: int) -> bool:
        return await self.categories.find_one(
            {"CategoryId": category_id},
            {"_id": 1},
        ) is not None

    async def exists_by_name(
        self,
        category_name: str,
        exclude_category_id: int | None = None,
    ) -> bool:
        query: dict = {
            "CategoryName": {
                "$regex": f"^{re.escape(category_name)}$",
                "$options": "i",
            }
        }
        if exclude_category_id is not None:
            query["CategoryId"] = {"$ne": exclude_category_id}
        return await self.categories.find_one(query, {"_id": 1}) is not None

    async def create(self, name: str, description: str) -> dict:
        category_id = await next_integer_id(
            self.database,
            self.settings,
            "categories",
            self.settings.categories_collection,
            "CategoryId",
        )
        document = {
            "CategoryId": category_id,
            "CategoryName": name,
            "Description": description,
        }
        await self.categories.insert_one(document)
        return document

    async def update(
        self,
        category_id: int,
        changes: dict,
    ) -> dict | None:
        return await self.categories.find_one_and_update(
            {"CategoryId": category_id},
            {"$set": changes},
            return_document=ReturnDocument.AFTER,
            projection={"_id": 0},
        )

    async def has_places(self, category_id: int) -> bool:
        return await self.places.find_one(
            {"CategoryId": category_id},
            {"_id": 1},
        ) is not None

    async def delete(self, category_id: int) -> bool:
        result = await self.categories.delete_one({"CategoryId": category_id})
        return result.deleted_count == 1
