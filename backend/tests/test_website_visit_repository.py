import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock

from src.repositories.user_activity_repository import UserActivityRepository


class WebsiteVisitRepositoryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.repository = object.__new__(UserActivityRepository)
        self.repository.website_visits = Mock()
        self.repository.website_visits.find_one_and_update = AsyncMock()

    async def test_start_is_idempotent_and_preserves_original_start_time(self):
        visit = {
            "VisitId": "visit-1",
            "StartedAt": datetime(2026, 11, 1, tzinfo=timezone.utc),
        }
        self.repository.website_visits.find_one_and_update.return_value = visit
        now = datetime.now(timezone.utc)

        result = await self.repository.start_website_visit("visit-1", now)

        self.assertEqual(visit, result)
        query, update = self.repository.website_visits.find_one_and_update.await_args.args
        self.assertEqual({"VisitId": "visit-1"}, query)
        self.assertEqual(
            {"VisitId": "visit-1", "StartedAt": now},
            update["$setOnInsert"],
        )
        self.assertEqual({"LastSeenAt": now}, update["$set"])
        self.assertTrue(
            self.repository.website_visits.find_one_and_update.await_args.kwargs["upsert"],
        )

    async def test_claim_and_release_change_account_association_on_the_same_visit(self):
        now = datetime.now(timezone.utc)

        await self.repository.claim_website_visit("visit-1", "user-1", now)
        claim_query, claim_update = (
            self.repository.website_visits.find_one_and_update.await_args.args
        )
        self.assertEqual(
            {"VisitId": "visit-1", "EndedAt": None},
            claim_query,
        )
        self.assertEqual(
            {"UserId": "user-1", "LastSeenAt": now},
            claim_update["$set"],
        )

        await self.repository.release_website_visit("visit-1", "user-1", now)
        release_query, release_update = (
            self.repository.website_visits.find_one_and_update.await_args.args
        )
        self.assertEqual(
            {"VisitId": "visit-1", "UserId": "user-1", "EndedAt": None},
            release_query,
        )
        self.assertEqual({"UserId": ""}, release_update["$unset"])


if __name__ == "__main__":
    unittest.main()
