from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from pymongo.errors import PyMongoError

from src.config.database import get_database
from src.config.settings import get_settings
from src.middlewares.admin_auth import require_admin
from src.repositories.category_repository import CategoryRepository
from src.services.admin_audit_service import log_admin_activity
from src.services.category_service import CategoryService


router = APIRouter(
    prefix="/api/admin/categories",
    tags=["Category management"],
    dependencies=[Depends(require_admin)],
)


class CategoryCreate(BaseModel):
    category_name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=1000)


class CategoryView(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    category_id: int = Field(alias="CategoryId")
    category_name: str = Field(alias="CategoryName")
    description: str = Field(default="", alias="Description")


def _service(database) -> CategoryService:
    return CategoryService(
        CategoryRepository(database, get_settings()),
    )


async def _log_category_change(
    database,
    admin_claims: dict,
    action: str,
    category_id: int,
    description: str,
) -> None:
    settings = get_settings()
    try:
        await log_admin_activity(
            database,
            settings.admin_activity_logs_collection,
            admin_id=admin_claims["AdminId"],
            action=action,
            entity_name="Categories",
            entity_id=str(category_id),
            description=description,
        )
    except PyMongoError as error:
        raise HTTPException(
            status_code=503,
            detail=(
                "The category operation completed, but its activity log could "
                "not be saved. Contact an administrator before retrying."
            ),
        ) from error


@router.get("", response_model=list[CategoryView])
async def list_categories(database=Depends(get_database)) -> list[dict]:
    return await _service(database).list_categories()


@router.post("", status_code=status.HTTP_201_CREATED, response_model=CategoryView)
async def create_category(
    request: CategoryCreate,
    database=Depends(get_database),
    admin_claims: dict = Depends(require_admin),
) -> dict:
    category = await _service(database).create_category(
        request.category_name,
        request.description or "",
    )
    await _log_category_change(
        database,
        admin_claims,
        "CREATE",
        category["CategoryId"],
        "Created category.",
    )
    return category


@router.patch("/{category_id}", response_model=CategoryView)
async def update_category(
    category_id: int,
    request: CategoryCreate,
    database=Depends(get_database),
    admin_claims: dict = Depends(require_admin),
) -> dict:
    category = await _service(database).update_category(
        category_id,
        request.category_name,
        request.description,
    )
    await _log_category_change(
        database,
        admin_claims,
        "UPDATE",
        category_id,
        "Updated category.",
    )
    return category


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: int,
    database=Depends(get_database),
    admin_claims: dict = Depends(require_admin),
) -> None:
    await _service(database).delete_category(category_id)
    await _log_category_change(
        database,
        admin_claims,
        "DELETE",
        category_id,
        "Deleted category.",
    )
