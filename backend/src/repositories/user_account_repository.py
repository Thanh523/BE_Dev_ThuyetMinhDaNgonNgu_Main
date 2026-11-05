import re
from datetime import datetime, timezone
from typing import Any

from pymongo import ReturnDocument

from src.config.settings import Settings


class UserAccountRepository:
    def __init__(self, database: Any, settings: Settings):
        # Chọn collection UserAccounts theo cấu hình của ứng dụng.
        self.users = database[settings.user_accounts_collection]
        self.saved_places = database[settings.saved_places_collection]
        self.listening_history = database[settings.listening_history_collection]
        self.visitor_sessions = database[settings.visitor_sessions_collection]
        self.usage_events = database[settings.usage_events_collection]

    @staticmethod
    def _user_id_query(user_id: str) -> dict:
        # Hỗ trợ UserId lưu dạng chuỗi hoặc số nguyên như trong các bản dữ liệu khác nhau.
        if user_id.isdecimal() and str(int(user_id)) == user_id:
            return {"$or": [{"UserId": user_id}, {"UserId": int(user_id)}]}
        return {"UserId": user_id}

    @classmethod
    def _not_deleted_query(cls, query: dict) -> dict:
        if "$or" in query:
            return {"$and": [query, {"IsDeleted": {"$ne": True}}]}
        return {**query, "IsDeleted": {"$ne": True}}

    async def list(
        self,
        search: str,
        is_active: bool | None,
        skip: int,
        limit: int,
    ) -> tuple[list[dict], int]:
        # Tạo điều kiện tìm kiếm tên/email và lọc trạng thái nếu được yêu cầu.
        query: dict = {"IsDeleted": {"$ne": True}}
        normalized_search = search.strip()
        if normalized_search:
            escaped_search = re.escape(normalized_search)
            query["$or"] = [
                {"FullName": {"$regex": escaped_search, "$options": "i"}},
                {"Email": {"$regex": escaped_search, "$options": "i"}},
            ]
        if is_active is not None:
            query["IsActive"] = is_active

        # Chỉ lấy trường cần hiển thị; tuyệt đối không truy vấn PasswordHash.
        projection = {
            "_id": 0,
            "UserId": 1,
            "FullName": 1,
            "Email": 1,
            "IsActive": 1,
            "CreatedAt": 1,
            "LastLoginAt": 1,
        }
        # Sắp xếp ổn định, phân trang danh sách rồi đếm tổng bản ghi phù hợp.
        cursor = (
            self.users.find(query, projection)
            .sort([("FullName", 1), ("UserId", 1)])
            .skip(skip)
            .limit(limit)
        )
        items = await cursor.to_list(length=limit)
        total = await self.users.count_documents(query)
        return items, total

    async def update_status(self, user_id: str, is_active: bool) -> dict | None:
        # Trả về bản ghi vừa cập nhật nhưng chỉ với các trường an toàn cho API.
        return await self.users.find_one_and_update(
            self._not_deleted_query(self._user_id_query(user_id)),
            {"$set": {"IsActive": is_active}},
            return_document=ReturnDocument.AFTER,
            projection={
                "_id": 0,
                "UserId": 1,
                "FullName": 1,
                "Email": 1,
                "IsActive": 1,
                "CreatedAt": 1,
                "LastLoginAt": 1,
            },
        )

    async def email_exists(self, email: str, exclude_user_id: str | None = None) -> bool:
        # Email được so sánh không phân biệt hoa thường.
        query: dict = {
            "Email": {
                "$regex": f"^{re.escape(email)}$",
                "$options": "i",
            }
        }
        if exclude_user_id is not None:
            user_ids: list[str | int] = [exclude_user_id]
            if (
                exclude_user_id.isdecimal()
                and str(int(exclude_user_id)) == exclude_user_id
            ):
                user_ids.append(int(exclude_user_id))
            query["UserId"] = {"$nin": user_ids}
        return await self.users.find_one(query, {"_id": 1}) is not None

    async def update_profile(self, user_id: str, changes: dict) -> dict | None:
        # Chỉ cập nhật họ tên/email và chỉ trả về các trường an toàn cho API.
        return await self.users.find_one_and_update(
            self._not_deleted_query(self._user_id_query(user_id)),
            {"$set": changes},
            return_document=ReturnDocument.AFTER,
            projection={
                "_id": 0,
                "UserId": 1,
                "FullName": 1,
                "Email": 1,
                "IsActive": 1,
                "CreatedAt": 1,
                "LastLoginAt": 1,
            },
        )

    async def create(self, user: dict) -> None:
        # Chèn tài khoản đã được service băm mật khẩu.
        await self.users.insert_one(user)

    async def get_activity(self, user_id: str, limit: int) -> dict | None:
        # Lấy profile an toàn trước; user không tồn tại thì không truy vấn lịch sử.
        user = await self.users.find_one(
            self._not_deleted_query(self._user_id_query(user_id)),
            {
                "_id": 0,
                "UserId": 1,
                "FullName": 1,
                "Email": 1,
                "IsActive": 1,
                "CreatedAt": 1,
                "LastLoginAt": 1,
            },
        )
        if user is None:
            return None

        # Hỗ trợ dữ liệu có UserId dạng chuỗi hoặc số nguyên.
        user_ids: list[str | int] = [user_id]
        if user_id.isdecimal() and str(int(user_id)) == user_id:
            user_ids.append(int(user_id))
        related_query = {"UserId": {"$in": user_ids}}

        saved_places_cursor = self.saved_places.find(
            related_query,
            {
                "_id": 0,
                "SavedPlaceId": 1,
                "PlaceId": 1,
                "SavedAt": 1,
            },
        )
        saved_places = await saved_places_cursor.sort(
            "SavedAt",
            -1,
        ).limit(limit).to_list(length=limit)
        saved_places_total = await self.saved_places.count_documents(related_query)

        listening_history_cursor = self.listening_history.find(
            related_query,
            {
                "_id": 0,
                "ListeningHistoryId": 1,
                "AudioId": 1,
                "ListenedAt": 1,
                "PlayedSeconds": 1,
                "IsCompleted": 1,
            },
        )
        listening_history = await listening_history_cursor.sort(
            "ListenedAt",
            -1,
        ).limit(limit).to_list(length=limit)
        listening_history_total = await self.listening_history.count_documents(
            related_query,
        )

        # Lấy các phiên truy cập mới nhất của user và tổng số phiên.
        sessions_cursor = self.visitor_sessions.find(
            related_query,
            {
                "_id": 0,
                "SessionId": 1,
                "StartedAt": 1,
                "LastReportedAt": 1,
                "EndedAt": 1,
            },
        )
        visitor_sessions = await sessions_cursor.sort(
            "StartedAt",
            -1,
        ).limit(limit).to_list(length=limit)
        visitor_sessions_total = await self.visitor_sessions.count_documents(
            related_query,
        )

        return {
            "user": user,
            "saved_places": saved_places,
            "saved_places_total": saved_places_total,
            "listening_history": listening_history,
            "listening_history_total": listening_history_total,
            "visitor_sessions": visitor_sessions,
            "visitor_sessions_total": visitor_sessions_total,
        }

    async def delete_if_unrelated(self, user_id: str) -> dict | None:
        # Giữ lại hồ sơ để hoạt động ghi đồng thời không tạo dữ liệu mồ côi.
        user_query = self._not_deleted_query(self._user_id_query(user_id))
        user = await self.users.find_one(user_query, {"_id": 0, "UserId": 1})
        if user is None:
            return None

        user_ids: list[str | int] = [user_id]
        if user_id.isdecimal() and str(int(user_id)) == user_id:
            user_ids.append(int(user_id))
        related_query = {"UserId": {"$in": user_ids}}
        related_counts = {
            "saved_places": await self.saved_places.count_documents(related_query),
            "listening_history": await self.listening_history.count_documents(
                related_query,
            ),
            "visitor_sessions": await self.visitor_sessions.count_documents(
                related_query,
            ),
        }

        # UsageEvents liên kết gián tiếp với user qua SessionId trong VisitorSessions.
        session_ids = await self.visitor_sessions.find(
            related_query,
            {"_id": 0, "SessionId": 1},
        ).to_list(length=None)
        session_values = [
            session["SessionId"]
            for session in session_ids
            if "SessionId" in session
        ]
        related_counts["usage_events"] = (
            await self.usage_events.count_documents(
                {"SessionId": {"$in": session_values}},
            )
            if session_values
            else 0
        )

        if any(related_counts.values()):
            return {"deleted": False, "related_counts": related_counts}

        result = await self.users.update_one(
            user_query,
            {
                "$set": {
                    "IsDeleted": True,
                    "IsActive": False,
                    "DeletedAt": datetime.now(timezone.utc),
                }
            },
        )
        if result.modified_count != 1:
            return None
        return {"deleted": True, "related_counts": related_counts}
