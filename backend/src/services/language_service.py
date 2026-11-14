from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError, PyMongoError

from src.repositories.language_repository import LanguageRepository


class LanguageService:
    def __init__(self, repository: LanguageRepository):
        self.repository = repository

    @staticmethod
    def _normalize_code(value: str) -> str:
        code = value.strip()
        if not code or len(code) > 10 or any(char.isspace() for char in code):
            raise HTTPException(
                status_code=422,
                detail="Language code must be 1-10 characters without spaces.",
            )
        return code

    @staticmethod
    def _normalize_name(value: str) -> str:
        name = value.strip()
        if not name:
            raise HTTPException(status_code=422, detail="Language name is required.")
        return name

    async def list_languages(self, search: str | None = None) -> list[dict]:
        try:
            languages = await self.repository.list(search)
            return [
                {**language, "IsActive": language.get("IsActive", True)}
                for language in languages
            ]
        except PyMongoError as error:
            raise HTTPException(
                status_code=503,
                detail="Language list is temporarily unavailable.",
            ) from error

    async def create_language(self, code: str, name: str) -> dict:
        code = self._normalize_code(code)
        name = self._normalize_name(name)
        try:
            if await self.repository.exists_by_code(code):
                raise HTTPException(status_code=409, detail="Language code already exists.")
            if await self.repository.exists_by_name(name):
                raise HTTPException(status_code=409, detail="Language name already exists.")
            return await self.repository.create(code, name)
        except DuplicateKeyError as error:
            raise HTTPException(status_code=409, detail="Language code already exists.") from error
        except PyMongoError as error:
            raise HTTPException(status_code=503, detail="Language could not be saved.") from error

    async def update_language(
        self,
        language_code: str,
        new_code: str,
        name: str,
    ) -> dict:
        current_code = self._normalize_code(language_code)
        new_code = self._normalize_code(new_code)
        name = self._normalize_name(name)
        try:
            if await self.repository.get(current_code) is None:
                raise HTTPException(status_code=404, detail="Language was not found.")
            if new_code != current_code and await self.repository.has_references(current_code):
                raise HTTPException(
                    status_code=409,
                    detail="Language code cannot change while content references it. Change the name or hide the language instead.",
                )
            if await self.repository.exists_by_code(new_code, current_code):
                raise HTTPException(status_code=409, detail="Language code already exists.")
            if await self.repository.exists_by_name(name, current_code):
                raise HTTPException(status_code=409, detail="Language name already exists.")
            changes = {"LanguageCode": new_code, "LanguageName": name}
            result = await self.repository.update(current_code, changes)
        except DuplicateKeyError as error:
            raise HTTPException(status_code=409, detail="Language code already exists.") from error
        except PyMongoError as error:
            raise HTTPException(status_code=503, detail="Language could not be updated.") from error
        if result is None:
            raise HTTPException(status_code=404, detail="Language was not found.")
        return {**result, "IsActive": result.get("IsActive", True)}

    async def set_status(self, language_code: str, is_active: bool) -> dict:
        try:
            result = await self.repository.update(
                self._normalize_code(language_code),
                {"IsActive": is_active},
            )
        except PyMongoError as error:
            raise HTTPException(status_code=503, detail="Language status could not be updated.") from error
        if result is None:
            raise HTTPException(status_code=404, detail="Language was not found.")
        return {**result, "IsActive": result.get("IsActive", True)}

    async def delete_language(self, language_code: str) -> None:
        code = self._normalize_code(language_code)
        try:
            if await self.repository.get(code) is None:
                raise HTTPException(status_code=404, detail="Language was not found.")
            if await self.repository.has_references(code):
                raise HTTPException(
                    status_code=409,
                    detail="Language cannot be deleted while content references it. Hide it instead.",
                )
            if not await self.repository.delete(code):
                raise HTTPException(status_code=404, detail="Language was not found.")
        except PyMongoError as error:
            raise HTTPException(status_code=503, detail="Language could not be deleted.") from error
