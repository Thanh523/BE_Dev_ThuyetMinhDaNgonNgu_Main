import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from bson import ObjectId
from fastapi import HTTPException

from src.services.gridfs_file_storage import GridFSFileStorage


class FakeGridOut:
    def __init__(self, content: bytes):
        self.content = io.BytesIO(content)
        self.length = len(content)
        self.filename = "guide.mp3"
        self.metadata = {"contentType": "audio/mpeg"}
        self.closed = False

    def read(self, size=-1):
        return self.content.read(size)

    def seek(self, offset):
        return self.content.seek(offset)

    def close(self):
        self.closed = True
        self.content.close()


class GridFSFileStorageTests(unittest.IsolatedAsyncioTestCase):
    async def test_upload_and_delete_use_gridfs_file_id(self):
        bucket = MagicMock()
        file_id = ObjectId("65a000000000000000000001")
        bucket.upload_from_stream.return_value = file_id
        storage = GridFSFileStorage(bucket)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "guide.mp3"
            path.write_bytes(b"audio")
            stored_id = await storage.upload_file(path, path.name)

        self.assertEqual(str(file_id), stored_id)
        self.assertEqual(
            "audio/mpeg",
            bucket.upload_from_stream.call_args.kwargs["metadata"]["contentType"],
        )
        await storage.delete_file(stored_id)
        bucket.delete.assert_called_once_with(file_id)

    async def test_streams_requested_byte_range(self):
        bucket = MagicMock()
        grid_out = FakeGridOut(b"0123456789")
        bucket.open_download_stream.return_value = grid_out
        storage = GridFSFileStorage(bucket)

        response = await storage.stream_response(
            "65a000000000000000000001",
            "bytes=3-6",
        )
        chunks = [chunk async for chunk in response.body_iterator]

        self.assertEqual(206, response.status_code)
        self.assertEqual("bytes 3-6/10", response.headers["content-range"])
        self.assertEqual(b"3456", b"".join(chunks))
        self.assertTrue(grid_out.closed)

    async def test_rejects_unsatisfiable_range_and_closes_gridfs_stream(self):
        bucket = MagicMock()
        grid_out = FakeGridOut(b"0123456789")
        bucket.open_download_stream.return_value = grid_out
        storage = GridFSFileStorage(bucket)

        with self.assertRaises(HTTPException) as raised:
            await storage.stream_response(
                "65a000000000000000000001",
                "bytes=10-",
            )

        self.assertEqual(416, raised.exception.status_code)
        self.assertEqual("bytes */10", raised.exception.headers["Content-Range"])
        self.assertTrue(grid_out.closed)


if __name__ == "__main__":
    unittest.main()
