from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field

from src.config.database import get_database
from src.config.settings import get_settings
from src.middlewares.admin_auth import require_admin
from src.repositories.admin_activity_repository import AdminActivityRepository
from src.services.admin_activity_service import AdminActivityService


router = APIRouter(
    prefix="/api/admin",
    tags=["Admin activity"],
    dependencies=[Depends(require_admin)],
)


class AdminActivityView(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    log_id: str = Field(alias="LogId")
    admin_id: str = Field(alias="AdminId")
    action: str = Field(alias="Action")
    entity_name: str = Field(alias="EntityName")
    entity_id: str = Field(alias="EntityId")
    description: str = Field(alias="Description")
    created_at: datetime = Field(alias="CreatedAt")


@router.get(
    "/activity-logs",
    response_model=list[AdminActivityView],
    response_model_by_alias=False,
)
async def list_admin_activity(
    limit: int = Query(default=50, ge=1, le=200),
    database=Depends(get_database),
) -> list[dict]:
    settings = get_settings()
    service = AdminActivityService(
        AdminActivityRepository(
            database,
            settings.admin_activity_logs_collection,
        ),
    )
    return await service.list_latest(limit)
