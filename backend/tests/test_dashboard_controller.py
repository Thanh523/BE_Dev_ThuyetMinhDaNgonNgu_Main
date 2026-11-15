import unittest
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from fastapi import HTTPException

from src.controllers.dashboard_controller import get_dashboard


def dashboard_payload():
    return {
        "access_count": 4,
        "access_error": None,
        "places_count": 2,
        "places_error": None,
        "narrations_count": 3,
        "narrations_error": None,
        "online_accounts_count": 1,
        "online_accounts": [],
        "online_accounts_error": None,
        "online_guests_count": 2,
        "online_guests_error": None,
        "online_visitors_count": 3,
        "online_visitors_error": None,
        "online_timeout_minutes": 5,
        "usage_by_place": [],
        "usage_by_place_error": None,
        "usage_by_language": [],
        "usage_by_language_error": None,
    }


class DashboardControllerTests(unittest.IsolatedAsyncioTestCase):
    @patch("src.controllers.dashboard_controller.DashboardService")
    @patch("src.controllers.dashboard_controller.get_settings")
    @patch("src.controllers.dashboard_controller.DashboardRepository")
    async def test_access_dates_are_converted_from_vietnam_time(
        self,
            repository_factory,
        get_settings_mock,
        service_factory,
    ):
        service = Mock()
        service.get_dashboard = AsyncMock(return_value=dashboard_payload())
        service_factory.return_value = service
        get_settings_mock.return_value = SimpleNamespace(
            online_session_timeout_minutes=5,
        )

        await get_dashboard(
            access_from=date(2026, 1, 1),
            access_to=date(2026, 1, 2),
            database=object(),
        )

        service.get_dashboard.assert_awaited_once_with(
            datetime(2025, 12, 31, 17, tzinfo=timezone.utc),
            datetime(2026, 1, 2, 17, tzinfo=timezone.utc),
        )

    async def test_access_date_range_rejects_start_after_end(self):
        with self.assertRaises(HTTPException) as raised:
            await get_dashboard(
                access_from=date(2026, 1, 2),
                access_to=date(2026, 1, 1),
                database=object(),
            )

        self.assertEqual(422, raised.exception.status_code)


if __name__ == "__main__":
    unittest.main()
