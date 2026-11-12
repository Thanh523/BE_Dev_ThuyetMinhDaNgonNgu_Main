import unittest
from unittest.mock import AsyncMock

from fastapi import HTTPException

from src.services.narration_service import NarrationService


class NarrationServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_create_requires_language_foreign_key(self):
        repository = AsyncMock()
        repository.place_exists.return_value = True
        repository.language_exists.return_value = False
        service = NarrationService(repository)

        with self.assertRaises(HTTPException) as raised:
            await service.create(15, "xx", "Title", "Content")

        self.assertEqual(422, raised.exception.status_code)
        repository.narration_language_exists.assert_not_awaited()
        repository.create.assert_not_awaited()

    async def test_create_stores_erd_fields_and_relationships(self):
        repository = AsyncMock()
        repository.place_exists.return_value = True
        repository.language_exists.return_value = True
        repository.narration_language_exists.return_value = False
        repository.create.return_value = {
            "NarrationId": 1,
            "PlaceId": 15,
            "LanguageCode": "vi",
            "Title": "Title",
            "Content": "Content",
        }
        service = NarrationService(repository)

        result = await service.create(15, " vi ", " Title ", " Content ")

        self.assertEqual(1, result["NarrationId"])
        repository.create.assert_awaited_once_with(
            {
                "PlaceId": 15,
                "LanguageCode": "vi",
                "Title": "Title",
                "Content": "Content",
            }
        )


if __name__ == "__main__":
    unittest.main()
