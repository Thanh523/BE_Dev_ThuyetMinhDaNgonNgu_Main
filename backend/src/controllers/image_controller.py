from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel, ConfigDict, Field
from pymongo.errors import PyMongoError

from src.config.database import get_database
from src.config.settings import get_settings
from src.middlewares.admin_auth import require_admin
from src.repositories.place_image_repository import (
    PlaceImageRepository,
    parse_place_id,
)
from src.services.admin_audit_service import log_admin_activity
from src.services.image_service import ImageService


router = APIRouter(
    prefix="/api/admin",
    tags=["Image management"],
    dependencies=[Depends(require_admin)],
)


class ImageView(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    image_id: str = Field(alias="ImageId")
    place_id: int | str = Field(alias="PlaceId")
    file_url: str = Field(alias="FileUrl")
    sort_order: int = Field(alias="SortOrder")
    caption: str = Field(alias="Caption")
    created_at: datetime = Field(alias="CreatedAt")
    updated_at: datetime = Field(alias="UpdatedAt")


class ImageUpdate(BaseModel):
    caption: str | None = Field(default=None, max_length=1000)
    sort_order: int | None = Field(default=None, ge=1)


def _repository(database) -> PlaceImageRepository:
    settings = get_settings()
    return PlaceImageRepository(
        database,
        settings.places_collection,
        settings.place_images_collection,
    )


def _service(database) -> ImageService:
    return ImageService(_repository(database), get_settings())


async def _record_activity(
    database,
    admin_claims: dict,
    action: str,
    entity_id: str,
    description: str,
) -> None:
    settings = get_settings()
    try:
        await log_admin_activity(
            database,
            settings.admin_activity_logs_collection,
            admin_id=admin_claims["AdminId"],
            action=action,
            entity_name="PlaceImages",
            entity_id=entity_id,
            description=description,
        )
    except PyMongoError as error:
        raise HTTPException(
            status_code=503,
            detail=(
                "The image operation completed, but its activity log could not "
                "be saved. Contact an administrator before retrying."
            ),
        ) from error


@router.get(
    "/places/{place_id}/images",
    response_model=list[ImageView],
    response_model_by_alias=False,
)
async def list_place_images(
    place_id: str,
    database=Depends(get_database),
) -> list[dict]:
    return await _service(database).list_for_place(parse_place_id(place_id))


@router.post(
    "/places/{place_id}/images",
    response_model=list[ImageView],
    response_model_by_alias=False,
    status_code=201,
)
async def upload_place_images(
    place_id: str,
    files: Annotated[list[UploadFile], File(description="JPEG, PNG, or WebP; up to 10 MB each.")],
    captions: Annotated[list[str] | None, Form()] = None,
    sort_orders: Annotated[list[int] | None, Form()] = None,
    database=Depends(get_database),
    admin_claims: dict = Depends(require_admin),
) -> list[dict]:
    images = await _service(database).upload(
        parse_place_id(place_id),
        files,
        captions,
        sort_orders,
    )
    for image in images:
        await _record_activity(
            database,
            admin_claims,
            action="UPLOAD",
            entity_id=image["ImageId"],
            description=f"Uploaded image for place {image['PlaceId']}.",
        )
    return images


@router.patch(
    "/images/{image_id}",
    response_model=ImageView,
    response_model_by_alias=False,
)
async def update_image(
    image_id: str,
    update: ImageUpdate,
    database=Depends(get_database),
    admin_claims: dict = Depends(require_admin),
) -> dict:
    image = await _service(database).update(
        image_id,
        update.caption,
        update.sort_order,
    )
    await _record_activity(
        database,
        admin_claims,
        action="UPDATE",
        entity_id=image_id,
        description="Updated image caption or sort order.",
    )
    return image


@router.delete("/images/{image_id}", status_code=204)
async def delete_image(
    image_id: str,
    database=Depends(get_database),
    admin_claims: dict = Depends(require_admin),
) -> Response:
    await _service(database).delete(image_id)
    await _record_activity(
        database,
        admin_claims,
        action="DELETE",
        entity_id=image_id,
        description="Deleted image and its file.",
    )
    return Response(status_code=204)
