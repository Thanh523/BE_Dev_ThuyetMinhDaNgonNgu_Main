import re
from typing import Any

from pymongo import ReturnDocument

from src.config.settings import Settings
from src.repositories.id_repository import next_integer_id


class PlaceRepository:
    def __init__(self, database: Any, settings: Settings):
        self.database = database
        self.settings = settings
        self.places = database[settings.places_collection]
        self.images = database[settings.place_images_collection]

    async def list(
        self,
        search: str,
        category_id: int | None,
        visibility: str,
        skip: int,
        limit: int,
    ) -> tuple[list[dict], int]:
        query: dict = {}
        if search.strip():
            pattern = re.escape(search.strip())
            query["$or"] = [
                {"PlaceName": {"$regex": pattern, "$options": "i"}},
                {"Slug": {"$regex": pattern, "$options": "i"}},
                {"Address": {"$regex": pattern, "$options": "i"}},
            ]
        if category_id is not None:
            query["CategoryId"] = category_id
        if visibility == "visible":
            query["$and"] = [
                {
                    "$or": [
                        {"IsVisible": True},
                        {"IsVisible": {"$exists": False}},
                    ]
                }
            ]
        elif visibility == "hidden":
            query["IsVisible"] = False

        total = await self.places.count_documents(query)
        cursor = (
            self.places.find(query, {"_id": 0})
            .sort([("PlaceName", 1), ("PlaceId", 1)])
            .skip(skip)
            .limit(limit)
        )
        return await cursor.to_list(length=limit), total

    async def get(self, place_id: int) -> dict | None:
        return await self.places.find_one({"PlaceId": place_id}, {"_id": 0})

    async def category_exists(self, category_id: int) -> bool:
        return await self.database[self.settings.categories_collection].find_one(
            {"CategoryId": category_id},
            {"_id": 1},
        ) is not None

    async def slug_exists(self, slug: str, exclude_place_id: int | None = None) -> bool:
        query = {"Slug": slug}
        if exclude_place_id is not None:
            query["PlaceId"] = {"$ne": exclude_place_id}
        return await self.places.find_one(query, {"_id": 1}) is not None

    async def create(self, fields: dict) -> dict:
        place_id = await next_integer_id(
            self.database,
            self.settings,
            "places",
            self.settings.places_collection,
            "PlaceId",
        )
        document = {"PlaceId": place_id, **fields}
        await self.places.insert_one(document)
        return {key: value for key, value in document.items() if key != "_id"}

    async def update(self, place_id: int, changes: dict) -> dict | None:
        return await self.places.find_one_and_update(
            {"PlaceId": place_id},
            {"$set": changes},
            return_document=ReturnDocument.AFTER,
            projection={"_id": 0},
        )

    async def set_visibility(self, place_id: int, is_visible: bool) -> dict | None:
        return await self.places.find_one_and_update(
            {"PlaceId": place_id},
            {"$set": {"IsVisible": is_visible}},
            return_document=ReturnDocument.AFTER,
            projection={"_id": 0},
        )

    async def has_images(self, place_id: int) -> bool:
        return await self.images.find_one({"PlaceId": place_id}, {"_id": 1}) is not None

    async def delete(self, place_id: int) -> bool:
        result = await self.places.delete_one({"PlaceId": place_id})
        return result.deleted_count == 1
