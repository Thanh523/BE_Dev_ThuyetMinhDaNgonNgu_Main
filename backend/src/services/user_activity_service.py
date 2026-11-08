import asyncio
from datetime import datetime, timezone
import uuid

from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError, PyMongoError

from src.repositories.user_activity_repository import UserActivityRepository


class UserActivityService:
    def __init__(self, repository: UserActivityRepository):
        self.repository = repository

    async def list_saved_places(self, user_id: str, skip: int, limit: int) -> dict:
        try:
            items, total = await self.repository.list_saved_places(user_id, skip, limit)
        except PyMongoError as error:
            raise self._unavailable("Saved places are temporarily unavailable.") from error
        return {"items": items, "total": total, "skip": skip, "limit": limit}

    async def save_place(self, user_id: str, place_id: int) -> None:
        # Kiểm tra địa điểm tồn tại/hiển thị trước khi upsert theo cặp user-place.
        try:
            if not await self.repository.get_visible_place(place_id):
                raise HTTPException(status_code=404, detail="Place was not found.")
            await self.repository.save_place(
                user_id,
                place_id,
                datetime.now(timezone.utc),
            )
        except PyMongoError as error:
            raise self._unavailable("Place could not be saved.") from error

    async def list_place_audios(self, place_id: int) -> list[dict]:
        try:
            if not await self.repository.get_visible_place(place_id):
                raise HTTPException(status_code=404, detail="Place was not found.")
            return await self.repository.list_active_audios(place_id)
        except PyMongoError as error:
            raise self._unavailable("Place audio is temporarily unavailable.") from error

    async def list_visible_categories(self) -> list[dict]:
        try:
            return await self.repository.list_visible_categories()
        except PyMongoError as error:
            raise self._unavailable(
                "Place categories are temporarily unavailable.",
            ) from error

    async def get_place_details(self, place_id: int) -> dict:
        try:
            # Kiểm tra visibility trước, tránh lộ ảnh/audio của địa điểm ẩn cho user.
            place = await self.repository.get_visible_place(place_id)
            if not place:
                raise HTTPException(status_code=404, detail="Place was not found.")
            category, images, audios = await self._place_detail_data(place)
            return {
                "place": place,
                "category": category,
                "images": images,
                "audios": audios,
            }
        except PyMongoError as error:
            raise self._unavailable(
                "Place details are temporarily unavailable.",
            ) from error

    async def _place_detail_data(self, place: dict) -> tuple[dict | None, list[dict], list[dict]]:
        # Các nguồn độc lập được lấy song song để trang chi tiết phản hồi nhanh hơn.
        category, images, audios = await asyncio.gather(
            self.repository.get_place_category(place.get("CategoryId")),
            self.repository.list_place_images(int(place["PlaceId"])),
            self.repository.list_active_audios(int(place["PlaceId"])),
        )
        return category, images, audios

    async def unsave_place(self, user_id: str, place_id: int) -> bool:
        try:
            return await self.repository.unsave_place(user_id, place_id)
        except PyMongoError as error:
            raise self._unavailable("Saved place could not be removed.") from error

    async def list_listening_history(self, user_id: str, skip: int, limit: int) -> dict:
        try:
            items, total = await self.repository.list_listening_history(
                user_id,
                skip,
                limit,
            )
        except PyMongoError as error:
            raise self._unavailable("Listening history is temporarily unavailable.") from error
        return {"items": items, "total": total, "skip": skip, "limit": limit}

    async def record_listening(
        self,
        user_id: str,
        audio_id: str,
        played_seconds: int,
        is_completed: bool,
    ) -> dict:
        # Không ghi lịch sử cho audio không tồn tại hoặc đã bị admin vô hiệu hóa.
        try:
            if not await self.repository.get_active_audio(audio_id):
                raise HTTPException(status_code=404, detail="Audio was not found.")
            return await self.repository.record_listening(
                user_id,
                audio_id,
                played_seconds,
                is_completed,
                datetime.now(timezone.utc),
            )
        except PyMongoError as error:
            raise self._unavailable("Listening history could not be recorded.") from error

    async def create_session(self, user_id: str) -> dict:
        try:
            return await self.repository.create_session(
                user_id,
                datetime.now(timezone.utc),
            )
        except PyMongoError as error:
            raise self._unavailable("Visitor session could not be started.") from error

    async def touch_session(self, user_id: str, session_id: str, end_session: bool) -> dict:
        # Xác minh quyền sở hữu trước; repository cập nhật có điều kiện để tránh race kết thúc.
        try:
            session = await self.repository.get_session(user_id, session_id)
            if session is None:
                raise HTTPException(status_code=404, detail="Visitor session was not found.")
            if session.get("EndedAt") is not None:
                raise HTTPException(status_code=409, detail="Visitor session has ended.")
            updated = await self.repository.touch_session(
                user_id,
                session_id,
                datetime.now(timezone.utc),
                end_session,
            )
        except PyMongoError as error:
            raise self._unavailable("Visitor session could not be updated.") from error
        if updated is None:
            raise HTTPException(status_code=409, detail="Visitor session has ended.")
        return updated

    async def list_sessions(self, user_id: str, skip: int, limit: int) -> dict:
        try:
            items, total = await self.repository.list_sessions(user_id, skip, limit)
        except PyMongoError as error:
            raise self._unavailable("Visitor sessions are temporarily unavailable.") from error
        return {"items": items, "total": total, "skip": skip, "limit": limit}

    async def list_usage_events(self, user_id: str, skip: int, limit: int) -> dict:
        try:
            items, total = await self.repository.list_usage_events(
                user_id,
                skip,
                limit,
            )
        except PyMongoError as error:
            raise self._unavailable("Usage events are temporarily unavailable.") from error
        return {"items": items, "total": total, "skip": skip, "limit": limit}

    async def record_usage_event(
        self,
        user_id: str,
        client_event_id: str,
        session_id: str,
        event_type: str,
        narration_id: int | str | None,
        audio_id: str | None,
    ) -> dict:
        # Chỉ nhận event từ session đang mở của user; đồng thời cập nhật LastSeenAt.
        try:
            session = await self.repository.get_session(user_id, session_id)
            if session is None:
                raise HTTPException(status_code=404, detail="Visitor session was not found.")
            if session.get("EndedAt") is not None:
                raise HTTPException(status_code=409, detail="Visitor session has ended.")
            active_session = await self.repository.touch_session(
                user_id,
                session_id,
                datetime.now(timezone.utc),
                False,
            )
            if active_session is None:
                raise HTTPException(status_code=409, detail="Visitor session has ended.")
            if audio_id and not await self.repository.get_active_audio(audio_id):
                raise HTTPException(status_code=404, detail="Audio was not found.")
            if narration_id and not await self.repository.get_narration(narration_id):
                raise HTTPException(status_code=404, detail="Narration was not found.")

            # ID do client cung cấp giúp retry idempotent; EventId vẫn do server tạo.
            event = {
                "EventId": uuid.uuid4().hex,
                "ClientEventId": client_event_id,
                "SessionId": session_id,
                "NarrationId": narration_id,
                "AudioId": audio_id,
                "EventType": event_type.strip(),
                "CreatedAt": datetime.now(timezone.utc),
            }
            stored = await self.repository.record_usage_event(event)
        except DuplicateKeyError as error:
            raise HTTPException(
                status_code=409,
                detail="ClientEventId has already been used.",
            ) from error
        except PyMongoError as error:
            raise self._unavailable("Usage event could not be recorded.") from error

        # Cùng client ID + payload trả event cũ; cùng ID nhưng payload khác bị từ chối.
        same_event = all(
            stored.get(key) == event.get(key)
            for key in ("ClientEventId", "SessionId", "NarrationId", "AudioId", "EventType")
        )
        if not same_event:
            raise HTTPException(
                status_code=409,
                detail="ClientEventId has already been used for another event.",
            )
        return stored

    @staticmethod
    def _unavailable(message: str) -> HTTPException:
        return HTTPException(status_code=503, detail=message)
