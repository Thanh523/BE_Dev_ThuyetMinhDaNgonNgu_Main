import re
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock

from fastapi import HTTPException
from pymongo.errors import PyMongoError

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

    def find(self, query, projection):
        self.find_arguments = (query, projection)
        return FakeCursor(self.items)

    async def find_one(self, query, projection):
        self.exists_arguments = (query, projection)
        email_condition = query.get("Email")
        excluded_user_ids = query.get("UserId", {}).get("$nin", [])
        if email_condition is None:
            user_id_query = query.get("UserId")
            alternatives = query.get("$or", [])
            user_ids = [condition["UserId"] for condition in alternatives]
            if user_id_query is not None:
                user_ids.append(user_id_query)
            for user in self.items:
                if user.get("UserId") in user_ids:
                    return {
                        key: value
                        for key, value in user.items()
                        if projection.get(key, 0)
                    }
            return None

        pattern = re.compile(email_condition["$regex"], re.IGNORECASE)
        return next(
            (
                {"_id": user.get("_id")}
                for user in self.items
                if pattern.fullmatch(user.get("Email", ""))
                and user.get("UserId") not in excluded_user_ids
            ),
            None,
        )

    async def count_documents(self, query):
        return len(self.items)

    async def find_one_and_update(
        self,
        query,
        update,
        return_document,
        projection,
    ):
        self.update_arguments = (query, update, return_document, projection)
        for user in self.items:
            matches = query.get("UserId") == user.get("UserId") or any(
                condition.get("UserId") == user.get("UserId")
                for condition in query.get("$or", [])
            )
            if matches:
                user.update(update["$set"])
                return {
                    key: value
                    for key, value in user.items()
                    if projection.get(key, 0)
                }
        return None

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

class FakeDatabase:
    def __init__(
        self,
        collection,
        saved_places=None,
        listening_history=None,
        visitor_sessions=None,
    ):
        self.collections = {
            "UserAccounts": collection,
            "SavedPlaces": saved_places or FakeUserCollection([]),
            "ListeningHistory": listening_history or FakeUserCollection([]),
            "VisitorSessions": visitor_sessions or FakeUserCollection([]),
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

    async def test_temporary_user_creation_hashes_password_and_returns_no_hash(self):
        collection = FakeUserCollection([])
        repository = UserAccountRepository(FakeDatabase(collection), self.settings)
        service = UserAccountService(repository)

        result = await service.create_user(
            " Test Account ",
            "TEST@example.com",
            "a-long-initial-password",
        )

        stored_user = collection.items[0]
        self.assertEqual("Test Account", stored_user["FullName"])
        self.assertEqual("test@example.com", stored_user["Email"])
        self.assertNotEqual("a-long-initial-password", stored_user["PasswordHash"])
        self.assertNotIn("PasswordHash", result)
        self.assertTrue(stored_user["IsActive"])

    async def test_temporary_user_creation_rejects_short_password(self):
        service = UserAccountService(Mock())

        with self.assertRaises(HTTPException) as raised:
            await service.create_user("Test Account", "test@example.com", "short")

        self.assertEqual(422, raised.exception.status_code)

    async def test_temporary_user_creation_rejects_duplicate_email(self):
        repository = Mock()
        repository.email_exists = AsyncMock(return_value=True)
        repository.create = AsyncMock()
        service = UserAccountService(repository)

        with self.assertRaises(HTTPException) as raised:
            await service.create_user(
                "Test Account",
                "taken@example.com",
                "a-long-initial-password",
            )

        self.assertEqual(409, raised.exception.status_code)
        repository.create.assert_not_called()

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
        repository = UserAccountRepository(
            FakeDatabase(
                user_collection,
                saved_places,
                listening_history,
                visitor_sessions,
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

    async def test_service_returns_unavailable_error_on_database_failure(self):
        repository = Mock()
        repository.list = AsyncMock(side_effect=PyMongoError("database unavailable"))
        service = UserAccountService(repository)

        with self.assertRaises(HTTPException) as raised:
            await service.list_users("", None, 0, 20)

        self.assertEqual(503, raised.exception.status_code)


if __name__ == "__main__":
    unittest.main()
