from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import HTTPException, status
from pymongo.errors import PyMongoError

from src.config.settings import Settings
from src.repositories.admin_account_repository import AdminAccountRepository
from src.services.admin_activity_service import AdminActivityService


ACCESS_TOKEN_LIFETIME = timedelta(hours=8)
password_hasher = PasswordHasher()
dummy_password_hash = password_hasher.hash("not-a-real-admin-password")


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


class AdminAuthService:
    def __init__(
        self,
        accounts: AdminAccountRepository,
        activity: AdminActivityService,
        settings: Settings,
    ):
        self.accounts = accounts
        self.activity = activity
        self.settings = settings

    async def login(self, username: str, password: str) -> dict:
        settings = self.settings
        if not settings.jwt_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="JWT_KEY is not configured.",
            )
        if (
            settings.jwt_algorithm == "HS256"
            and len(settings.jwt_key.encode("utf-8")) < 32
        ):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="JWT_KEY must be at least 32 bytes for HS256.",
            )

        login_name = username.strip().casefold()
        if not login_name:
            raise self._invalid_credentials()
        try:
            account = await self.accounts.find_for_login(login_name)
        except PyMongoError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Admin authentication is temporarily unavailable.",
            ) from error

        stored_hash = (
            account.get("PasswordHash")
            if account and isinstance(account.get("PasswordHash"), str)
            else dummy_password_hash
        )
        try:
            password_valid = password_hasher.verify(stored_hash, password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            password_valid = False

        if (
            not account
            or not isinstance(account.get("PasswordHash"), str)
            or not account.get("IsActive", False)
            or not isinstance(account.get("Role"), str)
            or account.get("Role", "").casefold() != "admin"
            or not password_valid
        ):
            raise self._invalid_credentials()

        now = datetime.now(timezone.utc)
        try:
            if not await self.accounts.record_login(account["AdminId"], now):
                raise self._invalid_credentials()
            await self.activity.log(
                admin_id=account["AdminId"],
                action="LOGIN",
                entity_name="AdminAccounts",
                entity_id=account["AdminId"],
                description="Admin signed in.",
            )
        except PyMongoError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Admin login could not be recorded.",
            ) from error

        claims = {
            "sub": account["AdminId"],
            "AdminId": account["AdminId"],
            settings.jwt_role_claim: account["Role"],
            "iat": now,
            "exp": now + ACCESS_TOKEN_LIFETIME,
        }
        if settings.jwt_issuer:
            claims["iss"] = settings.jwt_issuer
        if settings.jwt_audience:
            claims["aud"] = settings.jwt_audience

        try:
            token = jwt.encode(
                claims,
                settings.jwt_key,
                algorithm=settings.jwt_algorithm,
            )
        except (jwt.PyJWTError, TypeError, ValueError) as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="JWT signing configuration is invalid.",
            ) from error
        return {
            "access_token": token,
            "token_type": "bearer",
            "expires_in": int(ACCESS_TOKEN_LIFETIME.total_seconds()),
        }

    @staticmethod
    def _invalid_credentials() -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
