from datetime import datetime, timezone
import unittest
from unittest.mock import AsyncMock, Mock

from fastapi import HTTPException

from src.repositories.user_activity_repository import UserActivityRepository
from src.services.user_activity_service import UserActivityService


class UserActivityServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.repository = Mock()
        self.service = UserActivityService(self.repository)

    async def test_visible_categories_are_returned_by_repository(self):
        categories = [{"CategoryId": 3, "CategoryName": "Museum"}]
        self.repository.list_visible_categories = AsyncMock(return_value=categories)

        result = await self.service.list_visible_categories()

        self.assertEqual(categories, result)
        self.repository.list_visible_categories.assert_awaited_once_with()

    async def test_saving_place_is_scoped_to_authenticated_user(self):
        self.repository.get_visible_place = AsyncMock(return_value={"PlaceId": 15})
        self.repository.save_place = AsyncMock()

        await self.service.save_place("user-1", 15)

        self.repository.save_place.assert_awaited_once()
        args = self.repository.save_place.await_args.args
        self.assertEqual(("user-1", 15), args[:2])

    async def test_saving_unknown_place_returns_not_found(self):
        self.repository.get_visible_place = AsyncMock(return_value=None)
        self.repository.save_place = AsyncMock()

        with self.assertRaises(HTTPException) as raised:
            await self.service.save_place("user-1", 404)

        self.assertEqual(404, raised.exception.status_code)
        self.repository.save_place.assert_not_awaited()

    async def test_place_audio_list_is_limited_to_visible_places(self):
        audios = [{"AudioId": "audio-1", "IsActive": True}]
        self.repository.get_visible_place = AsyncMock(return_value={"PlaceId": 15})
        self.repository.list_active_audios = AsyncMock(return_value=audios)

        result = await self.service.list_place_audios(15)

        self.assertEqual(audios, result)
        self.repository.list_active_audios.assert_awaited_once_with(15)

    async def test_place_audio_list_rejects_hidden_places(self):
        self.repository.get_visible_place = AsyncMock(return_value=None)
        self.repository.list_active_audios = AsyncMock()

        with self.assertRaises(HTTPException) as raised:
            await self.service.list_place_audios(15)

        self.assertEqual(404, raised.exception.status_code)
        self.repository.list_active_audios.assert_not_awaited()

    async def test_place_details_include_category_images_and_audio_for_visible_place(self):
        place = {
            "PlaceId": 15,
            "PlaceName": "Museum",
            "CategoryId": 2,
        }
        category = {"CategoryId": 2, "CategoryName": "Museum"}
        images = [{"ImageId": "image-1", "FileUrl": "/image.jpg"}]
        audios = [{"AudioId": "audio-1", "FileUrl": "/audio.mp3"}]
        self.repository.get_visible_place = AsyncMock(return_value=place)
        self.repository.get_place_category = AsyncMock(return_value=category)
        self.repository.list_place_images = AsyncMock(return_value=images)
        self.repository.list_active_audios = AsyncMock(return_value=audios)

        result = await self.service.get_place_details(15)

        self.assertEqual(
            {
                "place": place,
                "category": category,
                "images": images,
                "audios": audios,
            },
            result,
        )
        self.repository.get_place_category.assert_awaited_once_with(2)
        self.repository.list_place_images.assert_awaited_once_with(15)
        self.repository.list_active_audios.assert_awaited_once_with(15)

    async def test_place_details_reject_hidden_or_missing_place(self):
        self.repository.get_visible_place = AsyncMock(return_value=None)
        self.repository.get_place_category = AsyncMock()
        self.repository.list_place_images = AsyncMock()
        self.repository.list_active_audios = AsyncMock()

        with self.assertRaises(HTTPException) as raised:
            await self.service.get_place_details(15)

        self.assertEqual(404, raised.exception.status_code)
        self.repository.get_place_category.assert_not_awaited()
        self.repository.list_place_images.assert_not_awaited()
        self.repository.list_active_audios.assert_not_awaited()

    async def test_recording_listening_rejects_unknown_audio(self):
        self.repository.get_active_audio = AsyncMock(return_value=None)
        self.repository.record_listening = AsyncMock()

        with self.assertRaises(HTTPException) as raised:
            await self.service.record_listening("user-1", "audio-1", 30, False)

        self.assertEqual(404, raised.exception.status_code)
        self.repository.record_listening.assert_not_awaited()

    async def test_user_cannot_update_another_users_session(self):
        self.repository.get_session = AsyncMock(return_value=None)
        self.repository.touch_session = AsyncMock()

        with self.assertRaises(HTTPException) as raised:
            await self.service.touch_session("user-1", "session-owned-by-other", False)

        self.assertEqual(404, raised.exception.status_code)
        self.repository.touch_session.assert_not_awaited()

    async def test_session_and_usage_lists_use_authenticated_user_id(self):
        self.repository.list_sessions = AsyncMock(return_value=([], 0))
        self.repository.list_usage_events = AsyncMock(return_value=([], 0))

        await self.service.list_sessions("user-1", 0, 20)
        await self.service.list_usage_events("user-1", 0, 20)

        self.repository.list_sessions.assert_awaited_once_with("user-1", 0, 20)
        self.repository.list_usage_events.assert_awaited_once_with("user-1", 0, 20)

    async def test_usage_event_requires_owned_active_session(self):
        self.repository.get_session = AsyncMock(return_value={"EndedAt": None})
        self.repository.touch_session = AsyncMock(return_value={"SessionId": "session-1"})
        self.repository.get_active_audio = AsyncMock(return_value={"AudioId": "audio-1"})
        self.repository.get_narration = AsyncMock(return_value=None)
        self.repository.record_usage_event = AsyncMock()

        with self.assertRaises(HTTPException) as raised:
            await self.service.record_usage_event(
                "user-1",
                "event-1",
                "session-1",
                "audio_play",
                "missing-narration",
                "audio-1",
            )

        self.assertEqual(404, raised.exception.status_code)
        self.repository.record_usage_event.assert_not_awaited()

    async def test_duplicate_client_event_is_idempotent_for_same_payload(self):
        self.repository.get_session = AsyncMock(return_value={"EndedAt": None})
        self.repository.touch_session = AsyncMock(return_value={"SessionId": "session-1"})
        self.repository.get_active_audio = AsyncMock(return_value={"AudioId": "audio-1"})
        self.repository.get_narration = AsyncMock()
        self.repository.record_usage_event = AsyncMock(
            return_value={
                "EventId": "event-db-1",
                "ClientEventId": "client-1",
                "SessionId": "session-1",
                "NarrationId": None,
                "AudioId": "audio-1",
                "EventType": "audio_play",
            }
        )

        result = await self.service.record_usage_event(
            "user-1",
            "client-1",
            "session-1",
            "audio_play",
            None,
            "audio-1",
        )

        self.assertEqual("event-db-1", result["EventId"])

    async def test_duplicate_client_event_with_different_payload_conflicts(self):
        self.repository.get_session = AsyncMock(return_value={"EndedAt": None})
        self.repository.touch_session = AsyncMock(return_value={"SessionId": "session-1"})
        self.repository.get_active_audio = AsyncMock()
        self.repository.get_narration = AsyncMock()
        self.repository.record_usage_event = AsyncMock(
            return_value={
                "ClientEventId": "client-1",
                "SessionId": "session-1",
                "NarrationId": None,
                "AudioId": "audio-1",
                "EventType": "audio_play",
            }
        )

        with self.assertRaises(HTTPException) as raised:
            await self.service.record_usage_event(
                "user-1",
                "client-1",
                "session-1",
                "audio_pause",
                None,
                "audio-1",
            )

        self.assertEqual(409, raised.exception.status_code)


class UserActivityRepositoryTests(unittest.IsolatedAsyncioTestCase):
    async def test_record_listening_response_omits_mongo_internal_id(self):
        repository = object.__new__(UserActivityRepository)
        repository.listening_history = Mock()

        async def insert_entry(entry):
            entry["_id"] = object()

        repository.listening_history.insert_one = AsyncMock(side_effect=insert_entry)

        result = await repository.record_listening(
            "user-1",
            "audio-1",
            42,
            False,
            datetime.now(timezone.utc),
        )

        self.assertNotIn("_id", result)
        self.assertNotIn("UserId", result)
        self.assertEqual("audio-1", result["AudioId"])


if __name__ == "__main__":
    unittest.main()
