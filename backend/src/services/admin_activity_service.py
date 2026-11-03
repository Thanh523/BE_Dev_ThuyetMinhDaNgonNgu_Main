from datetime import datetime, timezone
import uuid

from fastapi import HTTPException
from pymongo.errors import PyMongoError

from src.repositories.admin_activity_repository import AdminActivityRepository


class AdminActivityService:
    def __init__(self, repository: AdminActivityRepository):
        self.repository = repository

    async def log(
        self,
        admin_id: str,
        action: str,
        entity_name: str,
        entity_id: str,
        description: str,
    ) -> None:
        await self.repository.create(
            {
                "LogId": uuid.uuid4().hex,
                "AdminId": admin_id,
                "Action": action,
                "EntityName": entity_name,
                "EntityId": entity_id,
                "Description": description,
                "CreatedAt": datetime.now(timezone.utc),
            }
        )

    async def list_latest(self, limit: int) -> list[dict]:
        try:
            return await self.repository.list_latest(limit)
        except PyMongoError as error:
            raise HTTPException(
                status_code=503,
                detail="Admin activity is temporarily unavailable.",
            ) from error
