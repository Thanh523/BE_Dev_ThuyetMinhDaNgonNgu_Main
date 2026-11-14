import unittest
from unittest.mock import AsyncMock, Mock

from pymongo.errors import PyMongoError

from src.services.dashboard_service import DashboardService


class DashboardServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.repository = Mock()
        self.repository.count_access_events = AsyncMock(return_value=12)
        self.repository.count_places = AsyncMock(return_value=4)
        self.repository.count_narrations = AsyncMock(return_value=7)
        self.repository.list_online_accounts = AsyncMock(
            return_value=[
                {
                    "user_id": "user-1",
                    "full_name": "Nguyễn Văn A",
                    "email": "a@example.com",
                    "last_seen_at": None,
                },
            ],
        )
        self.repository.list_usage_by_place = AsyncMock(
            return_value=[
                {"place_id": 1, "place_name": "Bến Nhà Rồng", "count": 5},
            ],
        )
        self.repository.list_usage_by_language = AsyncMock(
            return_value=[
                {"language_code": "vi", "language_name": "Vietnamese", "count": 5},
            ],
        )
        self.service = DashboardService(self.repository)

    async def test_dashboard_returns_all_statistics(self):
        result = await self.service.get_dashboard()

        self.assertEqual(result["access_count"], 12)
        self.assertEqual(result["places_count"], 4)
        self.assertEqual(result["narrations_count"], 7)
        self.assertEqual(result["online_accounts_count"], 1)
        self.assertEqual(result["online_accounts"][0]["user_id"], "user-1")
        self.assertEqual(result["usage_by_place"][0]["count"], 5)
        self.assertEqual(result["usage_by_language"][0]["language_code"], "vi")
        self.assertIsNone(result["access_error"])

    async def test_dashboard_keeps_other_statistics_when_one_query_fails(self):
        self.repository.count_access_events = AsyncMock(
            side_effect=PyMongoError("database unavailable"),
        )
        self.repository.list_online_accounts = AsyncMock(
            return_value=[],
        )

        result = await self.service.get_dashboard()

        self.assertIsNone(result["access_count"])
        self.assertEqual(result["access_error"], "Không thể tải số liệu mục này.")
        self.assertEqual(result["places_count"], 4)
        self.assertEqual(result["narrations_count"], 7)
        self.assertEqual(result["online_accounts_count"], 0)

    async def test_dashboard_keeps_other_statistics_when_metric_data_is_invalid(self):
        self.repository.count_narrations = AsyncMock(
            side_effect=TypeError("invalid metric data"),
        )

        result = await self.service.get_dashboard()

        self.assertIsNone(result["narrations_count"])
        self.assertEqual(result["narrations_error"], "Không thể tải số liệu mục này.")
        self.assertEqual(result["places_count"], 4)
