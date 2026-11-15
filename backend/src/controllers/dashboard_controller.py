import logging
from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ValidationError

from src.config.database import get_database
from src.config.settings import get_settings
from src.middlewares.admin_auth import require_admin
from src.repositories.dashboard_repository import DashboardRepository
from src.services.dashboard_service import DashboardService


router = APIRouter(
    prefix="/api/admin",
    tags=["Dashboard"],
    dependencies=[Depends(require_admin)],
)
logger = logging.getLogger(__name__)


class DashboardPlaceUsage(BaseModel):
    place_id: int | str
    place_name: str
    count: int


class DashboardLanguageUsage(BaseModel):
    language_code: str
    language_name: str
    count: int


class DashboardOnlineAccount(BaseModel):
    user_id: int | str
    full_name: str
    email: str
    last_seen_at: datetime | None


class DashboardView(BaseModel):
    access_count: int | None
    access_error: str | None
    places_count: int | None
    places_error: str | None
    narrations_count: int | None
    narrations_error: str | None
    online_accounts_count: int
    online_accounts: list[DashboardOnlineAccount]
    online_accounts_error: str | None
    online_guests_count: int | None
    online_guests_error: str | None
    online_visitors_count: int | None
    online_visitors_error: str | None
    online_timeout_minutes: int
    usage_by_place: list[DashboardPlaceUsage]
    usage_by_place_error: str | None
    usage_by_language: list[DashboardLanguageUsage]
    usage_by_language_error: str | None


@router.get("/dashboard", response_model=DashboardView)
async def get_dashboard(
    access_from: date | None = Query(default=None),
    access_to: date | None = Query(default=None),
    database=Depends(get_database),
) -> dict:
    if access_from and access_to and access_from > access_to:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="The start date must be on or before the end date.",
        )

    vietnam_timezone = timezone(timedelta(hours=7))
    access_start_at = (
        datetime.combine(access_from, time.min, tzinfo=vietnam_timezone)
        .astimezone(timezone.utc)
        if access_from
        else None
    )
    access_end_at = (
        datetime.combine(
            access_to + timedelta(days=1),
            time.min,
            tzinfo=vietnam_timezone,
        ).astimezone(timezone.utc)
        if access_to
        else None
    )
    settings = get_settings()
    service = DashboardService(
        DashboardRepository(database, settings),
        settings.online_session_timeout_minutes,
    )
    try:
        result = await service.get_dashboard(access_start_at, access_end_at)
        return DashboardView.model_validate(result).model_dump()
    except (ValidationError, KeyError, TypeError, ValueError) as error:
        logger.exception("Dashboard response could not be built: %s", error)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Dashboard data could not be loaded.",
        ) from error
