from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from pymongo.errors import PyMongoError

from src.config.database import get_database
from src.config.settings import get_settings
from src.repositories.admin_account_repository import AdminAccountRepository
from src.repositories.admin_activity_repository import AdminActivityRepository
from src.services.admin_activity_service import AdminActivityService
from src.services.admin_auth_service import (
    AdminAuthService,
    hash_password as hash_password,
)

router = APIRouter(prefix="/api/admin/auth", tags=["Admin authentication"])


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


def _service(database) -> AdminAuthService:
    settings = get_settings()
    accounts = AdminAccountRepository(database, settings.admin_accounts_collection)
    activity = AdminActivityService(
        AdminActivityRepository(database, settings.admin_activity_logs_collection),
    )
    return AdminAuthService(accounts, activity, settings)


@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: LoginRequest,
    database=Depends(get_database),
) -> TokenResponse:
    try:
        result = await _service(database).login(
            credentials.username,
            credentials.password,
        )
    except PyMongoError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin login could not be recorded.",
        ) from error
    return TokenResponse(**result)
