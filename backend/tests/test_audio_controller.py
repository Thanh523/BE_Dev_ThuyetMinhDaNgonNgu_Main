import unittest
from datetime import datetime, timezone

from src.controllers.audio_controller import AudioView, router


class AudioControllerTests(unittest.TestCase):
    def test_audio_creation_only_exposes_upload_not_text_to_speech(self):
        routes = {
            (method, route.path)
            for route in router.routes
            for method in route.methods
        }
        self.assertNotIn(("POST", "/api/admin/places/{place_id}/audios"), routes)
        self.assertIn(
            ("POST", "/api/admin/places/{place_id}/audios/upload"),
            routes,
        )
        self.assertIn(
            ("PATCH", "/api/admin/audios/{audio_id}/narration"),
            routes,
        )

    def test_audio_responses_use_database_field_aliases(self):
        response_routes = [
            route
            for route in router.routes
            if getattr(route, "response_model", None) is not None
        ]
        self.assertTrue(response_routes)
        self.assertTrue(
            all(route.response_model_by_alias for route in response_routes)
        )

        payload = AudioView.model_validate(
            {
                "AudioId": "audio-1",
                "PlaceId": 17,
                "Language": "en",
                "Title": "Guide",
                "SourceText": "",
                "TranslatedText": "",
                "FileUrl": "/uploads/audio/guide.wav",
                "Voice": "voice",
                "CreatedAt": datetime.now(timezone.utc),
                "UpdatedAt": datetime.now(timezone.utc),
            }
        ).model_dump(by_alias=True)
        self.assertIn("AudioId", payload)
        self.assertIn("FileUrl", payload)
        self.assertIn("DurationSeconds", payload)
        self.assertIsNone(payload["NarrationId"])


if __name__ == "__main__":
    unittest.main()
