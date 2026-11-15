import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock

from src.repositories.dashboard_repository import DashboardRepository


class DashboardRepositoryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.repository = object.__new__(DashboardRepository)
        self.repository.website_visits = Mock()
        self.repository.website_visits.count_documents = AsyncMock(return_value=6)

    async def test_access_count_filters_visit_start_time(self):
        start_at = datetime(2026, 11, 1, tzinfo=timezone.utc)
        end_at = datetime(2026, 11, 2, tzinfo=timezone.utc)

        result = await self.repository.count_access_events(start_at, end_at)

        self.assertEqual(6, result)
        self.repository.website_visits.count_documents.assert_awaited_once_with(
            {"StartedAt": {"$gte": start_at, "$lt": end_at}},
        )

    async def test_access_count_without_dates_counts_all_website_visits(self):
        result = await self.repository.count_access_events()

        self.assertEqual(6, result)
        self.repository.website_visits.count_documents.assert_awaited_once_with({})

    async def test_online_guest_count_only_includes_recent_active_guest_visits(self):
        await self.repository.count_online_guests(5)

        query = self.repository.website_visits.count_documents.await_args.args[0]
        self.assertIsNone(query["UserId"])
        self.assertIsNone(query["EndedAt"])
        cutoff_age = (
            datetime.now(timezone.utc) - query["LastSeenAt"]["$gte"]
        ).total_seconds()
        self.assertGreaterEqual(cutoff_age, 300)
        self.assertLess(cutoff_age, 301)


if __name__ == "__main__":
    unittest.main()
