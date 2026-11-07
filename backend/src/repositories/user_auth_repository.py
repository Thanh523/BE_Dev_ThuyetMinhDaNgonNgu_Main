from typing import Any

from pymongo import ReturnDocument
from pymongo.collation import Collation


class UserAuthRepository:
    def __init__(self, database: Any, collection_name: str):
        self.users = database[collection_name]

    async def find_by_email(self, email: str) -> dict | None:
        # So khớp email không phân biệt hoa thường, phù hợp với unique index hiện có.
        return await self.users.find_one(
            {"Email": email},
            collation=Collation(locale="en", strength=2),
        )

    async def create(self, user: dict) -> None:
        await self.users.insert_one(user)

    @staticmethod
    def _user_id_query(user_id: str) -> dict:
        # Dữ liệu cũ có thể lưu UserId dạng số; hỗ trợ cả số và chuỗi.
        if user_id.isdecimal() and str(int(user_id)) == user_id:
            return {"$or": [{"UserId": user_id}, {"UserId": int(user_id)}]}
        return {"UserId": user_id}

    async def record_login(self, user_id: str, now) -> dict | None:
        # Cập nhật lần đăng nhập chỉ khi tài khoản vẫn active và chưa bị xóa mềm.
        return await self.users.find_one_and_update(
            {"$and": [
                self._user_id_query(user_id),
                {"IsActive": True, "IsDeleted": {"$ne": True}},
            ]},
            {"$set": {"LastLoginAt": now}},
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

    async def get_authorization_state(self, user_id: str) -> dict | None:
        # Middleware gọi lại DB theo mỗi request để token bị vô hiệu ngay khi khóa/xóa.
        return await self.users.find_one(
            self._user_id_query(user_id),
            {"_id": 0, "UserId": 1, "IsActive": 1, "IsDeleted": 1},
        )

    async def get_profile(self, user_id: str) -> dict | None:
        # Projection loại PasswordHash và không trả tài khoản đã vô hiệu hóa.
        return await self.users.find_one(
            {"$and": [
                self._user_id_query(user_id),
                {"IsActive": True, "IsDeleted": {"$ne": True}},
            ]},
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
