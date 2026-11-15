import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from gridfs import GridFSBucket
from pymongo import ASCENDING, DESCENDING, AsyncMongoClient, MongoClient
from pymongo.collation import Collation

from src.config.settings import get_settings
from src.services.gridfs_file_storage import GridFSFileStorage


DEFAULT_LANGUAGES = (
    ("vi", "Vietnamese"),
    ("en", "English"),
    ("zh-CN", "Chinese (Simplified)"),
    ("ja", "Japanese"),
    ("ko", "Korean"),
    ("fr", "French"),
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    client = AsyncMongoClient(settings.mongodb_uri)
    gridfs_client = None
    try:
        await client.admin.command("ping")
        database = client[settings.mongodb_database]
        app.state.gridfs_audio_storage = None
        app.state.gridfs_image_storage = None
        if (
            settings.audio_storage_backend == "gridfs"
            or settings.image_storage_backend == "gridfs"
        ):
            gridfs_client = MongoClient(settings.mongodb_uri)
            await asyncio.to_thread(
                gridfs_client.admin.command,
                "ping",
            )
            if settings.audio_storage_backend == "gridfs":
                app.state.gridfs_audio_storage = GridFSFileStorage(
                    GridFSBucket(
                        gridfs_client[settings.mongodb_database],
                        bucket_name=settings.audio_gridfs_bucket,
                    )
                )
            if settings.image_storage_backend == "gridfs":
                app.state.gridfs_image_storage = GridFSFileStorage(
                    GridFSBucket(
                        gridfs_client[settings.mongodb_database],
                        bucket_name=settings.image_gridfs_bucket,
                    )
                )
        await database[settings.place_images_collection].create_index(
            [("ImageId", ASCENDING)],
            unique=True,
        )
        await database[settings.place_images_collection].create_index(
            [("PlaceId", ASCENDING), ("SortOrder", ASCENDING)],
            unique=True,
        )
        await database[settings.places_collection].create_index(
            [("PlaceId", ASCENDING)],
            unique=True,
        )
        await database[settings.places_collection].create_index(
            [("Slug", ASCENDING)],
            unique=True,
        )
        await database[settings.places_collection].create_index(
            [("CategoryId", ASCENDING), ("IsVisible", ASCENDING)],
        )
        await database[settings.categories_collection].create_index(
            [("CategoryId", ASCENDING)],
            unique=True,
        )
        languages = database[settings.languages_collection]
        await languages.create_index(
            [("LanguageCode", ASCENDING)],
            unique=True,
        )
        for language_code, language_name in DEFAULT_LANGUAGES:
            await languages.update_one(
                {"LanguageCode": language_code},
                {
                    "$setOnInsert": {
                        "LanguageCode": language_code,
                        "LanguageName": language_name,
                        "IsActive": True,
                    }
                },
                upsert=True,
            )
        await database[settings.audio_collection].create_index(
            [("AudioId", ASCENDING)],
            unique=True,
        )
        await database[settings.audio_collection].create_index(
            [("PlaceId", ASCENDING), ("Language", ASCENDING)],
            unique=True,
        )
        await database[settings.narrations_collection].create_index(
            [("NarrationId", ASCENDING)],
            unique=True,
        )
        await database[settings.narrations_collection].create_index(
            [("PlaceId", ASCENDING), ("LanguageCode", ASCENDING)],
            unique=True,
        )
        await database[settings.audio_files_collection].create_index(
            [("AudioId", ASCENDING)],
            unique=True,
        )
        await database[settings.audio_files_collection].create_index(
            [("NarrationId", ASCENDING)],
        )
        await database[settings.categories_collection].create_index(
            [("CategoryName", ASCENDING)],
            unique=True,
        )
        admin_accounts = database[settings.admin_accounts_collection]
        await admin_accounts.create_index(
            [("AdminId", ASCENDING)],
            unique=True,
        )
        await admin_accounts.create_index(
            [("Username", ASCENDING)],
            unique=True,
        )
        await admin_accounts.create_index(
            [("Email", ASCENDING)],
            unique=True,
        )
        activity_logs = database[settings.admin_activity_logs_collection]
        await activity_logs.create_index(
            [("LogId", ASCENDING)],
            unique=True,
        )
        await activity_logs.create_index(
            [("AdminId", ASCENDING), ("CreatedAt", ASCENDING)],
        )
        # Email của user phải duy nhất, không phân biệt chữ hoa/chữ thường.
        await database[settings.user_accounts_collection].create_index(
            [("Email", ASCENDING)],
            unique=True,
            collation=Collation(locale="en", strength=2),
        )
        await database[settings.user_accounts_collection].create_index(
            [("UserId", ASCENDING)],
            unique=True,
        )
        # Các index hỗ trợ uniqueness, chống event trùng và phân trang activity theo user.
        await database[settings.saved_places_collection].create_index(
            [("UserId", ASCENDING), ("PlaceId", ASCENDING)],
            unique=True,
        )
        await database[settings.saved_places_collection].create_index(
            [("SavedPlaceId", ASCENDING)],
            unique=True,
        )
        await database[settings.saved_places_collection].create_index(
            [("UserId", ASCENDING), ("SavedAt", DESCENDING)],
        )
        await database[settings.saved_places_collection].create_index(
            [("PlaceId", ASCENDING), ("SavedAt", DESCENDING)],
        )
        await database[settings.listening_history_collection].create_index(
            [("ListeningHistoryId", ASCENDING)],
            unique=True,
        )
        await database[settings.listening_history_collection].create_index(
            [("UserId", ASCENDING), ("ListenedAt", DESCENDING)],
        )
        await database[settings.listening_history_collection].create_index(
            [("AudioId", ASCENDING), ("ListenedAt", DESCENDING)],
        )
        await database[settings.listening_history_collection].create_index(
            [("PlaceId", ASCENDING), ("ListenedAt", DESCENDING)],
        )
        await database[settings.visitor_sessions_collection].create_index(
            [("SessionId", ASCENDING)],
            unique=True,
        )
        await database[settings.visitor_sessions_collection].create_index(
            [("UserId", ASCENDING), ("StartedAt", DESCENDING)],
        )
        await database[settings.website_visits_collection].create_index(
            [("VisitId", ASCENDING)],
            unique=True,
        )
        await database[settings.website_visits_collection].create_index(
            [("StartedAt", DESCENDING)],
        )
        await database[settings.website_visits_collection].create_index(
            [("LastSeenAt", DESCENDING)],
        )
        await database[settings.usage_events_collection].create_index(
            [("EventId", ASCENDING)],
            unique=True,
        )
        await database[settings.usage_events_collection].create_index(
            [("ClientEventId", ASCENDING)],
            unique=True,
            partialFilterExpression={"ClientEventId": {"$type": "string"}},
        )
        await database[settings.usage_events_collection].create_index(
            [("SessionId", ASCENDING), ("CreatedAt", DESCENDING)],
        )
        app.state.mongo_client = client
        app.state.database = database
        yield
    finally:
        if gridfs_client is not None:
            gridfs_client.close()
        await client.close()


def get_database(request: Request):
    database = getattr(request.app.state, "database", None)
    if database is None:
        raise RuntimeError("The MongoDB connection is not initialized.")
    return database
