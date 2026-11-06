from datetime import datetime, timezone
from typing import Any

from pymongo import ReturnDocument


def parse_place_id(place_id: str) -> int | str:
    if place_id.isdecimal():
        return int(place_id)
    return place_id


class PlaceImageRepository:
    def __init__(self, database: Any, places_collection: str, images_collection: str):
        self.places = database[places_collection]
        self.images = database[images_collection]

    async def place_exists(self, place_id: int | str) -> bool:
        return await self.places.find_one({"PlaceId": place_id}, {"_id": 1}) is not None

    async def get_place(self, place_id: int | str) -> dict | None:
        return await self.places.find_one(
            {"PlaceId": place_id},
            {"_id": 0, "PlaceId": 1, "Slug": 1},
        )

    async def list_for_place(self, place_id: int | str) -> list[dict]:
        cursor = self.images.find({"PlaceId": place_id}).sort(
            [("SortOrder", 1), ("CreatedAt", 1), ("ImageId", 1)]
        )
        return await cursor.to_list(length=None)

    async def list_all_with_place_names(self) -> list[dict]:
        cursor = await self.images.aggregate(
            [
                {
                    "$lookup": {
                        "from": self.places.name,
                        "localField": "PlaceId",
                        "foreignField": "PlaceId",
                        "as": "_place",
                    }
                },
                {
                    "$unwind": {
                        "path": "$_place",
                        "preserveNullAndEmptyArrays": True,
                    }
                },
                {
                    "$addFields": {
                        "PlaceName": {
                            "$ifNull": ["$_place.PlaceName", "Địa điểm không tồn tại"]
                        }
                    }
                },
                {
                    "$project": {
                        "_id": 0,
                        "ImageId": 1,
                        "PlaceId": 1,
                        "PlaceName": 1,
                        "FileUrl": 1,
                        "SortOrder": 1,
                        "Caption": 1,
                        "CreatedAt": 1,
                        "UpdatedAt": 1,
                    }
                },
                {
                    "$sort": {
                        "PlaceName": 1,
                        "SortOrder": 1,
                        "CreatedAt": 1,
                        "ImageId": 1,
                    }
                },
            ]
        )
        return await cursor.to_list(length=None)

    async def next_sort_order(self, place_id: int | str) -> int:
        image = await self.images.find_one(
            {"PlaceId": place_id},
            {"SortOrder": 1},
            sort=[("SortOrder", -1)],
        )
        return int(image.get("SortOrder", 0)) + 1 if image else 1

    async def sort_orders_in_use(
        self,
        place_id: int | str,
        sort_orders: list[int],
        exclude_image_id: str | None = None,
    ) -> set[int]:
        query: dict = {
            "PlaceId": place_id,
            "SortOrder": {"$in": sort_orders},
        }
        if exclude_image_id is not None:
            query["ImageId"] = {"$ne": exclude_image_id}
        cursor = self.images.find(query, {"SortOrder": 1})
        documents = await cursor.to_list(length=None)
        return {int(document["SortOrder"]) for document in documents}

    async def insert_many(self, documents: list[dict]) -> None:
        if documents:
            await self.images.insert_many(documents, ordered=True)

    async def delete_by_ids(self, image_ids: list[str]) -> None:
        if image_ids:
            await self.images.delete_many({"ImageId": {"$in": image_ids}})

    async def get(self, image_id: str) -> dict | None:
        return await self.images.find_one({"ImageId": image_id})

    async def update(self, image_id: str, changes: dict) -> dict | None:
        changes["UpdatedAt"] = datetime.now(timezone.utc)
        result = await self.images.find_one_and_update(
            {"ImageId": image_id},
            {"$set": changes},
            return_document=ReturnDocument.AFTER,
        )
        return result

    async def delete(self, image_id: str) -> dict | None:
        return await self.images.find_one_and_delete({"ImageId": image_id})
