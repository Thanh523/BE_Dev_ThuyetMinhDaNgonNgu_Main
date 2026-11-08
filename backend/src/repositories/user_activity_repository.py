from datetime import datetime
from typing import Any
import uuid

from pymongo import ReturnDocument


class UserActivityRepository:
    def __init__(self, database: Any, settings):
        self.saved_places = database[settings.saved_places_collection]
        self.listening_history = database[settings.listening_history_collection]
        self.visitor_sessions = database[settings.visitor_sessions_collection]
        self.usage_events = database[settings.usage_events_collection]
        self.places = database[settings.places_collection]
        self.categories = database[settings.categories_collection]
        self.images = database[settings.place_images_collection]
        self.audios = database[settings.audio_collection]
        self.narrations = database[settings.narrations_collection]

    async def get_visible_place(self, place_id: int) -> dict | None:
        # Chỉ công khai dữ liệu địa điểm đang hiển thị trong trải nghiệm user.
        return await self.places.find_one(
            {"PlaceId": place_id, "IsVisible": {"$ne": False}},
            {
                "_id": 0,
                "PlaceId": 1,
                "PlaceName": 1,
                "Slug": 1,
                "Address": 1,
                "CategoryId": 1,
                "Description": 1,
            },
        )

    async def get_place_category(self, category_id: int | None) -> dict | None:
        if category_id is None:
            return None
        return await self.categories.find_one(
            {"CategoryId": category_id},
            {"_id": 0, "CategoryId": 1, "CategoryName": 1, "Description": 1},
        )

    async def list_place_images(self, place_id: int) -> list[dict]:
        # Một số bản ghi cũ lưu PlaceId dạng chuỗi, nên truy vấn cả chuỗi và số.
        cursor = self.images.find(
            {"PlaceId": {"$in": [place_id, str(place_id)]}},
            {
                "_id": 0,
                "ImageId": 1,
                "PlaceId": 1,
                "FileUrl": 1,
                "SortOrder": 1,
                "Caption": 1,
            },
        ).sort([("SortOrder", 1), ("CreatedAt", 1), ("ImageId", 1)])
        return await cursor.to_list(length=None)

    async def list_active_audios(self, place_id: int) -> list[dict]:
        cursor = (
            self.audios.find(
                {"PlaceId": place_id, "IsActive": {"$ne": False}},
                {
                    "_id": 0,
                    "AudioId": 1,
                    "PlaceId": 1,
                    "Language": 1,
                    "Title": 1,
                    "FileUrl": 1,
                    "VoiceName": 1,
                    "DurationSeconds": 1,
                },
            )
            .sort([("Language", 1), ("CreatedAt", 1)])
        )
        return await cursor.to_list(length=None)

    async def get_active_audio(self, audio_id: str) -> dict | None:
        return await self.audios.find_one(
            {"AudioId": audio_id, "IsActive": {"$ne": False}},
            {"_id": 0, "AudioId": 1},
        )

    async def get_narration(self, narration_id: int | str) -> dict | None:
        query = {"NarrationId": narration_id}
        if isinstance(narration_id, str) and narration_id.isdecimal():
            numeric_id = int(narration_id)
            if str(numeric_id) == narration_id:
                query = {
                    "$or": [
                        {"NarrationId": narration_id},
                        {"NarrationId": numeric_id},
                    ]
                }
        return await self.narrations.find_one(
            query,
            {"_id": 0, "NarrationId": 1},
        )

    async def list_saved_places(self, user_id: str, skip: int, limit: int) -> tuple[list[dict], int]:
        query = {"UserId": user_id}
        cursor = (
            self.saved_places.find(query, {"_id": 0, "SavedPlaceId": 1, "PlaceId": 1, "SavedAt": 1})
            .sort("SavedAt", -1)
            .skip(skip)
            .limit(limit)
        )
        return await cursor.to_list(length=limit), await self.saved_places.count_documents(query)

    async def save_place(self, user_id: str, place_id: int, now: datetime) -> None:
        # Unique index (UserId, PlaceId) bảo đảm lưu lặp lại không tạo bookmark trùng.
        await self.saved_places.update_one(
            {"UserId": user_id, "PlaceId": place_id},
            {
                "$setOnInsert": {
                    "SavedPlaceId": uuid.uuid4().hex,
                    "UserId": user_id,
                    "PlaceId": place_id,
                    "SavedAt": now,
                }
            },
            upsert=True,
        )

    async def unsave_place(self, user_id: str, place_id: int) -> bool:
        result = await self.saved_places.delete_one(
            {"UserId": user_id, "PlaceId": place_id},
        )
        return result.deleted_count > 0

    async def list_listening_history(
        self,
        user_id: str,
        skip: int,
        limit: int,
    ) -> tuple[list[dict], int]:
        query = {"UserId": user_id}
        cursor = (
            self.listening_history.find(
                query,
                {
                    "_id": 0,
                    "ListeningHistoryId": 1,
                    "AudioId": 1,
                    "ListenedAt": 1,
                    "PlayedSeconds": 1,
                    "IsCompleted": 1,
                },
            )
            .sort("ListenedAt", -1)
            .skip(skip)
            .limit(limit)
        )
        return (
            await cursor.to_list(length=limit),
            await self.listening_history.count_documents(query),
        )

    async def record_listening(
        self,
        user_id: str,
        audio_id: str,
        played_seconds: int,
        is_completed: bool,
        now: datetime,
    ) -> dict:
        # Mỗi lần nghe là một dòng lịch sử riêng; UserId được truyền từ token.
        entry = {
            "ListeningHistoryId": uuid.uuid4().hex,
            "UserId": user_id,
            "AudioId": audio_id,
            "ListenedAt": now,
            "PlayedSeconds": played_seconds,
            "IsCompleted": is_completed,
        }
        await self.listening_history.insert_one(entry)
        return {
            key: value
            for key, value in entry.items()
            if key not in {"_id", "UserId"}
        }

    async def create_session(self, user_id: str, now: datetime) -> dict:
        # SessionId khó đoán; LastSeenAt khởi tạo cùng thời điểm bắt đầu.
        session = {
            "SessionId": uuid.uuid4().hex,
            "UserId": user_id,
            "StartedAt": now,
            "LastSeenAt": now,
            "EndedAt": None,
        }
        await self.visitor_sessions.insert_one(session)
        return {key: value for key, value in session.items() if key != "UserId"}

    async def get_session(self, user_id: str, session_id: str) -> dict | None:
        return await self.visitor_sessions.find_one(
            {"UserId": user_id, "SessionId": session_id},
            {"_id": 0, "SessionId": 1, "EndedAt": 1},
        )

    async def touch_session(
        self,
        user_id: str,
        session_id: str,
        now: datetime,
        end_session: bool,
    ) -> dict | None:
        # Điều kiện EndedAt=None ngăn phiên đã kết thúc bị tiếp tục cập nhật.
        changes: dict = {"LastSeenAt": now}
        if end_session:
            changes["EndedAt"] = now
        return await self.visitor_sessions.find_one_and_update(
            {
                "UserId": user_id,
                "SessionId": session_id,
                "EndedAt": None,
            },
            {"$set": changes},
            return_document=ReturnDocument.AFTER,
            projection={
                "_id": 0,
                "SessionId": 1,
                "StartedAt": 1,
                "LastSeenAt": 1,
                "EndedAt": 1,
            },
        )

    async def list_sessions(
        self,
        user_id: str,
        skip: int,
        limit: int,
    ) -> tuple[list[dict], int]:
        query = {"UserId": user_id}
        cursor = (
            self.visitor_sessions.find(
                query,
                {
                    "_id": 0,
                    "SessionId": 1,
                    "StartedAt": 1,
                    "LastSeenAt": 1,
                    "EndedAt": 1,
                },
            )
            .sort("StartedAt", -1)
            .skip(skip)
            .limit(limit)
        )
        return (
            await cursor.to_list(length=limit),
            await self.visitor_sessions.count_documents(query),
        )

    async def record_usage_event(self, event: dict) -> dict:
        # $setOnInsert cùng unique ClientEventId giúp retry cùng event không nhân bản.
        return await self.usage_events.find_one_and_update(
            {"ClientEventId": event["ClientEventId"]},
            {"$setOnInsert": event},
            upsert=True,
            return_document=ReturnDocument.AFTER,
            projection={
                "_id": 0,
                "EventId": 1,
                "ClientEventId": 1,
                "SessionId": 1,
                "NarrationId": 1,
                "AudioId": 1,
                "EventType": 1,
                "CreatedAt": 1,
            },
        )

    async def list_usage_events(
        self,
        user_id: str,
        skip: int,
        limit: int,
    ) -> tuple[list[dict], int]:
        # Chỉ truy vấn event theo session thuộc user; không nhận session tùy ý từ client.
        sessions = await self.visitor_sessions.find(
            {"UserId": user_id},
            {"_id": 0, "SessionId": 1},
        ).to_list(length=None)
        session_ids = [
            session["SessionId"]
            for session in sessions
            if "SessionId" in session
        ]
        if not session_ids:
            return [], 0
        query = {"SessionId": {"$in": session_ids}}
        cursor = (
            self.usage_events.find(
                query,
                {
                    "_id": 0,
                    "EventId": 1,
                    "ClientEventId": 1,
                    "SessionId": 1,
                    "NarrationId": 1,
                    "AudioId": 1,
                    "EventType": 1,
                    "CreatedAt": 1,
                },
            )
            .sort("CreatedAt", -1)
            .skip(skip)
            .limit(limit)
        )
        return (
            await cursor.to_list(length=limit),
            await self.usage_events.count_documents(query),
        )
