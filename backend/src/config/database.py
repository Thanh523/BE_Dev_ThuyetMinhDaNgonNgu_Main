from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from pymongo import ASCENDING, DESCENDING, AsyncMongoClient
from pymongo.collation import Collation

from src.config.settings import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    client = AsyncMongoClient(settings.mongodb_uri)
    try:
        await client.admin.command("ping")
        database = client[settings.mongodb_database]
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
        await database[settings.audio_collection].create_index(
            [("AudioId", ASCENDING)],
            unique=True,
        )
        await database[settings.audio_collection].create_index(
            [("PlaceId", ASCENDING), ("Language", ASCENDING)],
            unique=True,
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
        await database[settings.listening_history_collection].create_index(
            [("ListeningHistoryId", ASCENDING)],
            unique=True,
        )
        await database[settings.listening_history_collection].create_index(
            [("UserId", ASCENDING), ("ListenedAt", DESCENDING)],
        )
        await database[settings.visitor_sessions_collection].create_index(
            [("SessionId", ASCENDING)],
            unique=True,
        )
        await database[settings.visitor_sessions_collection].create_index(
            [("UserId", ASCENDING), ("StartedAt", DESCENDING)],
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
        await client.close()


def get_database(request: Request):
    database = getattr(request.app.state, "database", None)
    if database is None:
        raise RuntimeError("The MongoDB connection is not initialized.")
    return database
