from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from pymongo import ASCENDING, AsyncMongoClient

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
