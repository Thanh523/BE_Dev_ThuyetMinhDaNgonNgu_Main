import asyncio
import mimetypes
from pathlib import Path
from typing import AsyncIterator

from bson import ObjectId
from fastapi import HTTPException
from gridfs import GridFSBucket
from gridfs.errors import NoFile
from pymongo.errors import PyMongoError
from starlette.responses import StreamingResponse


STREAM_CHUNK_SIZE = 256 * 1024


def _byte_range(range_header: str | None, size: int) -> tuple[int, int, int]:
    if not range_header:
        return 0, max(0, size - 1), 200
    if not range_header.startswith("bytes=") or "," in range_header:
        raise ValueError("Invalid byte range.")

    start_text, separator, end_text = range_header[6:].partition("-")
    if not separator:
        raise ValueError("Invalid byte range.")
    try:
        if not start_text:
            suffix_length = int(end_text)
            if suffix_length <= 0 or size == 0:
                raise ValueError("Invalid byte range.")
            start = max(0, size - suffix_length)
            end = size - 1
        else:
            start = int(start_text)
            end = int(end_text) if end_text else size - 1
            if start < 0 or start >= size or end < start:
                raise ValueError("Invalid byte range.")
            end = min(end, size - 1)
    except ValueError as error:
        raise ValueError("Invalid byte range.") from error
    return start, end, 206


class GridFSFileStorage:
    def __init__(self, bucket: GridFSBucket):
        self.bucket = bucket

    async def upload_file(self, path: Path, filename: str) -> str:
        try:
            return await asyncio.to_thread(self._upload_file, path, filename)
        except PyMongoError as error:
            raise HTTPException(
                status_code=503,
                detail="File could not be saved to MongoDB.",
            ) from error

    def _upload_file(self, path: Path, filename: str) -> str:
        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        with path.open("rb") as source_file:
            file_id = self.bucket.upload_from_stream(
                filename,
                source_file,
                metadata={"contentType": content_type},
            )
        return str(file_id)

    async def delete_file(self, file_id: str) -> None:
        object_id = self._object_id(file_id)
        try:
            await asyncio.to_thread(self.bucket.delete, object_id)
        except NoFile as error:
            raise HTTPException(
                status_code=404,
                detail="File was not found in MongoDB.",
            ) from error
        except PyMongoError as error:
            raise HTTPException(
                status_code=503,
                detail="File could not be deleted from MongoDB.",
            ) from error

    async def stream_response(
        self,
        file_id: str,
        range_header: str | None = None,
    ) -> StreamingResponse:
        object_id = self._object_id(file_id)
        try:
            grid_out = await asyncio.to_thread(
                self.bucket.open_download_stream,
                object_id,
            )
        except NoFile as error:
            raise HTTPException(status_code=404, detail="File was not found.") from error
        except PyMongoError as error:
            raise HTTPException(
                status_code=503,
                detail="File is temporarily unavailable.",
            ) from error

        try:
            size = grid_out.length
            try:
                start, end, status_code = _byte_range(range_header, size)
            except ValueError as error:
                raise HTTPException(
                    status_code=416,
                    detail="Requested file range is not satisfiable.",
                    headers={"Content-Range": f"bytes */{size}"},
                ) from error

            if status_code == 206:
                await asyncio.to_thread(grid_out.seek, start)
            content_length = end - start + 1 if size else 0
            metadata = grid_out.metadata or {}
            content_type = metadata.get("contentType") or (
                mimetypes.guess_type(grid_out.filename)[0]
                or "application/octet-stream"
            )
            headers = {
                "Accept-Ranges": "bytes",
                "Cache-Control": "public, max-age=3600",
                "Content-Length": str(content_length),
            }
            if status_code == 206:
                headers["Content-Range"] = f"bytes {start}-{end}/{size}"

            return StreamingResponse(
                self._iter_stream(grid_out, content_length),
                status_code=status_code,
                media_type=content_type,
                headers=headers,
            )
        except PyMongoError as error:
            await asyncio.to_thread(grid_out.close)
            raise HTTPException(
                status_code=503,
                detail="File is temporarily unavailable.",
            ) from error
        except BaseException:
            await asyncio.to_thread(grid_out.close)
            raise

    async def _iter_stream(
        self,
        grid_out,
        remaining: int,
    ) -> AsyncIterator[bytes]:
        try:
            while remaining > 0:
                chunk = await asyncio.to_thread(
                    grid_out.read,
                    min(STREAM_CHUNK_SIZE, remaining),
                )
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk
        finally:
            await asyncio.to_thread(grid_out.close)

    @staticmethod
    def _object_id(file_id: str) -> ObjectId:
        if not ObjectId.is_valid(file_id):
            raise HTTPException(status_code=404, detail="File was not found.")
        return ObjectId(file_id)
