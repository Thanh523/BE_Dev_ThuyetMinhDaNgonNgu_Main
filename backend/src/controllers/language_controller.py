from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, ConfigDict, Field

from src.config.database import get_database
from src.config.settings import get_settings
from src.middlewares.admin_auth import require_admin
from src.repositories.language_repository import LanguageRepository
from src.services.language_service import LanguageService


router = APIRouter(
    prefix="/api/admin/languages",
    tags=["Language management"],
    dependencies=[Depends(require_admin)],
)


class LanguageCreate(BaseModel):
    language_code: str = Field(min_length=1, max_length=10)
    language_name: str = Field(min_length=1, max_length=100)


class LanguageStatus(BaseModel):
    is_active: bool


class LanguageView(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    language_code: str = Field(alias="LanguageCode")
    language_name: str = Field(alias="LanguageName")
    is_active: bool = Field(default=True, alias="IsActive")


def _service(database) -> LanguageService:
    return LanguageService(LanguageRepository(database, get_settings()))


@router.get("", response_model=list[LanguageView])
async def list_languages(
    search: str | None = None,
    database=Depends(get_database),
) -> list[dict]:
    return await _service(database).list_languages(search)


@router.post("", response_model=LanguageView, status_code=status.HTTP_201_CREATED)
async def create_language(
    request: LanguageCreate,
    database=Depends(get_database),
) -> dict:
    return await _service(database).create_language(
        request.language_code,
        request.language_name,
    )


@router.patch("/{language_code}", response_model=LanguageView)
async def update_language(
    language_code: str,
    request: LanguageCreate,
    database=Depends(get_database),
) -> dict:
    return await _service(database).update_language(
        language_code,
        request.language_code,
        request.language_name,
    )


@router.patch("/{language_code}/status", response_model=LanguageView)
async def set_language_status(
    language_code: str,
    request: LanguageStatus,
    database=Depends(get_database),
) -> dict:
    return await _service(database).set_status(language_code, request.is_active)


@router.delete("/{language_code}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_language(
    language_code: str,
    database=Depends(get_database),
) -> Response:
    await _service(database).delete_language(language_code)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
