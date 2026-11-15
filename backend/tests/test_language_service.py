import unittest
from unittest.mock import AsyncMock, Mock

from fastapi import HTTPException

from src.services.language_service import LanguageService


class LanguageServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.repository = Mock()
        self.repository.list = AsyncMock(return_value=[])
        self.repository.get = AsyncMock(return_value={
            "LanguageCode": "vi",
            "LanguageName": "Tiếng Việt",
            "IsActive": True,
        })
        self.repository.exists_by_code = AsyncMock(return_value=False)
        self.repository.exists_by_name = AsyncMock(return_value=False)
        self.repository.create = AsyncMock(return_value={
            "LanguageCode": "fr",
            "LanguageName": "Français",
            "IsActive": True,
        })
        self.repository.update = AsyncMock(return_value={
            "LanguageCode": "vi",
            "LanguageName": "Vietnamese",
            "IsActive": False,
        })
        self.repository.has_references = AsyncMock(return_value=False)
        self.repository.delete = AsyncMock(return_value=True)
        self.service = LanguageService(self.repository)

    async def test_create_language_normalizes_and_activates_language(self):
        result = await self.service.create_language(" fr ", " Français ")

        self.repository.create.assert_awaited_once_with("fr", "Français")
        self.assertEqual(result["IsActive"], True)

    async def test_status_update_preserves_language_data(self):
        result = await self.service.set_status("vi", False)

        self.repository.update.assert_awaited_once_with("vi", {"IsActive": False})
        self.assertFalse(result["IsActive"])

    async def test_delete_rejects_referenced_language(self):
        self.repository.has_references.return_value = True

        with self.assertRaises(HTTPException) as context:
            await self.service.delete_language("vi")

        self.assertEqual(context.exception.status_code, 409)
        self.repository.delete.assert_not_awaited()
