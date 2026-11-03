from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError, PyMongoError

from src.repositories.category_repository import CategoryRepository


class CategoryService:
    def __init__(self, repository: CategoryRepository):
        self.repository = repository

    async def list_categories(self) -> list[dict]:
        try:
            return await self.repository.list()
        except PyMongoError as error:
            raise HTTPException(
                status_code=503,
                detail="Category list is temporarily unavailable.",
            ) from error

    async def create_category(self, name: str, description: str = "") -> dict:
        category_name = name.strip()
        category_description = description.strip()
        if not category_name:
            raise HTTPException(status_code=422, detail="Category name is required.")
        try:
            if await self.repository.exists_by_name(category_name):
                raise HTTPException(
                    status_code=409,
                    detail="Category name already exists.",
                )
            return await self.repository.create(category_name, category_description)
        except DuplicateKeyError as error:
            raise HTTPException(
                status_code=409,
                detail="Category name or ID already exists.",
            ) from error
        except PyMongoError as error:
            raise HTTPException(status_code=503, detail="Category could not be saved.") from error

    async def update_category(
        self,
        category_id: int,
        name: str,
        description: str | None = None,
    ) -> dict:
        category_name = name.strip()
        if not category_name:
            raise HTTPException(status_code=422, detail="Category name is required.")
        updates = {"CategoryName": category_name}
        if description is not None:
            updates["Description"] = description.strip()
        try:
            if await self.repository.exists_by_name(category_name, category_id):
                raise HTTPException(
                    status_code=409,
                    detail="Category name already exists.",
                )
            category = await self.repository.update(category_id, updates)
        except DuplicateKeyError as error:
            raise HTTPException(
                status_code=409,
                detail="Category name already exists.",
            ) from error
        except PyMongoError as error:
            raise HTTPException(
                status_code=503,
                detail="Category could not be updated.",
            ) from error
        if category is None:
            raise HTTPException(status_code=404, detail="Category was not found.")
        return category

    async def delete_category(self, category_id: int) -> None:
        try:
            if await self.repository.get(category_id) is None:
                raise HTTPException(status_code=404, detail="Category was not found.")
            if await self.repository.has_places(category_id):
                raise HTTPException(
                    status_code=409,
                    detail="Category cannot be deleted while places use it.",
                )
            deleted = await self.repository.delete(category_id)
        except PyMongoError as error:
            raise HTTPException(status_code=503, detail="Category could not be deleted.") from error
        if not deleted:
            raise HTTPException(status_code=404, detail="Category was not found.")

    async def exists(self, category_id: int) -> bool:
        try:
            return await self.repository.exists(category_id)
        except PyMongoError as error:
            raise HTTPException(
                status_code=503,
                detail="Category information is temporarily unavailable.",
            ) from error
