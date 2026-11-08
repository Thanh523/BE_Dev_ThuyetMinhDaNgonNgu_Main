from datetime import datetime
import re

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pymongo.errors import PyMongoError

from src.config.database import get_database
from src.config.settings import get_settings
from src.middlewares.user_auth import require_user
from src.repositories.user_auth_repository import UserAuthRepository
from src.repositories.user_account_repository import UserAccountRepository
from src.services.user_account_service import UserAccountService
from src.services.user_auth_service import UserAuthService


router = APIRouter(prefix="/api/user/auth", tags=["User authentication"])


# Payload đăng ký/đăng nhập được giới hạn tại biên API trước khi gọi service.
class UserRegister(BaseModel):
    full_name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value.strip()):
            raise ValueError("Email address is invalid.")
        return value


class UserLogin(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value.strip()):
            raise ValueError("Email address is invalid.")
        return value


class UserProfileUpdate(BaseModel):
    full_name: str = Field(min_length=1, max_length=200)


class UserPasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)


class UserView(BaseModel):
    # Danh sách cho phép này đảm bảo PasswordHash không xuất hiện trong response.
    model_config = ConfigDict(populate_by_name=True)

    user_id: str = Field(alias="UserId")
    full_name: str = Field(alias="FullName")
    email: str = Field(alias="Email")
    is_active: bool = Field(alias="IsActive")
    created_at: datetime | None = Field(default=None, alias="CreatedAt")
    last_login_at: datetime | None = Field(default=None, alias="LastLoginAt")


def _service(database) -> UserAuthService:
    # Giữ controller mỏng: tạo dependency theo từng request rồi giao nghiệp vụ cho service.
    settings = get_settings()
    return UserAuthService(
        UserAuthRepository(database, settings.user_accounts_collection),
        settings,
    )


def _account_service(database) -> UserAccountService:
    return UserAccountService(
        UserAccountRepository(database, get_settings()),
    )


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=UserView)
async def register(request: UserRegister, database=Depends(get_database)) -> dict:
    # Đăng ký công khai; tài khoản được kích hoạt ngay, chưa có bước xác minh email.
    return await _service(database).register(
        request.full_name,
        str(request.email),
        request.password,
    )


@router.post("/login")
async def login(request: UserLogin, database=Depends(get_database)) -> dict:
    # Service xác thực mật khẩu, cập nhật LastLoginAt và cấp JWT role=user.
    return await _service(database).login(str(request.email), request.password)


@router.get("/me", response_model=UserView)
async def get_current_user(
    database=Depends(get_database),
    claims: dict = Depends(require_user),
) -> dict:
    # Chỉ đọc hồ sơ của UserId lấy từ token đã qua require_user.
    settings = get_settings()
    try:
        user = await UserAuthRepository(
            database,
            settings.user_accounts_collection,
        ).get_profile(claims["UserId"])
    except PyMongoError as error:
        raise HTTPException(
            status_code=503,
            detail="User profile is temporarily unavailable.",
        ) from error
    if user is None:
        raise HTTPException(status_code=404, detail="User account was not found.")
    return user


@router.patch("/me", response_model=UserView)
async def update_current_user(
    request: UserProfileUpdate,
    database=Depends(get_database),
    claims: dict = Depends(require_user),
) -> dict:
    # Lấy UserId từ token để user chỉ có thể chỉnh sửa hồ sơ của chính mình.
    return await _account_service(database).update_profile(
        claims["UserId"],
        request.full_name,
        None,
    )


@router.patch("/me/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_current_user_password(
    request: UserPasswordChange,
    database=Depends(get_database),
    claims: dict = Depends(require_user),
) -> None:
    # Yêu cầu mật khẩu hiện tại để chỉ chủ tài khoản đã xác thực mới đổi được mật khẩu.
    await _service(database).change_password(
        claims["UserId"],
        request.current_password,
        request.new_password,
    )
