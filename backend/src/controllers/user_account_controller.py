from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field

from src.config.database import get_database
from src.config.settings import get_settings
from src.middlewares.admin_auth import require_admin
from src.repositories.user_account_repository import UserAccountRepository
from src.services.user_account_service import UserAccountService


# Gom API quản lý user; mọi endpoint trong router đều yêu cầu admin đăng nhập.
router = APIRouter(
    prefix="/api/admin/users",
    tags=["User management"],
    dependencies=[Depends(require_admin)],
)


# Các trường được phép trả về frontend; không đưa PasswordHash ra API.
class UserView(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    user_id: int | str = Field(alias="UserId")
    full_name: str = Field(alias="FullName")
    email: str = Field(alias="Email")
    is_active: bool = Field(alias="IsActive")
    created_at: datetime | None = Field(default=None, alias="CreatedAt")
    last_login_at: datetime | None = Field(default=None, alias="LastLoginAt")


class UserPage(BaseModel):
    # Trả danh sách cùng tổng số bản ghi để frontend hiển thị phân trang.
    items: list[UserView]
    total: int
    skip: int
    limit: int


def _service(database) -> UserAccountService:
    # Tạo service và repository cho request hiện tại.
    return UserAccountService(
        UserAccountRepository(database, get_settings()),
    )


@router.get("", response_model=UserPage)
async def list_users(
    # Tham số lọc và phân trang của danh sách user.
    search: str = Query(default="", max_length=200),
    is_active: bool | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    database=Depends(get_database),
) -> dict:
    # Chuyển yêu cầu xuống service xử lý nghiệp vụ và truy vấn dữ liệu.
    items, total = await _service(database).list_users(
        search,
        is_active,
        skip,
        limit,
    )
    return {"items": items, "total": total, "skip": skip, "limit": limit}
