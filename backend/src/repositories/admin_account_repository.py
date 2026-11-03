from typing import Any


class AdminAccountRepository:
    def __init__(self, database: Any, collection_name: str):
        self.accounts = database[collection_name]

    async def find_for_login(self, login_name: str) -> dict | None:
        return await self.accounts.find_one(
            {
                "$or": [
                    {"Username": login_name},
                    {"Email": login_name},
                ]
            }
        )

    async def record_login(self, admin_id: str, now) -> bool:
        result = await self.accounts.update_one(
            {
                "AdminId": admin_id,
                "IsActive": True,
                "Role": "admin",
            },
            {"$set": {"LastLoginAt": now, "UpdatedAt": now}},
        )
        return result.matched_count == 1

    async def get_authorization_state(self, admin_id: str) -> dict | None:
        return await self.accounts.find_one(
            {"AdminId": admin_id},
            {"Role": 1, "IsActive": 1},
        )

    async def create(self, account: dict) -> None:
        await self.accounts.insert_one(account)

    async def ensure_indexes(self) -> None:
        await self.accounts.create_index("AdminId", unique=True)
        await self.accounts.create_index("Username", unique=True)
        await self.accounts.create_index("Email", unique=True)
