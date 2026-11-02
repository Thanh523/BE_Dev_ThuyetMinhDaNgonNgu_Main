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
