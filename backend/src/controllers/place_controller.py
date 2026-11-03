from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from pymongo.errors import PyMongoError

from src.config.database import get_database
from src.config.settings import get_settings
from src.middlewares.admin_auth import require_admin
from src.repositories.category_repository import CategoryRepository
from src.repositories.place_repository import PlaceRepository
from src.services.admin_audit_service import log_admin_activity
from src.services.place_service import PlaceService


router = APIRouter(
    prefix="/api/admin/places",
    tags=["Place management"],
    dependencies=[Depends(require_admin)],
)


class PlaceCreate(BaseModel):
    category_id: int = Field(gt=0)
    place_name: str = Field(min_length=1, max_length=200)
    slug: str | None = Field(default=None, max_length=200)
    address: str = Field(min_length=1, max_length=1000)


class PlaceUpdate(BaseModel):
    category_id: int | None = Field(default=None, gt=0)
    place_name: str | None = Field(default=None, min_length=1, max_length=200)
    slug: str | None = Field(default=None, min_length=1, max_length=200)
    address: str | None = Field(default=None, min_length=1, max_length=1000)


class VisibilityUpdate(BaseModel):
    is_visible: bool


class PlacePage(BaseModel):
    items: list[dict]
    total: int
    skip: int
    limit: int


def _service(database) -> PlaceService:
    settings = get_settings()
    return PlaceService(
        PlaceRepository(database, settings),
        CategoryRepository(database, settings),
    )


async def _log_place_change(
    database,
    admin_claims: dict,
    action: str,
    place_id: int,
    description: str,
) -> None:
    settings = get_settings()
    try:
        await log_admin_activity(
            database,
            settings.admin_activity_logs_collection,
            admin_id=admin_claims["AdminId"],
            action=action,
            entity_name="Places",
            entity_id=str(place_id),
            description=description,
        )
    except PyMongoError as error:
        raise HTTPException(
            status_code=503,
            detail=(
                "The place operation completed, but its activity log could not "
                "be saved. Contact an administrator before retrying."
            ),
        ) from error


@router.get("", response_model=PlacePage)
async def list_places(
    search: str = Query(default="", max_length=200),
    category_id: int | None = Query(default=None, gt=0),
    visibility: Literal["all", "visible", "hidden"] = "all",
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    database=Depends(get_database),
) -> dict:
    items, total = await _service(database).list_places(
        search,
        category_id,
        visibility,
        skip,
        limit,
    )
    return {"items": items, "total": total, "skip": skip, "limit": limit}


@router.get("/{place_id}")
async def get_place(place_id: int, database=Depends(get_database)) -> dict:
    return await _service(database).get_place(place_id)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_place(
    request: PlaceCreate,
    database=Depends(get_database),
    admin_claims: dict = Depends(require_admin),
) -> dict:
    place = await _service(database).create_place(
        request.category_id,
        request.place_name,
        request.slug,
        request.address,
    )
    await _log_place_change(
        database,
        admin_claims,
        "CREATE",
        place["PlaceId"],
        "Created place.",
    )
    return place


@router.patch("/{place_id}")
async def update_place(
    place_id: int,
    request: PlaceUpdate,
    database=Depends(get_database),
    admin_claims: dict = Depends(require_admin),
) -> dict:
    place = await _service(database).update_place(
        place_id,
        request.model_dump(exclude_unset=True),
    )
    await _log_place_change(
        database,
        admin_claims,
        "UPDATE",
        place_id,
        "Updated place details.",
    )
    return place


@router.patch("/{place_id}/visibility")
async def update_place_visibility(
    place_id: int,
    request: VisibilityUpdate,
    database=Depends(get_database),
    admin_claims: dict = Depends(require_admin),
) -> dict:
    place = await _service(database).set_visibility(place_id, request.is_visible)
    await _log_place_change(
        database,
        admin_claims,
        "SHOW" if request.is_visible else "HIDE",
        place_id,
        "Changed place visibility.",
    )
    return place


@router.delete("/{place_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_place(
    place_id: int,
    database=Depends(get_database),
    admin_claims: dict = Depends(require_admin),
) -> None:
    await _service(database).delete_place(place_id)
    await _log_place_change(
        database,
        admin_claims,
        "DELETE",
        place_id,
        "Deleted place.",
    )
