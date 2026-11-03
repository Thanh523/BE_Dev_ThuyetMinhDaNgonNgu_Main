import unittest
from pathlib import Path
from unittest.mock import patch

import jwt
from fastapi import HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials

from src.config.settings import Settings
from src.controllers.auth_controller import LoginRequest, hash_password, login
from src.middlewares.admin_auth import require_admin


class FakeUpdateResult:
    def __init__(self, matched_count):
        self.matched_count = matched_count


class FakeAdminCollection:
    def __init__(self, account):
        self.account = account

    async def find_one(self, query, projection=None):
        identity_matches = any(
            self.account and self.account.get(field) == value
            for item in query.get("$or", [])
            for field, value in item.items()
        )
        if self.account and (
            identity_matches
            or query.get("AdminId") == self.account.get("AdminId")
        ):
            return self.account
        return None

    async def update_one(self, query, update):
        if (
            self.account
            and self.account["AdminId"] == query["AdminId"]
            and self.account["IsActive"] == query["IsActive"]
            and self.account["Role"] == query["Role"]
        ):
            self.account.update(update["$set"])
            return FakeUpdateResult(1)
        return FakeUpdateResult(0)


class FakeDatabase:
    def __init__(self, account):
        self.accounts = FakeAdminCollection(account)
        self.logs = []

    def __getitem__(self, collection_name):
        if collection_name == "AdminAccounts":
            return self.accounts
        return FakeLogCollection(self.logs)


class FakeLogCollection:
    def __init__(self, logs):
        self.logs = logs

    async def insert_one(self, document):
        self.logs.append(document)


class AdminAuthTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.key = "test-signing-key-with-at-least-32-bytes"
        self.settings = Settings(
            mongodb_uri="mongodb://localhost:27017",
            mongodb_database="test",
            places_collection="Places",
            place_images_collection="PlaceImages",
            jwt_key=self.key,
            jwt_algorithm="HS256",
            jwt_role_claim="role",
            jwt_issuer=None,
            jwt_audience=None,
            cors_origins=[],
            image_storage_dir=Path("uploads"),
        )

    async def test_login_returns_eight_hour_admin_jwt_and_updates_account(self):
        account = {
            "AdminId": "admin-id",
            "Username": "admin",
            "Email": "admin@example.com",
            "PasswordHash": hash_password("a-long-admin-password"),
            "Role": "admin",
            "IsActive": True,
        }
        database = FakeDatabase(account)
        with patch("src.controllers.auth_controller.get_settings", return_value=self.settings):
            result = await login(
                LoginRequest(username=" ADMIN@EXAMPLE.COM ", password="a-long-admin-password"),
                database,
            )

        claims = jwt.decode(result.access_token, self.key, algorithms=["HS256"])
        self.assertEqual("admin-id", claims["sub"])
        self.assertEqual("admin-id", claims["AdminId"])
        self.assertEqual("admin", claims["role"])
        self.assertEqual(8 * 60 * 60, result.expires_in)
        self.assertEqual(claims["iat"] + result.expires_in, claims["exp"])
        self.assertIsNotNone(account["LastLoginAt"])
        self.assertEqual("LOGIN", database.logs[0]["Action"])
        self.assertEqual("admin-id", database.logs[0]["AdminId"])

    async def test_login_rejects_wrong_password(self):
        account = {
            "AdminId": "admin-id",
            "Username": "admin",
            "PasswordHash": hash_password("a-long-admin-password"),
            "Role": "admin",
            "IsActive": True,
        }
        with (
            patch("src.controllers.auth_controller.get_settings", return_value=self.settings),
            self.assertRaises(HTTPException) as raised,
        ):
            await login(
                LoginRequest(username="admin", password="wrong-password"),
                FakeDatabase(account),
            )

        self.assertEqual(401, raised.exception.status_code)

    async def test_login_rejects_unknown_username(self):
        with (
            patch("src.controllers.auth_controller.get_settings", return_value=self.settings),
            self.assertRaises(HTTPException) as raised,
        ):
            await login(
                LoginRequest(username="unknown", password="wrong-password"),
                FakeDatabase(None),
            )

        self.assertEqual(401, raised.exception.status_code)

    async def test_login_rejects_inactive_admin(self):
        account = {
            "AdminId": "admin-id",
            "Username": "admin",
            "PasswordHash": hash_password("a-long-admin-password"),
            "Role": "admin",
            "IsActive": False,
        }
        with (
            patch("src.controllers.auth_controller.get_settings", return_value=self.settings),
            self.assertRaises(HTTPException) as raised,
        ):
            await login(
                LoginRequest(username="admin", password="a-long-admin-password"),
                FakeDatabase(account),
            )

        self.assertEqual(401, raised.exception.status_code)

    async def test_admin_token_is_rejected_after_account_deactivation(self):
        account = {
            "AdminId": "admin-id",
            "Role": "admin",
            "IsActive": False,
        }
        token = jwt.encode(
            {
                "sub": "admin-id",
                "AdminId": "admin-id",
                "role": "admin",
                "exp": 4_102_444_800,
            },
            self.key,
            algorithm="HS256",
        )
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=token,
        )

        with (
            patch("src.middlewares.admin_auth.get_settings", return_value=self.settings),
            self.assertRaises(HTTPException) as raised,
        ):
            await require_admin(credentials, FakeDatabase(account))

        self.assertEqual(status.HTTP_401_UNAUTHORIZED, raised.exception.status_code)


if __name__ == "__main__":
    unittest.main()
