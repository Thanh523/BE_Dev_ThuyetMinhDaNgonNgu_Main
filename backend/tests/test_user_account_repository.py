import re
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock

from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError, PyMongoError

from src.config.settings import Settings
from src.repositories.user_account_repository import UserAccountRepository
from src.services.user_account_service import UserAccountService


class FakeCursor:
    # Mô phỏng các thao tác cursor MongoDB cần thiết trong repository.
    def __init__(self, items):
        self.items = items

    def sort(self, *_sort):
        return self

    def skip(self, _skip):
        return self

    def limit(self, _limit):
        return self

    async def to_list(self, length):
        return self.items[:length]


class FakeUserCollection:
    # Ghi lại truy vấn để kiểm tra bộ lọc và projection an toàn.
    def __init__(self, items):
        self.items = items
        self.find_arguments = None
        self.before_update = None

    @classmethod
    def matches(cls, query, item):
        for key, expected in query.items():
            if key == "$and":
                if not all(cls.matches(condition, item) for condition in expected):
                    return False
                continue
            if key == "$or":
                if not any(cls.matches(condition, item) for condition in expected):
                    return False
                continue
            actual = item.get(key)
            if isinstance(expected, dict):
                if "$ne" in expected and actual == expected["$ne"]:
                    return False
                if "$in" in expected and actual not in expected["$in"]:
                    return False
                if "$nin" in expected and actual in expected["$nin"]:
                    return False
                if "$regex" in expected:
                    flags = re.IGNORECASE if expected.get("$options") == "i" else 0
                    if not re.search(expected["$regex"], str(actual or ""), flags):
                        return False
            elif actual != expected:
                return False
        return True

    def find(self, query, projection):
        self.find_arguments = (query, projection)
        matched = [item for item in self.items if self.matches(query, item)]
        projected = [
            {key: value for key, value in item.items() if projection.get(key, 0)}
            for item in matched
        ]
        return FakeCursor(projected)

    async def find_one(self, query, projection):
        self.exists_arguments = (query, projection)
        return next(
            (
                {
                    key: value
                    for key, value in user.items()
                    if projection.get(key, 0)
                }
                for user in self.items
                if self.matches(query, user)
            ),
            None,
        )

    async def count_documents(self, query):
        return sum(self.matches(query, item) for item in self.items)

    async def find_one_and_update(
        self,
        query,
        update,
        return_document,
        projection,
    ):
        self.update_arguments = (query, update, return_document, projection)
        for user in self.items:
            if self.matches(query, user):
                user.update(update["$set"])
                return {
                    key: value
                    for key, value in user.items()
                    if projection.get(key, 0)
                }
        return None

    async def update_one(self, query, update):
        self.update_arguments = (query, update)
        if self.before_update:
            self.before_update()
        for user in self.items:
            if self.matches(query, user):
                previous = user.copy()
                user.update(update["$set"])
                return FakeUpdateResult(previous != user)
        return FakeUpdateResult(False)

    async def insert_one(self, document):
        if await self.find_one(
            {
                "Email": {
                    "$regex": f"^{re.escape(document['Email'])}$",
                    "$options": "i",
                }
            },
            {"_id": 1},
        ):
            raise DuplicateKeyError("duplicate email")
        self.items.append(document)

    async def delete_one(self, query):
        user_ids = []
        if "UserId" in query:
            user_ids.append(query["UserId"])
        user_ids.extend(
            condition["UserId"]
            for condition in query.get("$or", [])
            if "UserId" in condition
        )
        for index, user in enumerate(self.items):
            if user.get("UserId") in user_ids:
                del self.items[index]
                return FakeDeleteResult(1)
        return FakeDeleteResult(0)


class FakeDeleteResult:
    def __init__(self, deleted_count):
        self.deleted_count = deleted_count


class FakeUpdateResult:
    def __init__(self, modified):
        self.modified_count = int(modified)


class FakeDatabase:
    def __init__(
        self,
        collection,
        saved_places=None,
        listening_history=None,
        visitor_sessions=None,
        usage_events=None,
    ):
        self.collections = {
            "UserAccounts": collection,
            "SavedPlaces": saved_places or FakeUserCollection([]),
            "ListeningHistory": listening_history or FakeUserCollection([]),
            "VisitorSessions": visitor_sessions or FakeUserCollection([]),
            "UsageEvents": usage_events or FakeUserCollection([]),
        }
        self.collection_name = None
        self.accessed_collection_names = []

    def __getitem__(self, collection_name):
        self.collection_name = collection_name
        self.accessed_collection_names.append(collection_name)
        return self.collections.setdefault(collection_name, FakeUserCollection([]))


class UserAccountRepositoryTests(unittest.IsolatedAsyncioTestCase):
    # Kiểm tra truy vấn danh sách và cách xử lý lỗi database của service.
    def setUp(self):
        self.settings = Settings(
            mongodb_uri="mongodb://localhost:27017",
            mongodb_database="test",
            places_collection="Places",
            place_images_collection="PlaceImages",
            jwt_key=None,
            jwt_algorithm="HS256",
            jwt_role_claim="role",
            jwt_issuer=None,
            jwt_audience=None,
            cors_origins=[],
            image_storage_dir=Path("uploads"),
        )

    async def test_list_filters_search_and_never_projects_password_hash(self):
        users = [
            {
                "UserId": 7,
                "FullName": "Test User",
                "Email": "test@example.com",
                "IsActive": True,
            }
        ]
        collection = FakeUserCollection(users)
        database = FakeDatabase(collection)
        repository = UserAccountRepository(database, self.settings)

        items, total = await repository.list("test", True, 10, 5)

        self.assertEqual("UserAccounts", database.accessed_collection_names[0])
        self.assertEqual(
            {
                "$or": [
                    {"FullName": {"$regex": "test", "$options": "i"}},
                    {"Email": {"$regex": "test", "$options": "i"}},
                ],
                "IsActive": True,
                "IsDeleted": {"$ne": True},
            },
            collection.find_arguments[0],
        )
        self.assertNotIn("PasswordHash", collection.find_arguments[1])
        self.assertEqual(users, items)
        self.assertEqual(1, total)

    async def test_update_status_accepts_numeric_user_id_and_excludes_password_hash(self):
        users = [
            {
                "UserId": 7,
                "FullName": "Test User",
                "Email": "test@example.com",
                "PasswordHash": "must-not-be-returned",
                "IsActive": True,
            }
        ]
        collection = FakeUserCollection(users)
        repository = UserAccountRepository(FakeDatabase(collection), self.settings)

        result = await repository.update_status("7", False)

        self.assertEqual({"IsActive": False}, collection.update_arguments[1]["$set"])
        self.assertIn("IsDeleted", collection.update_arguments[0]["$and"][1])
        self.assertEqual(False, result["IsActive"])
        self.assertNotIn("PasswordHash", result)

    async def test_update_status_returns_not_found_for_unknown_user(self):
        repository = UserAccountRepository(
            FakeDatabase(FakeUserCollection([])),
            self.settings,
        )
        service = UserAccountService(repository)

        with self.assertRaises(HTTPException) as raised:
            await service.update_status("missing", False)

        self.assertEqual(404, raised.exception.status_code)

    async def test_email_exists_ignores_same_user_and_finds_another_user(self):
        collection = FakeUserCollection(
            [
                {"UserId": 7, "Email": "same@example.com"},
                {"UserId": 8, "Email": "other@example.com"},
            ]
        )
        repository = UserAccountRepository(FakeDatabase(collection), self.settings)

        self.assertFalse(await repository.email_exists("SAME@example.com", "7"))
        self.assertTrue(await repository.email_exists("same@example.com", "8"))

    async def test_profile_update_normalizes_name_and_email(self):
        repository = Mock()
        repository.email_exists = AsyncMock(return_value=False)
        repository.update_profile = AsyncMock(
            return_value={
                "UserId": "user-7",
                "FullName": "Test User",
                "Email": "test@example.com",
                "IsActive": True,
            }
        )
        service = UserAccountService(repository)

        await service.update_profile("user-7", " Test User ", " TEST@EXAMPLE.COM ")

        repository.update_profile.assert_awaited_once_with(
            "user-7",
            {"FullName": "Test User", "Email": "test@example.com"},
        )

    async def test_profile_update_rejects_invalid_email(self):
        repository = Mock()
        service = UserAccountService(repository)

        with self.assertRaises(HTTPException) as raised:
            await service.update_profile("user-7", "Test User", "not-an-email")

        self.assertEqual(422, raised.exception.status_code)
        repository.update_profile.assert_not_called()

    async def test_profile_update_rejects_email_used_by_another_user(self):
        repository = Mock()
        repository.email_exists = AsyncMock(return_value=True)
        repository.update_profile = AsyncMock()
        service = UserAccountService(repository)

        with self.assertRaises(HTTPException) as raised:
            await service.update_profile("user-7", None, "taken@example.com")

        self.assertEqual(409, raised.exception.status_code)
        repository.update_profile.assert_not_called()

    async def test_profile_update_only_returns_public_fields(self):
        users = [
            {
                "UserId": "user-7",
                "FullName": "Old Name",
                "Email": "old@example.com",
                "PasswordHash": "must-not-be-returned",
                "IsActive": True,
            }
        ]
        collection = FakeUserCollection(users)
        repository = UserAccountRepository(FakeDatabase(collection), self.settings)

        result = await repository.update_profile(
            "user-7",
            {"FullName": "New Name", "Email": "new@example.com"},
        )

        self.assertEqual("New Name", result["FullName"])
        self.assertNotIn("PasswordHash", result)

    async def test_get_activity_returns_recent_records_and_totals(self):
        user_collection = FakeUserCollection(
            [
                {
                    "UserId": 7,
                    "FullName": "Test User",
                    "Email": "test@example.com",
                    "PasswordHash": "must-not-be-returned",
                    "IsActive": True,
                }
            ]
        )
        saved_places = FakeUserCollection(
            [{"SavedPlaceId": 1, "UserId": 7, "PlaceId": 12}]
        )
        listening_history = FakeUserCollection(
            [
                {
                    "ListeningHistoryId": 2,
                    "UserId": 7,
                    "AudioId": 15,
                    "PlayedSeconds": 42,
                    "IsCompleted": False,
                }
            ]
        )
        visitor_sessions = FakeUserCollection(
            [
                {
                    "SessionId": "session-3",
                    "UserId": 7,
                    "StartedAt": "2026-11-01T10:00:00Z",
                    "LastReportedAt": "2026-11-01T10:15:00Z",
                    "EndedAt": None,
                }
            ]
        )
        usage_events = FakeUserCollection(
            [
                {
                    "EventId": "event-4",
                    "ClientEventId": "client-event-4",
                    "SessionId": "session-3",
                    "EventType": "audio_play",
                    "CreatedAt": "2026-11-01T10:16:00Z",
                }
            ]
        )
        repository = UserAccountRepository(
            FakeDatabase(
                user_collection,
                saved_places,
                listening_history,
                visitor_sessions,
                usage_events,
            ),
            self.settings,
        )

        activity = await repository.get_activity("7", 10)

        self.assertEqual("Test User", activity["user"]["FullName"])
        self.assertNotIn("PasswordHash", activity["user"])
        self.assertEqual(1, activity["saved_places_total"])
        self.assertEqual(12, activity["saved_places"][0]["PlaceId"])
        self.assertEqual(1, activity["listening_history_total"])
        self.assertEqual(15, activity["listening_history"][0]["AudioId"])
        self.assertEqual(1, activity["visitor_sessions_total"])
        self.assertEqual("session-3", activity["visitor_sessions"][0]["SessionId"])
        self.assertEqual("2026-11-01T10:15:00Z", activity["visitor_sessions"][0]["LastSeenAt"])
        self.assertEqual(1, activity["usage_events_total"])
        self.assertEqual("audio_play", activity["usage_events"][0]["EventType"])

    async def test_delete_user_when_no_related_activity_exists(self):
        users = FakeUserCollection(
            [{"UserId": "user-1", "FullName": "Test User"}]
        )
        repository = UserAccountRepository(FakeDatabase(users), self.settings)

        result = await repository.delete_if_unrelated("user-1")

        self.assertTrue(result["deleted"])
        self.assertEqual(1, len(users.items))
        self.assertTrue(users.items[0]["IsDeleted"])
        self.assertFalse(users.items[0]["IsActive"])
        self.assertIn("DeletedAt", users.items[0])

    async def test_concurrent_activity_write_keeps_user_reference_after_soft_delete(self):
        users = FakeUserCollection([{"UserId": "user-1"}])
        saved_places = FakeUserCollection([])
        users.before_update = lambda: saved_places.items.append(
            {"UserId": "user-1", "PlaceId": 10}
        )
        repository = UserAccountRepository(
            FakeDatabase(users, saved_places=saved_places),
            self.settings,
        )

        result = await repository.delete_if_unrelated("user-1")

        self.assertTrue(result["deleted"])
        self.assertTrue(users.items[0]["IsDeleted"])
        self.assertEqual("user-1", saved_places.items[0]["UserId"])

    async def test_deleted_users_are_hidden_from_list_and_cannot_be_deleted_again(self):
        users = FakeUserCollection(
            [
                {"UserId": "user-1", "FullName": "Visible"},
                {"UserId": "user-2", "FullName": "Deleted", "IsDeleted": True},
            ]
        )
        repository = UserAccountRepository(FakeDatabase(users), self.settings)

        items, total = await repository.list("", None, 0, 20)
        second_delete = await repository.delete_if_unrelated("user-2")

        self.assertEqual(["user-1"], [item["UserId"] for item in items])
        self.assertEqual(1, total)
        self.assertIsNone(second_delete)

    async def test_delete_user_is_blocked_by_saved_place(self):
        users = FakeUserCollection([{"UserId": "user-1"}])
        saved_places = FakeUserCollection(
            [{"UserId": "user-1", "PlaceId": 10}]
        )
        repository = UserAccountRepository(
            FakeDatabase(users, saved_places=saved_places),
            self.settings,
        )

        result = await repository.delete_if_unrelated("user-1")

        self.assertFalse(result["deleted"])
        self.assertEqual(1, result["related_counts"]["saved_places"])
        self.assertEqual(1, len(users.items))

    async def test_delete_user_is_blocked_by_usage_event_for_visitor_session(self):
        users = FakeUserCollection([{"UserId": "user-1"}])
        visitor_sessions = FakeUserCollection(
            [{"UserId": "user-1", "SessionId": "session-1"}]
        )
        usage_events = FakeUserCollection(
            [{"SessionId": "session-1", "EventType": "play"}]
        )
        repository = UserAccountRepository(
            FakeDatabase(
                users,
                visitor_sessions=visitor_sessions,
                usage_events=usage_events,
            ),
            self.settings,
        )

        result = await repository.delete_if_unrelated("user-1")

        self.assertFalse(result["deleted"])
        self.assertEqual(1, result["related_counts"]["usage_events"])
        self.assertEqual(1, len(users.items))

    async def test_delete_service_returns_conflict_when_activity_exists(self):
        repository = Mock()
        repository.delete_if_unrelated = AsyncMock(
            return_value={
                "deleted": False,
                "related_counts": {
                    "saved_places": 1,
                    "listening_history": 0,
                    "visitor_sessions": 0,
                    "usage_events": 0,
                },
            }
        )
        service = UserAccountService(repository)

        with self.assertRaises(HTTPException) as raised:
            await service.delete_user("user-1")

        self.assertEqual(409, raised.exception.status_code)

    async def test_service_returns_unavailable_error_on_database_failure(self):
        repository = Mock()
        repository.list = AsyncMock(side_effect=PyMongoError("database unavailable"))
        service = UserAccountService(repository)

        with self.assertRaises(HTTPException) as raised:
            await service.list_users("", None, 0, 20)

        self.assertEqual(503, raised.exception.status_code)


if __name__ == "__main__":
    unittest.main()
