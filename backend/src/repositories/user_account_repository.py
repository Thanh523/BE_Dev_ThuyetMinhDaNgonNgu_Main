import re
from typing import Any

from pymongo import ReturnDocument

from src.config.settings import Settings


class UserAccountRepository:
    def __init__(self, database: Any, settings: Settings):
        # Chọn collection UserAccounts theo cấu hình của ứng dụng.
        self.users = database[settings.user_accounts_collection]
        self.saved_places = database[settings.saved_places_collection]
        self.listening_history = database[settings.listening_history_collection]

    @staticmethod
    def _user_id_query(user_id: str) -> dict:
        # Hỗ trợ UserId lưu dạng chuỗi hoặc số nguyên như trong các bản dữ liệu khác nhau.
        if user_id.isdecimal() and str(int(user_id)) == user_id:
            return {"$or": [{"UserId": user_id}, {"UserId": int(user_id)}]}
        return {"UserId": user_id}

    async def list(
        self,
        search: str,
        is_active: bool | None,
        skip: int,
        limit: int,
    ) -> tuple[list[dict], int]:
        # Tạo điều kiện tìm kiếm tên/email và lọc trạng thái nếu được yêu cầu.
        query: dict = {}
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
            self._user_id_query(user_id),
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

    async def email_exists(self, email: str, user_id: str) -> bool:
        # Email được so sánh không phân biệt hoa thường và loại trừ chính user đang sửa.
        user_ids: list[str | int] = [user_id]
        if user_id.isdecimal() and str(int(user_id)) == user_id:
            user_ids.append(int(user_id))
        query = {
            "$and": [
                {
                    "Email": {
                        "$regex": f"^{re.escape(email)}$",
                        "$options": "i",
                    }
                },
                {"UserId": {"$nin": user_ids}},
            ]
        }
        return await self.users.find_one(query, {"_id": 1}) is not None

    async def update_profile(self, user_id: str, changes: dict) -> dict | None:
        # Chỉ cập nhật họ tên/email và chỉ trả về các trường an toàn cho API.
        return await self.users.find_one_and_update(
            self._user_id_query(user_id),
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

    async def get_activity(self, user_id: str, limit: int) -> dict | None:
        # Lấy profile an toàn trước; user không tồn tại thì không truy vấn lịch sử.
        user = await self.users.find_one(
            self._user_id_query(user_id),
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

        return {
            "user": user,
            "saved_places": saved_places,
            "saved_places_total": saved_places_total,
            "listening_history": listening_history,
            "listening_history_total": listening_history_total,
        }
