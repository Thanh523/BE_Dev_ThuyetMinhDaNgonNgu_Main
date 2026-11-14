from typing import Awaitable, Callable

from pymongo.errors import PyMongoError

from src.repositories.dashboard_repository import DashboardRepository


class DashboardService:
    def __init__(self, repository: DashboardRepository, online_timeout_minutes: int = 5):
        self.repository = repository
        self.online_timeout_minutes = online_timeout_minutes

    async def get_dashboard(self) -> dict:
        access_count, access_error = await self._load_metric(
            self.repository.count_access_events,
        )
        places_count, places_error = await self._load_metric(
            self.repository.count_places,
        )
        narrations_count, narrations_error = await self._load_metric(
            self.repository.count_narrations,
        )
        online_accounts, online_accounts_error = await self._load_metric(
            lambda: self.repository.list_online_accounts(
                self.online_timeout_minutes,
            ),
        )
        usage_by_place, usage_by_place_error = await self._load_metric(
            self.repository.list_usage_by_place,
        )
        usage_by_language, usage_by_language_error = await self._load_metric(
            self.repository.list_usage_by_language,
        )
        return {
            "access_count": access_count,
            "access_error": access_error,
            "places_count": places_count,
            "places_error": places_error,
            "narrations_count": narrations_count,
            "narrations_error": narrations_error,
            "online_accounts_count": len(online_accounts or []),
            "online_accounts": online_accounts or [],
            "online_accounts_error": online_accounts_error,
            "online_timeout_minutes": self.online_timeout_minutes,
            "usage_by_place": usage_by_place or [],
            "usage_by_place_error": usage_by_place_error,
            "usage_by_language": usage_by_language or [],
            "usage_by_language_error": usage_by_language_error,
        }

    async def _load_metric(
        self,
        operation: Callable[[], Awaitable[int | list[dict]]],
    ) -> tuple[int | list[dict] | None, str | None]:
        try:
            return await operation(), None
        except (PyMongoError, KeyError, TypeError, ValueError):
            return None, "Không thể tải số liệu mục này."
