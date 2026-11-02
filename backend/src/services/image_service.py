import asyncio
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from PIL import Image, UnidentifiedImageError
from pymongo.errors import DuplicateKeyError, PyMongoError

from src.config.settings import Settings
from src.repositories.place_image_repository import PlaceImageRepository


SUPPORTED_FORMATS = {
    "JPEG": "jpg",
    "PNG": "png",
    "WEBP": "webp",
}


def _inspect_image(path: str) -> str:
    with Image.open(path) as image:
        image_format = image.format
        image.verify()
    if image_format not in SUPPORTED_FORMATS:
        raise ValueError("Unsupported image format.")
    return image_format


def _remove_file(path: Path) -> None:
    path.unlink(missing_ok=True)


class ImageService:
    def __init__(self, repository: PlaceImageRepository, settings: Settings):
        self.repository = repository
        self.settings = settings
        self.settings.image_storage_dir.mkdir(parents=True, exist_ok=True)
        self.staging_dir = (
            self.settings.image_storage_dir.parent
            / f".{self.settings.image_storage_dir.name}-staging"
        )
        self.staging_dir.mkdir(parents=True, exist_ok=True)

    async def upload(
        self,
        place_id: int | str,
        files: list[UploadFile],
        captions: list[str] | None,
        sort_orders: list[int] | None,
    ) -> list[dict]:
        if not files:
            raise HTTPException(status_code=400, detail="At least one image is required.")
        if captions is not None and len(captions) != len(files):
            raise HTTPException(
                status_code=422,
                detail="Provide one caption for each uploaded image.",
            )
        if captions is not None and any(len(caption) > 1000 for caption in captions):
            raise HTTPException(
                status_code=422,
                detail="Captions must be no longer than 1000 characters.",
            )
        if sort_orders is not None and len(sort_orders) != len(files):
            raise HTTPException(
                status_code=422,
                detail="Provide one sort order for each uploaded image.",
            )
        if sort_orders is not None and any(sort_order < 1 for sort_order in sort_orders):
            raise HTTPException(
                status_code=422,
                detail="Sort orders must be positive integers.",
            )
        if sort_orders is not None and len(set(sort_orders)) != len(sort_orders):
            raise HTTPException(
                status_code=422,
                detail="Sort orders in one upload must be unique.",
            )

        if not await self.repository.place_exists(place_id):
            raise HTTPException(status_code=404, detail="Place was not found.")

        if sort_orders is not None:
            duplicates = await self.repository.sort_orders_in_use(place_id, sort_orders)
            if duplicates:
                raise HTTPException(
                    status_code=409,
                    detail=f"Sort order already exists: {min(duplicates)}.",
                )

        first_sort_order = await self.repository.next_sort_order(place_id)
        staged_files: list[Path] = []
        documents: list[dict] = []
        now = datetime.now(timezone.utc)
        persisted = False

        try:
            for index, upload in enumerate(files):
                temporary_path, image_format = await self._save_and_validate(upload)
                staged_files.append(temporary_path)
                image_id = uuid.uuid4().hex
                extension = SUPPORTED_FORMATS[image_format]
                final_path = self.settings.image_storage_dir / f"{image_id}.{extension}"
                await asyncio.to_thread(os.replace, temporary_path, final_path)
                staged_files[-1] = final_path

                documents.append(
                    {
                        "ImageId": image_id,
                        "PlaceId": place_id,
                        "FileUrl": f"/uploads/images/{final_path.name}",
                        "SortOrder": (
                            sort_orders[index]
                            if sort_orders is not None
                            else first_sort_order + index
                        ),
                        "Caption": captions[index].strip() if captions is not None else "",
                        "CreatedAt": now,
                        "UpdatedAt": now,
                    }
                )

            await self.repository.insert_many(documents)
            persisted = True
        except DuplicateKeyError as error:
            await self.repository.delete_by_ids(
                [document["ImageId"] for document in documents]
            )
            raise HTTPException(
                status_code=409,
                detail="One or more sort orders already exist for this place.",
            ) from error
        except PyMongoError as error:
            await self.repository.delete_by_ids(
                [document["ImageId"] for document in documents]
            )
            raise HTTPException(
                status_code=503,
                detail="Images could not be saved to the database.",
            ) from error
        finally:
            if not persisted:
                await self._cleanup(staged_files)

        return documents

    async def _save_and_validate(self, upload: UploadFile) -> tuple[Path, str]:
        temporary_file = tempfile.NamedTemporaryFile(
            prefix=".upload-",
            suffix=".tmp",
            dir=self.staging_dir,
            delete=False,
        )
        temporary_path = Path(temporary_file.name)
        size = 0
        upload_closed = False
        try:
            with temporary_file:
                while chunk := await upload.read(64 * 1024):
                    size += len(chunk)
                    if size > self.settings.max_image_size_bytes:
                        raise HTTPException(
                            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                            detail="Each image must be at most "
                            f"{self.settings.max_image_size_bytes} bytes.",
                        )
                    temporary_file.write(chunk)

            if size == 0:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Uploaded image is empty.",
                )

            try:
                image_format = await asyncio.to_thread(
                    _inspect_image,
                    str(temporary_path),
                )
            except (UnidentifiedImageError, OSError, Image.DecompressionBombError, ValueError) as error:
                raise HTTPException(
                    status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                    detail="Only valid JPEG, PNG, and WebP images are supported.",
                ) from error
            await upload.close()
            upload_closed = True
            return temporary_path, image_format
        finally:
            if not upload_closed:
                try:
                    await upload.close()
                finally:
                    await asyncio.to_thread(_remove_file, temporary_path)

    async def update(
        self,
        image_id: str,
        caption: str | None,
        sort_order: int | None,
    ) -> dict:
        changes: dict = {}
        if caption is not None:
            changes["Caption"] = caption.strip()
        if sort_order is not None:
            changes["SortOrder"] = sort_order
        if not changes:
            raise HTTPException(
                status_code=422,
                detail="At least one of caption or sort_order is required.",
            )

        existing_image = await self.repository.get(image_id)
        if existing_image is None:
            raise HTTPException(status_code=404, detail="Image was not found.")
        if sort_order is not None:
            duplicates = await self.repository.sort_orders_in_use(
                existing_image["PlaceId"],
                [sort_order],
                exclude_image_id=image_id,
            )
            if duplicates:
                raise HTTPException(
                    status_code=409,
                    detail=f"Sort order already exists: {sort_order}.",
                )

        try:
            image = await self.repository.update(image_id, changes)
        except DuplicateKeyError as error:
            raise HTTPException(
                status_code=409,
                detail=f"Sort order already exists: {sort_order}.",
            ) from error
        if image is None:
            raise HTTPException(status_code=404, detail="Image was not found.")
        return image

    async def delete(self, image_id: str) -> None:
        image = await self.repository.get(image_id)
        if image is None:
            raise HTTPException(status_code=404, detail="Image was not found.")

        try:
            await asyncio.to_thread(self._path_from_file_url(image["FileUrl"]).unlink, missing_ok=True)
        except OSError as error:
            raise HTTPException(
                status_code=500,
                detail="Image metadata remains unchanged because its file could not be removed.",
            ) from error

        deleted = await self.repository.delete(image_id)
        if deleted is None:
            raise HTTPException(
                status_code=409,
                detail="Image metadata changed while the file was being removed.",
            )

    async def _cleanup(self, paths: list[Path]) -> None:
        for path in paths:
            await asyncio.to_thread(_remove_file, path)

    def _path_from_file_url(self, file_url: str) -> Path:
        prefix = "/uploads/images/"
        filename = file_url.removeprefix(prefix)
        if not file_url.startswith(prefix) or not filename or "/" in filename or "\\" in filename:
            raise ValueError("Stored image URL is outside the configured image directory.")
        path = (self.settings.image_storage_dir / filename).resolve()
        if path.parent != self.settings.image_storage_dir:
            raise ValueError("Stored image path is outside the configured image directory.")
        return path
