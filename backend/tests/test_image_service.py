import io
import tempfile
import unittest
from pathlib import Path

from fastapi import HTTPException, UploadFile
from PIL import Image

from src.config.settings import Settings
from src.services.image_service import ImageService


class FakeRepository:
    def __init__(self):
        self.documents: dict[str, dict] = {}
        self.exists = True

    async def place_exists(self, place_id):
        return self.exists

    async def next_sort_order(self, place_id):
        orders = [
            document["SortOrder"]
            for document in self.documents.values()
            if document["PlaceId"] == place_id
        ]
        return max(orders, default=0) + 1

    async def sort_orders_in_use(self, place_id, sort_orders, exclude_image_id=None):
        return {
            document["SortOrder"]
            for image_id, document in self.documents.items()
            if image_id != exclude_image_id
            and document["PlaceId"] == place_id
            and document["SortOrder"] in sort_orders
        }

    async def insert_many(self, documents):
        self.documents.update(
            {document["ImageId"]: document for document in documents}
        )

    async def delete_by_ids(self, image_ids):
        for image_id in image_ids:
            self.documents.pop(image_id, None)

    async def get(self, image_id):
        return self.documents.get(image_id)

    async def update(self, image_id, changes):
        document = self.documents.get(image_id)
        if document is None:
            return None
        document.update(changes)
        return document

    async def delete(self, image_id):
        return self.documents.pop(image_id, None)


def image_bytes(image_format: str) -> bytes:
    image = Image.new("RGB", (2, 2), color="blue")
    output = io.BytesIO()
    image.save(output, format=image_format)
    return output.getvalue()


class ImageServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.storage = Path(self.temporary_directory.name) / "images"
        self.repository = FakeRepository()
        self.settings = Settings(
            mongodb_uri="mongodb://localhost:27017",
            mongodb_database="test",
            places_collection="Places",
            place_images_collection="PlaceImages",
            jwt_key="test-key",
            jwt_algorithm="HS256",
            jwt_role_claim="role",
            jwt_issuer=None,
            jwt_audience=None,
            cors_origins=[],
            image_storage_dir=self.storage,
        )
        self.service = ImageService(self.repository, self.settings)

    async def asyncTearDown(self):
        self.temporary_directory.cleanup()

    async def test_uploads_multiple_verified_images_with_manual_order(self):
        files = [
            UploadFile(filename="first.jpg", file=io.BytesIO(image_bytes("JPEG"))),
            UploadFile(filename="second.webp", file=io.BytesIO(image_bytes("WEBP"))),
        ]

        images = await self.service.upload(
            place_id=17,
            files=files,
            captions=[" First ", "Second"],
            sort_orders=[20, 10],
        )

        self.assertEqual([20, 10], [image["SortOrder"] for image in images])
        self.assertEqual(["First", "Second"], [image["Caption"] for image in images])
        self.assertTrue(all((self.storage / image["FileUrl"].split("/")[-1]).is_file() for image in images))
        self.assertEqual(2, len(self.repository.documents))

    async def test_rejects_non_image_and_removes_temporary_file(self):
        upload = UploadFile(filename="fake.png", file=io.BytesIO(b"not an image"))

        with self.assertRaises(HTTPException) as raised:
            await self.service.upload(17, [upload], None, None)

        self.assertEqual(415, raised.exception.status_code)
        self.assertEqual([], list(self.storage.iterdir()))
        self.assertEqual({}, self.repository.documents)

    async def test_rejects_files_over_configured_limit(self):
        self.settings = Settings(
            mongodb_uri="mongodb://localhost:27017",
            mongodb_database="test",
            places_collection="Places",
            place_images_collection="PlaceImages",
            jwt_key="test-key",
            jwt_algorithm="HS256",
            jwt_role_claim="role",
            jwt_issuer=None,
            jwt_audience=None,
            cors_origins=[],
            image_storage_dir=self.storage,
            max_image_size_bytes=8,
        )
        self.service = ImageService(self.repository, self.settings)

        with self.assertRaises(HTTPException) as raised:
            await self.service.upload(
                17,
                [UploadFile(filename="large.png", file=io.BytesIO(b"123456789"))],
                None,
                None,
            )

        self.assertEqual(413, raised.exception.status_code)
        self.assertEqual([], list(self.storage.iterdir()))

    async def test_updates_caption_and_sort_order_then_permanently_deletes(self):
        image = (
            await self.service.upload(
                17,
                [UploadFile(filename="image.png", file=io.BytesIO(image_bytes("PNG")))],
                None,
                None,
            )
        )[0]
        stored_file = self.storage / image["FileUrl"].split("/")[-1]

        updated = await self.service.update(image["ImageId"], "Updated caption", 5)
        self.assertEqual("Updated caption", updated["Caption"])
        self.assertEqual(5, updated["SortOrder"])

        await self.service.delete(image["ImageId"])
        self.assertFalse(stored_file.exists())
        self.assertNotIn(image["ImageId"], self.repository.documents)

    async def test_rejects_sort_order_already_used_by_another_image(self):
        files = [
            UploadFile(filename="first.png", file=io.BytesIO(image_bytes("PNG"))),
            UploadFile(filename="second.png", file=io.BytesIO(image_bytes("PNG"))),
        ]
        await self.service.upload(17, files, None, [1, 2])

        with self.assertRaises(HTTPException) as raised:
            await self.service.update(next(iter(self.repository.documents)), None, 2)

        self.assertEqual(409, raised.exception.status_code)


if __name__ == "__main__":
    unittest.main()
