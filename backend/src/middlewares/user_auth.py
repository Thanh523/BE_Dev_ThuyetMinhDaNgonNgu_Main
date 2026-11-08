import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from jwt import InvalidTokenError
from pymongo.errors import PyMongoError

from src.config.database import get_database
from src.config.settings import get_settings
from src.middlewares.admin_auth import bearer_scheme
from src.repositories.user_auth_repository import UserAuthRepository


async def require_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    database=Depends(get_database),
) -> dict:
    # Bước 1: yêu cầu Bearer token và kiểm tra cấu hình khóa ký.
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    settings = get_settings()
    if not settings.jwt_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="JWT_KEY is not configured.",
        )
    # Bước 2: xác minh chữ ký, thời hạn và issuer/audience nếu đã cấu hình.
    try:
        claims = jwt.decode(
            credentials.credentials,
            settings.jwt_key,
            algorithms=[settings.jwt_algorithm],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            options={"require": ["exp"]},
        )
    except InvalidTokenError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token is invalid or expired.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error

    # Bước 3: chỉ nhận token có role user; token admin không được dùng ở API user.
    user_id = claims.get("UserId")
    role = claims.get(settings.jwt_role_claim)
    if (
        not isinstance(user_id, str)
        or claims.get("sub") != user_id
        or not isinstance(role, str)
        or role.casefold() != "user"
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token is invalid or expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # Bước 4: kiểm tra trạng thái mới nhất trong DB để khóa/xóa thu hồi quyền tức thời.
    try:
        user = await UserAuthRepository(
            database,
            settings.user_accounts_collection,
        ).get_authorization_state(user_id)
    except PyMongoError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="User account status could not be verified.",
        ) from error
    if not user or not user.get("IsActive", False) or user.get("IsDeleted", False):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive or no longer exists.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return claims
