from datetime import datetime, timedelta, timezone
from typing import Any


class DashboardRepository:
    def __init__(self, database: Any, settings: Any):
        self.places = database[settings.places_collection]
        self.narrations = database[settings.narrations_collection]
        self.usage_events = database[settings.usage_events_collection]
        self.listening_history = database[settings.listening_history_collection]
        self.audios = database[settings.audio_collection]
        self.languages = database[settings.languages_collection]
        self.visitor_sessions = database[settings.visitor_sessions_collection]
        self.user_accounts = database[settings.user_accounts_collection]

    async def count_access_events(self) -> int:
        return await self.usage_events.count_documents({})

    async def count_places(self) -> int:
        return await self.places.count_documents({})

    async def count_narrations(self) -> int:
        return await self.narrations.count_documents({})

    async def list_online_accounts(self, timeout_minutes: int) -> list[dict]:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=timeout_minutes)
        cursor = self.visitor_sessions.find(
            {
                "EndedAt": None,
                "LastSeenAt": {"$gte": cutoff},
            },
            {
                "_id": 0,
                "UserId": 1,
                "LastSeenAt": 1,
            },
        ).sort("LastSeenAt", -1)
        sessions = await cursor.to_list(length=None)
        user_ids = list({str(session["UserId"]) for session in sessions})
        if not user_ids:
            return []

        accounts = await self.user_accounts.find(
            {"UserId": {"$in": user_ids}, "IsActive": True},
            {
                "_id": 0,
                "UserId": 1,
                "FullName": 1,
                "Email": 1,
            },
        ).to_list(length=None)
        accounts_by_id = {str(account["UserId"]): account for account in accounts}
        online: list[dict] = []
        seen_users: set[str] = set()
        for session in sessions:
            user_id = str(session["UserId"])
            if user_id in seen_users:
                continue
            seen_users.add(user_id)
            account = accounts_by_id.get(user_id)
            if account is None:
                continue
            online.append(
                {
                    "user_id": str(session["UserId"]),
                    "full_name": account.get("FullName") or "Tài khoản không tên",
                    "email": account.get("Email") or "Không có email",
                    "last_seen_at": session.get("LastSeenAt"),
                }
            )
        return online

    async def list_usage_by_place(self) -> list[dict]:
        places = await self.places.find(
            {},
            {"_id": 0, "PlaceId": 1, "PlaceName": 1},
        ).sort("PlaceName", 1).to_list(length=None)
        usage_cursor = await self.listening_history.aggregate(
            [
                {
                    "$group": {
                        "_id": "$PlaceId",
                        "count": {"$sum": 1},
                    }
                }
            ]
        )
        usage = await usage_cursor.to_list(length=None)
        counts = {str(item["_id"]): item["count"] for item in usage}
        return [
            {
                "place_id": place["PlaceId"],
                "place_name": place.get("PlaceName") or "Không có tên",
                "count": counts.get(str(place["PlaceId"]), 0),
            }
            for place in places
        ]

    async def list_usage_by_language(self) -> list[dict]:
        languages = await self.languages.find(
            {
                "$or": [
                    {"IsActive": True},
                    {"IsActive": {"$exists": False}},
                ],
            },
            {"_id": 0, "LanguageCode": 1, "LanguageName": 1},
        ).sort("LanguageCode", 1).to_list(length=None)
        usage_cursor = await self.listening_history.aggregate(
            [
                {
                    "$lookup": {
                        "from": self.audios.name,
                        "localField": "AudioId",
                        "foreignField": "AudioId",
                        "as": "audio",
                    }
                },
                {"$unwind": "$audio"},
                {
                    "$group": {
                        "_id": "$audio.Language",
                        "count": {"$sum": 1},
                    }
                },
            ]
        )
        usage = await usage_cursor.to_list(length=None)
        counts = {
            str(item["_id"]): item["count"]
            for item in usage
            if item.get("_id")
        }
        result = [
            {
                "language_code": language["LanguageCode"],
                "language_name": language.get("LanguageName")
                or language["LanguageCode"],
                "count": counts.pop(language["LanguageCode"], 0),
            }
            for language in languages
        ]
        result.extend(
            {
                "language_code": code,
                "language_name": code,
                "count": count,
            }
            for code, count in sorted(counts.items())
        )
        return result
