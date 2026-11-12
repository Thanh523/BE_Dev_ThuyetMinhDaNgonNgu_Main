from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, ConfigDict, Field

from src.config.database import get_database
from src.config.settings import get_settings
from src.middlewares.admin_auth import require_admin
from src.repositories.narration_repository import NarrationRepository
from src.services.narration_service import NarrationService


router = APIRouter(
    prefix="/api/admin",
    tags=["Narration management"],
    dependencies=[Depends(require_admin)],
)


class NarrationCreate(BaseModel):
    language_code: str = Field(min_length=2, max_length=10)
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=100000)


class NarrationUpdate(BaseModel):
    language_code: str | None = Field(default=None, min_length=2, max_length=10)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    content: str | None = Field(default=None, min_length=1, max_length=100000)


class NarrationView(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    narration_id: int = Field(alias="NarrationId")
    place_id: int = Field(alias="PlaceId")
    language_code: str = Field(alias="LanguageCode")
    title: str = Field(alias="Title")
    content: str = Field(alias="Content")


def _service(database) -> NarrationService:
    return NarrationService(NarrationRepository(database, get_settings()))


@router.get("/places/{place_id}/narrations", response_model=list[NarrationView])
async def list_narrations(place_id: int, database=Depends(get_database)) -> list[dict]:
    return await _service(database).list_for_place(place_id)


@router.post(
    "/places/{place_id}/narrations",
    response_model=NarrationView,
    status_code=status.HTTP_201_CREATED,
)
async def create_narration(
    place_id: int,
    request: NarrationCreate,
    database=Depends(get_database),
) -> dict:
    return await _service(database).create(
        place_id,
        request.language_code,
        request.title,
        request.content,
    )


@router.patch("/narrations/{narration_id}", response_model=NarrationView)
async def update_narration(
    narration_id: int,
    request: NarrationUpdate,
    database=Depends(get_database),
) -> dict:
    return await _service(database).update(
        narration_id,
        request.model_dump(exclude_unset=True),
    )


@router.delete("/narrations/{narration_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_narration(
    narration_id: int,
    database=Depends(get_database),
) -> Response:
    await _service(database).delete(narration_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
