import unittest
from unittest.mock import AsyncMock, Mock, patch

from src.controllers.user_auth_controller import (
    UserPasswordChange,
    UserProfileUpdate,
    change_current_user_password,
    update_current_user,
)


class UserAuthControllerTests(unittest.IsolatedAsyncioTestCase):
    @patch("src.controllers.user_auth_controller._account_service")
    async def test_profile_update_uses_user_id_from_authenticated_claims(
        self,
        account_service_factory,
    ):
        account_service = Mock()
        account_service.update_profile = AsyncMock(
            return_value={
                "UserId": "user-1",
                "FullName": "Updated Name",
                "Email": "user@example.com",
                "IsActive": True,
            }
        )
        account_service_factory.return_value = account_service

        result = await update_current_user(
            request=UserProfileUpdate(full_name="Updated Name"),
            database=object(),
            claims={"UserId": "user-1"},
        )

        account_service.update_profile.assert_awaited_once_with(
            "user-1",
            "Updated Name",
            None,
        )
        self.assertEqual("Updated Name", result["FullName"])

    @patch("src.controllers.user_auth_controller._service")
    async def test_password_change_uses_authenticated_user_id(
        self,
        auth_service_factory,
    ):
        auth_service = Mock()
        auth_service.change_password = AsyncMock()
        auth_service_factory.return_value = auth_service

        await change_current_user_password(
            request=UserPasswordChange(
                current_password="current-password",
                new_password="a-new-long-password",
            ),
            database=object(),
            claims={"UserId": "user-1"},
        )

        auth_service.change_password.assert_awaited_once_with(
            "user-1",
            "current-password",
            "a-new-long-password",
        )


if __name__ == "__main__":
    unittest.main()
