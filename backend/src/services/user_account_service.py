import uuid
from datetime import datetime, timezone
import re

from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError, PyMongoError

from src.repositories.user_account_repository import UserAccountRepository
from src.services.admin_auth_service import hash_password


class UserAccountService:
    def __init__(self, repository: UserAccountRepository):
        self.repository = repository

    # Chuyển yêu cầu danh sách xuống repository và đổi lỗi database thành HTTP 503.
    async def list_users(
        self,
        search: str,
        is_active: bool | None,
        skip: int,
        limit: int,
    ) -> tuple[list[dict], int]:
        try:
            return await self.repository.list(search, is_active, skip, limit)
        except PyMongoError as error:
            raise HTTPException(
                status_code=503,
                detail="User list is temporarily unavailable.",
            ) from error

    # Cập nhật trạng thái tài khoản; báo 404 nếu UserId không tồn tại.
    async def update_status(self, user_id: str, is_active: bool) -> dict:
        try:
            user = await self.repository.update_status(user_id, is_active)
        except PyMongoError as error:
            raise HTTPException(
                status_code=503,
                detail="User account status could not be updated.",
            ) from error
        if user is None:
            raise HTTPException(status_code=404, detail="User account was not found.")
        return user

    # Chuẩn hóa và kiểm tra họ tên/email trước khi ghi hồ sơ user.
    async def update_profile(
        self,
        user_id: str,
        full_name: str | None,
        email: str | None,
    ) -> dict:
        changes: dict = {}
        if full_name is not None:
            normalized_name = full_name.strip()
            if not normalized_name:
                raise HTTPException(status_code=422, detail="Full name is required.")
            changes["FullName"] = normalized_name

        if email is not None:
            normalized_email = email.strip().casefold()
            if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", normalized_email):
                raise HTTPException(status_code=422, detail="Email address is invalid.")
            changes["Email"] = normalized_email

        if not changes:
            raise HTTPException(
                status_code=422,
                detail="At least one profile field must be provided.",
            )

        try:
            if "Email" in changes and await self.repository.email_exists(
                changes["Email"],
                user_id,
            ):
                raise HTTPException(
                    status_code=409,
                    detail="Email address is already used by another account.",
                )
            user = await self.repository.update_profile(user_id, changes)
        except DuplicateKeyError as error:
            raise HTTPException(
                status_code=409,
                detail="Email address is already used by another account.",
            ) from error
        except PyMongoError as error:
            raise HTTPException(
                status_code=503,
                detail="User profile could not be updated.",
            ) from error

        if user is None:
            raise HTTPException(status_code=404, detail="User account was not found.")
        return user

    # Lấy lịch sử địa điểm đã lưu và nghe audio của một user.
    async def get_activity(self, user_id: str, limit: int) -> dict:
        try:
            activity = await self.repository.get_activity(user_id, limit)
        except PyMongoError as error:
            raise HTTPException(
                status_code=503,
                detail="User activity is temporarily unavailable.",
            ) from error
        if activity is None:
            raise HTTPException(status_code=404, detail="User account was not found.")
        return activity

    # Xóa user chỉ khi không còn bản ghi liên quan để tránh làm mất lịch sử.
    async def delete_user(self, user_id: str) -> None:
        try:
            result = await self.repository.delete_if_unrelated(user_id)
        except PyMongoError as error:
            raise HTTPException(
                status_code=503,
                detail="User account could not be deleted.",
            ) from error
        if result is None:
            raise HTTPException(status_code=404, detail="User account was not found.")
        if not result["deleted"]:
            related = ", ".join(
                f"{name}: {count}"
                for name, count in result["related_counts"].items()
                if count
            )
            raise HTTPException(
                status_code=409,
                detail=(
                    "User account cannot be deleted while related activity "
                    f"records exist ({related})."
                ),
            )

    # Tạo user tạm để admin có dữ liệu kiểm thử các chức năng quản lý.
    async def create_user(self, full_name: str, email: str, password: str) -> dict:
        normalized_name = full_name.strip()
        normalized_email = email.strip().casefold()
        if not normalized_name:
            raise HTTPException(status_code=422, detail="Full name is required.")
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", normalized_email):
            raise HTTPException(status_code=422, detail="Email address is invalid.")
        if len(password) < 12:
            raise HTTPException(
                status_code=422,
                detail="Password must contain at least 12 characters.",
            )
        if len(password) > 128:
            raise HTTPException(
                status_code=422,
                detail="Password must be no longer than 128 characters.",
            )

        user_id = uuid.uuid4().hex
        try:
            if await self.repository.email_exists(normalized_email):
                raise HTTPException(
                    status_code=409,
                    detail="Email address is already used by another account.",
                )
            user = {
                "UserId": user_id,
                "FullName": normalized_name,
                "Email": normalized_email,
                "PasswordHash": hash_password(password),
                "IsActive": True,
                "CreatedAt": datetime.now(timezone.utc),
                "LastLoginAt": None,
            }
            await self.repository.create(user)
        except DuplicateKeyError as error:
            raise HTTPException(
                status_code=409,
                detail="Email address is already used by another account.",
            ) from error
        except PyMongoError as error:
            raise HTTPException(
                status_code=503,
                detail="User account could not be created.",
            ) from error

        return {
            "UserId": user_id,
            "FullName": normalized_name,
            "Email": normalized_email,
            "IsActive": True,
            "CreatedAt": user["CreatedAt"],
            "LastLoginAt": None,
        }
