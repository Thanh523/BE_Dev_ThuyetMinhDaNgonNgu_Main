import unittest
from unittest.mock import AsyncMock, Mock, patch

from src.controllers.user_activity_controller import (
    get_user_place_details,
    list_user_places,
)


class UserActivityControllerTests(unittest.IsolatedAsyncioTestCase):
    @patch("src.controllers.user_activity_controller._place_service")
    async def test_user_place_listing_only_requests_visible_places(
        self,
        place_service_factory,
    ):
        place_service = Mock()
        place_service.list_places = AsyncMock(return_value=([{"PlaceId": 1}], 1))
        place_service_factory.return_value = place_service

        result = await list_user_places(
            search="museum",
            skip=12,
            limit=12,
            database=object(),
            claims={"UserId": "user-1"},
        )

        place_service.list_places.assert_awaited_once_with(
            "museum",
            None,
            "visible",
            12,
            12,
        )
        self.assertEqual(
            {"items": [{"PlaceId": 1}], "total": 1, "skip": 12, "limit": 12},
            result,
        )

    @patch("src.controllers.user_activity_controller._service")
    async def test_user_place_details_uses_user_activity_service(
        self,
        service_factory,
    ):
        service = Mock()
        details = {
            "place": {"PlaceId": 1},
            "category": None,
            "images": [],
            "audios": [],
        }
        service.get_place_details = AsyncMock(return_value=details)
        service_factory.return_value = service

        result = await get_user_place_details(
            place_id=1,
            database=object(),
            claims={"UserId": "user-1"},
        )

        service.get_place_details.assert_awaited_once_with(1)
        self.assertEqual(details, result)


if __name__ == "__main__":
    unittest.main()
