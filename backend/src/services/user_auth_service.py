import re
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import HTTPException, status
from pymongo.errors import DuplicateKeyError, PyMongoError

from src.config.settings import Settings
from src.repositories.user_auth_repository import UserAuthRepository


ACCESS_TOKEN_LIFETIME = timedelta(hours=8)
password_hasher = PasswordHasher()
# Dùng hash giả khi email không tồn tại để giảm khác biệt thời gian phản hồi đăng nhập.
dummy_password_hash = password_hasher.hash("not-a-real-user-password")


class UserAuthService:
    def __init__(self, repository: UserAuthRepository, settings: Settings):
        self.repository = repository
        self.settings = settings

    async def register(self, full_name: str, email: str, password: str) -> dict:
        # Chuẩn hóa và xác thực đầu vào trước khi lưu tài khoản mới.
        normalized_name = full_name.strip()
        normalized_email = email.strip().casefold()
        if not normalized_name:
            raise HTTPException(status_code=422, detail="Full name is required.")
        if len(normalized_name) > 200:
            raise HTTPException(
                status_code=422,
                detail="Full name must be no longer than 200 characters.",
            )
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", normalized_email):
            raise HTTPException(status_code=422, detail="Email address is invalid.")
        if len(normalized_email) > 254:
            raise HTTPException(
                status_code=422,
                detail="Email address must be no longer than 254 characters.",
            )
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

        try:
            # Kiểm tra sớm giúp trả lỗi dễ hiểu; unique index vẫn chặn đăng ký đồng thời.
            if await self.repository.find_by_email(normalized_email):
                raise HTTPException(
                    status_code=409,
                    detail="Email address is already registered.",
                )
            now = datetime.now(timezone.utc)
            user = {
                "UserId": uuid.uuid4().hex,
                "FullName": normalized_name,
                "Email": normalized_email,
                "PasswordHash": password_hasher.hash(password),
                "IsActive": True,
                "IsDeleted": False,
                "CreatedAt": now,
                "LastLoginAt": None,
            }
            await self.repository.create(user)
        except DuplicateKeyError as error:
            raise HTTPException(
                status_code=409,
                detail="Email address is already registered.",
            ) from error
        except PyMongoError as error:
            raise HTTPException(
                status_code=503,
                detail="User registration is temporarily unavailable.",
            ) from error
        return self._public_user(user)

    async def login(self, email: str, password: str) -> dict:
        # Không cho phát hành token nếu khóa ký JWT chưa được cấu hình an toàn.
        self._validate_jwt_configuration()
        normalized_email = email.strip().casefold()
        try:
            user = await self.repository.find_by_email(normalized_email)
        except PyMongoError as error:
            raise HTTPException(
                status_code=503,
                detail="User authentication is temporarily unavailable.",
            ) from error

        # Luôn kiểm tra một hash hợp lệ, kể cả khi email không tìm thấy.
        stored_hash = (
            user.get("PasswordHash")
            if user and isinstance(user.get("PasswordHash"), str)
            else dummy_password_hash
        )
        try:
            password_valid = password_hasher.verify(stored_hash, password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            password_valid = False

        if (
            not user
            or not user.get("IsActive", False)
            or user.get("IsDeleted", False)
            or not password_valid
        ):
            raise self._invalid_credentials()

        # Ghi LastLoginAt có điều kiện để khóa/xóa tài khoản chen ngang không cấp token.
        user_id = str(user["UserId"])
        now = datetime.now(timezone.utc)
        try:
            public_user = await self.repository.record_login(user_id, now)
        except PyMongoError as error:
            raise HTTPException(
                status_code=503,
                detail="User login could not be recorded.",
            ) from error
        if public_user is None:
            raise self._invalid_credentials()

        # Role "user" tách biệt với JWT "admin" dù cùng dùng khóa ký.
        claims = {
            "sub": user_id,
            "UserId": user_id,
            self.settings.jwt_role_claim: "user",
            "iat": now,
            "exp": now + ACCESS_TOKEN_LIFETIME,
        }
        if self.settings.jwt_issuer:
            claims["iss"] = self.settings.jwt_issuer
        if self.settings.jwt_audience:
            claims["aud"] = self.settings.jwt_audience
        try:
            token = jwt.encode(
                claims,
                self.settings.jwt_key,
                algorithm=self.settings.jwt_algorithm,
            )
        except (jwt.PyJWTError, TypeError, ValueError) as error:
            raise HTTPException(
                status_code=503,
                detail="JWT signing configuration is invalid.",
            ) from error
        return {
            "access_token": token,
            "token_type": "bearer",
            "expires_in": int(ACCESS_TOKEN_LIFETIME.total_seconds()),
            "user": self._public_user(public_user),
        }

    def _validate_jwt_configuration(self) -> None:
        if not self.settings.jwt_key:
            raise HTTPException(
                status_code=503,
                detail="JWT_KEY is not configured.",
            )
        if (
            self.settings.jwt_algorithm == "HS256"
            and len(self.settings.jwt_key.encode("utf-8")) < 32
        ):
            raise HTTPException(
                status_code=503,
                detail="JWT_KEY must be at least 32 bytes for HS256.",
            )

    @staticmethod
    def _public_user(user: dict) -> dict:
        # Chỉ trả các trường hồ sơ công khai; tuyệt đối không trả PasswordHash.
        return {
            key: user[key]
            for key in (
                "UserId",
                "FullName",
                "Email",
                "IsActive",
                "CreatedAt",
                "LastLoginAt",
            )
            if key in user
        }

    @staticmethod
    def _invalid_credentials() -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
