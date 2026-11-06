import asyncio
import re
import unicodedata
from pathlib import Path

from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError, PyMongoError

from src.repositories.category_repository import CategoryRepository
from src.repositories.place_repository import PlaceRepository


def slugify(value: str) -> str:
    value = value.strip().replace("đ", "d").replace("Đ", "D")
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-zA-Z0-9]+", "-", ascii_value).strip("-").lower()


def _image_folder_name(place_id: int | str, slug: str) -> str:
    place_id_value = str(place_id)
    if (
        not place_id_value.isdecimal()
        or re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug) is None
    ):
        raise ValueError("Place ID or slug is invalid for image storage.")
    return f"{place_id_value}-{slug}"


class PlaceService:
    def __init__(
        self,
        repository: PlaceRepository,
        category_repository: CategoryRepository,
        image_storage_dir: Path,
    ):
        self.repository = repository
        self.category_repository = category_repository
        self.image_storage_dir = image_storage_dir

    async def list_places(
        self,
        search: str,
        category_id: int | None,
        visibility: str,
        skip: int,
        limit: int,
    ) -> tuple[list[dict], int]:
        try:
            return await self.repository.list(
                search,
                category_id,
                visibility,
                skip,
                limit,
            )
        except PyMongoError as error:
            raise HTTPException(
                status_code=503,
                detail="Place list is temporarily unavailable.",
            ) from error

    async def get_place(self, place_id: int) -> dict:
        try:
            place = await self.repository.get(place_id)
        except PyMongoError as error:
            raise HTTPException(
                status_code=503,
                detail="Place details are temporarily unavailable.",
            ) from error
        if place is None:
            raise HTTPException(status_code=404, detail="Place was not found.")
        return place

    async def create_place(
        self,
        category_id: int,
        place_name: str,
        slug: str | None,
        address: str,
    ) -> dict:
        name = place_name.strip()
        address_value = address.strip()
        if not name or not address_value:
            raise HTTPException(
                status_code=422,
                detail="Place name and address are required.",
            )
        slug_value = slugify(slug or name)
        if not slug_value:
            raise HTTPException(
                status_code=422,
                detail="A valid slug could not be generated.",
            )
        try:
            if not await self.category_repository.exists(category_id):
                raise HTTPException(
                    status_code=422,
                    detail="Selected category was not found.",
                )
            if await self.repository.slug_exists(slug_value):
                raise HTTPException(status_code=409, detail="Slug is already in use.")
            place = await self.repository.create(
                {
                    "CategoryId": category_id,
                    "PlaceName": name,
                    "Slug": slug_value,
                    "Address": address_value,
                    "IsVisible": True,
                }
            )
            image_directory = self.image_storage_dir / _image_folder_name(
                place["PlaceId"],
                slug_value,
            )
            try:
                await asyncio.to_thread(
                    image_directory.mkdir,
                    parents=True,
                    exist_ok=True,
                )
            except OSError as error:
                try:
                    await self.repository.delete(place["PlaceId"])
                except PyMongoError as rollback_error:
                    raise HTTPException(
                        status_code=503,
                        detail=(
                            "Place was saved, but its image folder could not be "
                            "created and the place could not be rolled back."
                        ),
                    ) from rollback_error
                raise HTTPException(
                    status_code=503,
                    detail="Place could not be saved because its image folder could not be created.",
                ) from error
            return place
        except DuplicateKeyError as error:
            raise HTTPException(
                status_code=409,
                detail="Place ID or slug is already in use.",
            ) from error
        except PyMongoError as error:
            raise HTTPException(status_code=503, detail="Place could not be saved.") from error

    async def update_place(self, place_id: int, changes: dict) -> dict:
        await self.get_place(place_id)
        mapped: dict = {}
        if "category_id" in changes:
            category_id = changes["category_id"]
            try:
                category_exists = await self.category_repository.exists(category_id)
            except PyMongoError as error:
                raise HTTPException(
                    status_code=503,
                    detail="Category information is temporarily unavailable.",
                ) from error
            if not category_exists:
                raise HTTPException(
                    status_code=422,
                    detail="Selected category was not found.",
                )
            mapped["CategoryId"] = category_id
        if "place_name" in changes:
            name = changes["place_name"].strip()
            if not name:
                raise HTTPException(status_code=422, detail="Place name is required.")
            mapped["PlaceName"] = name
        if "address" in changes:
            address = changes["address"].strip()
            if not address:
                raise HTTPException(status_code=422, detail="Address is required.")
            mapped["Address"] = address
        if "slug" in changes:
            slug = slugify(changes["slug"])
            if not slug:
                raise HTTPException(status_code=422, detail="Slug is required.")
            try:
                slug_in_use = await self.repository.slug_exists(slug, place_id)
            except PyMongoError as error:
                raise HTTPException(
                    status_code=503,
                    detail="Place could not be updated.",
                ) from error
            if slug_in_use:
                raise HTTPException(status_code=409, detail="Slug is already in use.")
            mapped["Slug"] = slug
        if not mapped:
            raise HTTPException(status_code=422, detail="No place fields were provided.")

        try:
            place = await self.repository.update(place_id, mapped)
        except DuplicateKeyError as error:
            raise HTTPException(status_code=409, detail="Slug is already in use.") from error
        except PyMongoError as error:
            raise HTTPException(status_code=503, detail="Place could not be updated.") from error
        if place is None:
            raise HTTPException(status_code=404, detail="Place was not found.")
        return place

    async def set_visibility(self, place_id: int, is_visible: bool) -> dict:
        try:
            place = await self.repository.set_visibility(place_id, is_visible)
        except PyMongoError as error:
            raise HTTPException(
                status_code=503,
                detail="Place status could not be updated.",
            ) from error
        if place is None:
            raise HTTPException(status_code=404, detail="Place was not found.")
        return place

    async def delete_place(self, place_id: int) -> None:
        await self.get_place(place_id)
        try:
            if await self.repository.has_images(place_id):
                raise HTTPException(
                    status_code=409,
                    detail="Place cannot be deleted while it has related images.",
                )
            deleted = await self.repository.delete(place_id)
        except PyMongoError as error:
            raise HTTPException(
                status_code=503,
                detail="Place could not be deleted or its relationships could not be checked.",
            ) from error
        if not deleted:
            raise HTTPException(status_code=404, detail="Place was not found.")
