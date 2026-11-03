import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from pymongo.errors import PyMongoError

from src.config.database import get_database
from src.config.settings import get_settings
from src.repositories.admin_account_repository import AdminAccountRepository


bearer_scheme = HTTPBearer(auto_error=False)


async def require_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    database=Depends(get_database),
) -> dict:
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

    admin_id = claims.get("AdminId")
    if not isinstance(admin_id, str) or claims.get("sub") != admin_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="****** is invalid or expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        account = await AdminAccountRepository(
            database,
            settings.admin_accounts_collection,
        ).get_authorization_state(
            admin_id,
        )
    except PyMongoError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin account status could not be verified.",
        ) from error

    if not account or not account.get("IsActive", False):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin account is inactive or no longer exists.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    role = account.get("Role")
    token_role = claims.get(settings.jwt_role_claim)
    if (
        not isinstance(role, str)
        or role.casefold() != "admin"
        or not isinstance(token_role, str)
        or token_role.casefold() != role.casefold()
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator role is required.",
        )

    return claims
