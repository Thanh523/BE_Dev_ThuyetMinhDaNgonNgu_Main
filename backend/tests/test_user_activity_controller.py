import unittest
from unittest.mock import AsyncMock, Mock, patch

from src.controllers.user_activity_controller import (
    clear_listening_history,
    delete_listening_history_entry,
    get_user_place_details,
    list_user_categories,
    list_user_place_audios,
    list_user_places,
    router,
)
from src.middlewares.user_auth import require_user


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
            category_id=3,
            skip=12,
            limit=12,
            database=object(),
        )

        place_service.list_places.assert_awaited_once_with(
            "museum",
            3,
            "visible",
            12,
            12,
            True,
        )
        self.assertEqual(
            {"items": [{"PlaceId": 1}], "total": 1, "skip": 12, "limit": 12},
            result,
        )

    @patch("src.controllers.user_activity_controller._service")
    async def test_user_category_listing_returns_visible_categories(
        self,
        service_factory,
    ):
        service = Mock()
        categories = [{"CategoryId": 3, "CategoryName": "Museum"}]
        service.list_visible_categories = AsyncMock(return_value=categories)
        service_factory.return_value = service

        result = await list_user_categories(
            database=object(),
        )

        service.list_visible_categories.assert_awaited_once_with()
        self.assertEqual(categories, result)

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
        )

        service.get_place_details.assert_awaited_once_with(1)
        self.assertEqual(details, result)

    @patch("src.controllers.user_activity_controller._service")
    async def test_guest_audio_listing_returns_active_audio(
        self,
        service_factory,
    ):
        service = Mock()
        audios = [{"AudioId": "audio-1"}]
        service.list_place_audios = AsyncMock(return_value=audios)
        service_factory.return_value = service

        result = await list_user_place_audios(place_id=1, database=object())

        service.list_place_audios.assert_awaited_once_with(1)
        self.assertEqual(audios, result)

    def test_guest_browse_routes_are_public_but_personal_routes_require_login(self):
        routes = {
            (method, route.path): route
            for route in router.routes
            for method in (route.methods or set())
        }
        public_routes = (
            ("GET", "/api/user/places"),
            ("GET", "/api/user/categories"),
            ("GET", "/api/user/places/{place_id}"),
            ("GET", "/api/user/places/{place_id}/audios"),
        )
        for key in public_routes:
            with self.subTest(route=key):
                dependencies = routes[key].dependant.dependencies
                self.assertFalse(any(
                    dependency.call is require_user
                    for dependency in dependencies
                ))

        personal_route = routes[("GET", "/api/user/saved-places")]
        self.assertTrue(any(
            dependency.call is require_user
            for dependency in personal_route.dependant.dependencies
        ))

    @patch("src.controllers.user_activity_controller._service")
    async def test_delete_history_entry_uses_authenticated_user(
        self,
        service_factory,
    ):
        service = Mock()
        service.delete_listening_history_entry = AsyncMock(return_value=True)
        service_factory.return_value = service

        response = await delete_listening_history_entry(
            history_id="history-1",
            database=object(),
            claims={"UserId": "user-1"},
        )

        service.delete_listening_history_entry.assert_awaited_once_with(
            "user-1",
            "history-1",
        )
        self.assertEqual(204, response.status_code)

    @patch("src.controllers.user_activity_controller._service")
    async def test_clear_history_uses_authenticated_user(
        self,
        service_factory,
    ):
        service = Mock()
        service.clear_listening_history = AsyncMock(return_value=4)
        service_factory.return_value = service

        response = await clear_listening_history(
            database=object(),
            claims={"UserId": "user-1"},
        )

        service.clear_listening_history.assert_awaited_once_with("user-1")
        self.assertEqual(204, response.status_code)


if __name__ == "__main__":
    unittest.main()
