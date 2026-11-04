from fastapi import HTTPException
from pymongo.errors import PyMongoError

from src.repositories.user_account_repository import UserAccountRepository


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
