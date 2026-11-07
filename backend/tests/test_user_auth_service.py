import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import jwt
from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

from src.config.settings import Settings
from src.services.user_auth_service import UserAuthService, password_hasher


def settings(jwt_key="x" * 48):
    return Settings(
        mongodb_uri="mongodb://localhost:27017",
        mongodb_database="test",
        places_collection="Places",
        place_images_collection="PlaceImages",
        jwt_key=jwt_key,
        jwt_algorithm="HS256",
        jwt_role_claim="role",
        jwt_issuer=None,
        jwt_audience=None,
        cors_origins=[],
        image_storage_dir=Path("uploads"),
    )


class UserAuthServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_register_normalizes_email_and_stores_only_password_hash(self):
        repository = Mock()
        repository.find_by_email = AsyncMock(return_value=None)
        repository.create = AsyncMock()
        service = UserAuthService(repository, settings())

        user = await service.register(" Test User ", " USER@Example.COM ", "a-long-password")

        created = repository.create.await_args.args[0]
        self.assertEqual("Test User", created["FullName"])
        self.assertEqual("user@example.com", created["Email"])
        self.assertTrue(password_hasher.verify(created["PasswordHash"], "a-long-password"))
        self.assertNotIn("PasswordHash", user)
        self.assertTrue(user["IsActive"])

    async def test_register_rejects_duplicate_email(self):
        repository = Mock()
        repository.find_by_email = AsyncMock(return_value={"UserId": "existing"})
        repository.create = AsyncMock()
        service = UserAuthService(repository, settings())

        with self.assertRaises(HTTPException) as raised:
            await service.register("Test", "test@example.com", "a-long-password")

        self.assertEqual(409, raised.exception.status_code)
        repository.create.assert_not_awaited()

    async def test_register_maps_unique_index_race_to_conflict(self):
        repository = Mock()
        repository.find_by_email = AsyncMock(return_value=None)
        repository.create = AsyncMock(side_effect=DuplicateKeyError("duplicate"))
        service = UserAuthService(repository, settings())

        with self.assertRaises(HTTPException) as raised:
            await service.register("Test", "test@example.com", "a-long-password")

        self.assertEqual(409, raised.exception.status_code)

    async def test_login_returns_user_role_token_and_records_last_login(self):
        jwt_settings = settings()
        user = {
            "UserId": "user-1",
            "FullName": "Test",
            "Email": "test@example.com",
            "PasswordHash": password_hasher.hash("a-long-password"),
            "IsActive": True,
            "CreatedAt": None,
            "LastLoginAt": None,
        }
        repository = Mock()
        repository.find_by_email = AsyncMock(return_value=user)
        repository.record_login = AsyncMock(
            return_value={
                key: value
                for key, value in user.items()
                if key != "PasswordHash"
            }
        )
        service = UserAuthService(repository, jwt_settings)

        result = await service.login("TEST@example.com", "a-long-password")
        claims = jwt.decode(
            result["access_token"],
            jwt_settings.jwt_key,
            algorithms=["HS256"],
        )

        self.assertEqual("user", claims["role"])
        self.assertEqual("user-1", claims["UserId"])
        self.assertEqual("Bearer".casefold(), result["token_type"].casefold())
        self.assertNotIn("PasswordHash", result["user"])
        repository.record_login.assert_awaited_once()

    async def test_login_rejects_soft_deleted_account(self):
        user = {
            "UserId": "user-1",
            "PasswordHash": password_hasher.hash("a-long-password"),
            "IsActive": False,
            "IsDeleted": True,
        }
        repository = Mock()
        repository.find_by_email = AsyncMock(return_value=user)
        repository.record_login = AsyncMock()
        service = UserAuthService(repository, settings())

        with self.assertRaises(HTTPException) as raised:
            await service.login("test@example.com", "a-long-password")

        self.assertEqual(401, raised.exception.status_code)
        repository.record_login.assert_not_awaited()

    async def test_login_requires_secure_jwt_configuration(self):
        repository = Mock()
        service = UserAuthService(repository, settings(jwt_key="short"))

        with self.assertRaises(HTTPException) as raised:
            await service.login("test@example.com", "a-long-password")

        self.assertEqual(503, raised.exception.status_code)


if __name__ == "__main__":
    unittest.main()
