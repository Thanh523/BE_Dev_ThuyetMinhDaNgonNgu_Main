from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from pymongo.errors import PyMongoError

from src.config.database import get_database
from src.config.settings import get_settings
from src.middlewares.admin_auth import require_admin
from src.repositories.user_account_repository import UserAccountRepository
from src.services.admin_audit_service import log_admin_activity
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


class UserStatusUpdate(BaseModel):
    is_active: bool


class UserProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    email: str | None = Field(default=None, min_length=3, max_length=254)

    @model_validator(mode="after")
    def validate_profile_fields(self):
        # Không cho gửi payload rỗng hoặc dùng null để xóa thông tin bắt buộc.
        fields = self.model_fields_set
        if not fields or any(getattr(self, field) is None for field in fields):
            raise ValueError("Provide at least one non-null profile field.")
        return self


class SavedPlaceActivity(BaseModel):
    saved_place_id: int | str | None = Field(default=None, alias="SavedPlaceId")
    place_id: int | str = Field(alias="PlaceId")
    saved_at: datetime | None = Field(default=None, alias="SavedAt")


class ListeningHistoryActivity(BaseModel):
    listening_history_id: int | str | None = Field(
        default=None,
        alias="ListeningHistoryId",
    )
    audio_id: int | str = Field(alias="AudioId")
    listened_at: datetime | None = Field(default=None, alias="ListenedAt")
    played_seconds: int | float = Field(alias="PlayedSeconds")
    is_completed: bool = Field(alias="IsCompleted")


class VisitorSessionActivity(BaseModel):
    session_id: int | str = Field(alias="SessionId")
    started_at: datetime | None = Field(default=None, alias="StartedAt")
    last_seen_at: datetime | None = Field(default=None, alias="LastSeenAt")
    ended_at: datetime | None = Field(default=None, alias="EndedAt")


class UsageEventActivity(BaseModel):
    event_id: int | str | None = Field(default=None, alias="EventId")
    client_event_id: str | None = Field(default=None, alias="ClientEventId")
    session_id: int | str = Field(alias="SessionId")
    narration_id: int | str | None = Field(default=None, alias="NarrationId")
    audio_id: int | str | None = Field(default=None, alias="AudioId")
    event_type: str = Field(alias="EventType")
    created_at: datetime | None = Field(default=None, alias="CreatedAt")


class UserActivityView(BaseModel):
    user: UserView
    saved_places: list[SavedPlaceActivity]
    saved_places_total: int
    listening_history: list[ListeningHistoryActivity]
    listening_history_total: int
    visitor_sessions: list[VisitorSessionActivity]
    visitor_sessions_total: int
    usage_events: list[UsageEventActivity]
    usage_events_total: int


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


@router.patch("/{user_id}/status", response_model=UserView)
async def update_user_status(
    user_id: str,
    request: UserStatusUpdate,
    database=Depends(get_database),
    admin_claims: dict = Depends(require_admin),
) -> dict:
    # Khóa hoặc mở tài khoản theo IsActive rồi ghi lại thao tác vào nhật ký admin.
    user = await _service(database).update_status(user_id, request.is_active)
    settings = get_settings()
    action = "ACTIVATE" if request.is_active else "DEACTIVATE"
    status_text = "activated" if request.is_active else "deactivated"
    try:
        await log_admin_activity(
            database,
            settings.admin_activity_logs_collection,
            admin_id=admin_claims["AdminId"],
            action=action,
            entity_name="UserAccounts",
            entity_id=str(user["UserId"]),
            description=f"User account {status_text}.",
        )
    except PyMongoError as error:
        raise HTTPException(
            status_code=503,
            detail=(
                "The user status changed, but its activity log could not be "
                "saved. Contact an administrator before retrying."
            ),
        ) from error
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    database=Depends(get_database),
    admin_claims: dict = Depends(require_admin),
) -> None:
    # Xóa mềm user khi không có dữ liệu liên quan rồi ghi lại thao tác admin.
    await _service(database).delete_user(user_id)
    settings = get_settings()
    try:
        await log_admin_activity(
            database,
            settings.admin_activity_logs_collection,
            admin_id=admin_claims["AdminId"],
            action="DELETE",
            entity_name="UserAccounts",
            entity_id=user_id,
            description="Soft-deleted user account; user data was retained.",
        )
    except PyMongoError as error:
        raise HTTPException(
            status_code=503,
            detail=(
                "The user account was disabled, but its activity log could not "
                "be saved. Contact an administrator before retrying."
            ),
        ) from error


@router.patch("/{user_id}", response_model=UserView)
async def update_user_profile(
    user_id: str,
    request: UserProfileUpdate,
    database=Depends(get_database),
    admin_claims: dict = Depends(require_admin),
) -> dict:
    # Cập nhật các trường hồ sơ được phép và ghi nhật ký admin.
    user = await _service(database).update_profile(
        user_id,
        request.full_name,
        request.email,
    )
    settings = get_settings()
    try:
        await log_admin_activity(
            database,
            settings.admin_activity_logs_collection,
            admin_id=admin_claims["AdminId"],
            action="UPDATE",
            entity_name="UserAccounts",
            entity_id=str(user["UserId"]),
            description="Updated user profile.",
        )
    except PyMongoError as error:
        raise HTTPException(
            status_code=503,
            detail=(
                "The user profile was updated, but its activity log could not "
                "be saved. Contact an administrator before retrying."
            ),
        ) from error
    return user


@router.get("/{user_id}/activity", response_model=UserActivityView)
async def get_user_activity(
    user_id: str,
    limit: int = Query(default=20, ge=1, le=50),
    database=Depends(get_database),
) -> dict:
    # Trả các hoạt động gần đây cùng tổng số; chỉ đọc và giới hạn kết quả.
    return await _service(database).get_activity(user_id, limit)
