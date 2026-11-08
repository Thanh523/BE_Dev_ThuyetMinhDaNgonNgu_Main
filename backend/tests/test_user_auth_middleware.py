from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest
from unittest.mock import AsyncMock, patch

import jwt
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from src.config.settings import Settings
from src.middlewares.admin_auth import require_admin
from src.middlewares.user_auth import require_user


def settings():
    return Settings(
        mongodb_uri="mongodb://localhost:27017",
        mongodb_database="test",
        places_collection="Places",
        place_images_collection="PlaceImages",
        jwt_key="x" * 48,
        jwt_algorithm="HS256",
        jwt_role_claim="role",
        jwt_issuer=None,
        jwt_audience=None,
        cors_origins=[],
        image_storage_dir=Path("uploads"),
    )


def credentials(role="user", user_id="user-1"):
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": user_id,
            "UserId": user_id,
            "role": role,
            "iat": now,
            "exp": now + timedelta(hours=1),
        },
        settings().jwt_key,
        algorithm="HS256",
    )
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


class UserCollection:
    def __init__(self, account):
        self.account = account
        self.query = None

    async def find_one(self, query, projection):
        self.query = query
        if self.account.get("UserId") != query.get("UserId"):
            return None
        return {
            key: value
            for key, value in self.account.items()
            if projection.get(key, 0)
        }


class Database:
    def __init__(self, users):
        self.users = users

    def __getitem__(self, name):
        if name != "UserAccounts":
            raise AssertionError(f"Unexpected collection: {name}")
        return self.users


class UserAuthMiddlewareTests(unittest.IsolatedAsyncioTestCase):
    async def test_user_token_is_accepted_for_active_account(self):
        database = Database(UserCollection({"UserId": "user-1", "IsActive": True}))
        with patch("src.middlewares.user_auth.get_settings", return_value=settings()):
            claims = await require_user(credentials(), database)

        self.assertEqual("user-1", claims["UserId"])

    async def test_soft_deleted_user_token_is_rejected(self):
        database = Database(
            UserCollection(
                {"UserId": "user-1", "IsActive": False, "IsDeleted": True}
            )
        )
        with patch("src.middlewares.user_auth.get_settings", return_value=settings()):
            with self.assertRaises(HTTPException) as raised:
                await require_user(credentials(), database)

        self.assertEqual(401, raised.exception.status_code)

    async def test_admin_role_token_is_not_accepted_as_user(self):
        database = Database(UserCollection({"UserId": "user-1", "IsActive": True}))
        with patch("src.middlewares.user_auth.get_settings", return_value=settings()):
            with self.assertRaises(HTTPException) as raised:
                await require_user(credentials(role="admin"), database)

        self.assertEqual(401, raised.exception.status_code)

    async def test_user_token_is_not_accepted_by_admin_guard(self):
        with patch("src.middlewares.admin_auth.get_settings", return_value=settings()):
            with self.assertRaises(HTTPException) as raised:
                await require_admin(credentials(), AsyncMock())

        self.assertEqual(401, raised.exception.status_code)


if __name__ == "__main__":
    unittest.main()
