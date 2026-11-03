from typing import Any


class AdminActivityRepository:
    def __init__(self, database: Any, collection_name: str):
        self.logs = database[collection_name]

    async def create(self, document: dict) -> None:
        await self.logs.insert_one(document)

    async def list_latest(self, limit: int) -> list[dict]:
        cursor = (
            self.logs.find({}, {"_id": 0})
            .sort("CreatedAt", -1)
            .limit(limit)
        )
        return await cursor.to_list(length=limit)

    async def ensure_indexes(self) -> None:
        await self.logs.create_index("LogId", unique=True)
        await self.logs.create_index([("AdminId", 1), ("CreatedAt", 1)])
