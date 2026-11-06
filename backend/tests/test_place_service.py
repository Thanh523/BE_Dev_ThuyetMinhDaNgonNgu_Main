import unittest
from copy import deepcopy
import tempfile
from pathlib import Path
from types import SimpleNamespace

from fastapi import HTTPException

from src.config.settings import Settings
from src.repositories.category_repository import CategoryRepository
from src.repositories.place_repository import PlaceRepository
from src.services.category_service import CategoryService
from src.services.place_service import PlaceService, slugify


def matches(document, query):
    for key, condition in query.items():
        if key == "$or":
            if not any(matches(document, option) for option in condition):
                return False
            continue
        if key == "$and":
            if not all(matches(document, option) for option in condition):
                return False
            continue
        value = document.get(key)
        if isinstance(condition, dict):
            for operator, expected in condition.items():
                if operator == "$type":
                    if expected == "number" and not isinstance(value, (int, float)):
                        return False
                elif operator == "$ne" and value == expected:
                    return False
                elif operator == "$exists" and ((key in document) != expected):
                    return False
                elif operator == "$regex":
                    import re

                    flags = re.IGNORECASE if condition.get("$options") == "i" else 0
                    if value is None or re.search(expected, str(value), flags) is None:
                        return False
        elif value != condition:
            return False
    return True


class FakeCursor:
    def __init__(self, documents):
        self.documents = documents

    def sort(self, fields, direction=None):
        if isinstance(fields, str):
            fields = [(fields, direction or 1)]
        for field, order in reversed(fields):
            self.documents.sort(
                key=lambda document: document.get(field, ""),
                reverse=order < 0,
            )
        return self

    def skip(self, count):
        self.documents = self.documents[count:]
        return self

    def limit(self, count):
        self.documents = self.documents[:count]
        return self

    async def to_list(self, length=None):
        return deepcopy(self.documents[:length])


class FakeCollection:
    def __init__(self):
        self.documents = []

    async def find_one(self, query, projection=None, sort=None):
        found = [document for document in self.documents if matches(document, query)]
        if sort:
            for field, direction in reversed(sort):
                found.sort(
                    key=lambda document: document.get(field, 0),
                    reverse=direction < 0,
                )
        return deepcopy(found[0]) if found else None

    def find(self, query, projection=None):
        return FakeCursor(
            [deepcopy(document) for document in self.documents if matches(document, query)]
        )

    async def count_documents(self, query):
        return sum(matches(document, query) for document in self.documents)

    async def insert_one(self, document):
        self.documents.append(deepcopy(document))

    async def update_one(self, query, update, upsert=False):
        document = next(
            (item for item in self.documents if matches(item, query)),
            None,
        )
        if document is None and upsert:
            document = {"_id": query["_id"]}
            self.documents.append(document)
        if document is not None:
            for field, value in update.get("$max", {}).items():
                document[field] = max(document.get(field, value), value)
            for field, value in update.get("$inc", {}).items():
                document[field] = document.get(field, 0) + value

    async def find_one_and_update(
        self,
        query,
        update,
        return_document=None,
        projection=None,
    ):
        document = next(
            (item for item in self.documents if matches(item, query)),
            None,
        )
        if document is None:
            return None
        document.update(update.get("$set", {}))
        for field, value in update.get("$inc", {}).items():
            document[field] = document.get(field, 0) + value
        return deepcopy(document)

    async def delete_one(self, query):
        for index, document in enumerate(self.documents):
            if matches(document, query):
                del self.documents[index]
                return SimpleNamespace(deleted_count=1)
        return SimpleNamespace(deleted_count=0)


class FakeDatabase:
    def __init__(self):
        self.collections = {}

    def __getitem__(self, name):
        return self.collections.setdefault(name, FakeCollection())


class PlaceSlugTests(unittest.TestCase):
    def test_slugify_normalizes_vietnamese_and_punctuation(self):
        self.assertEqual(
            "cho-ben-thanh-sai-gon",
            slugify("Chợ Bến Thành - Sài Gòn"),
        )

    def test_slugify_handles_d_and_empty_values(self):
        self.assertEqual("duong-hoa", slugify("Đường hoa"))
        self.assertEqual("", slugify(" !? "))


class PlaceManagementTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.image_storage_dir = Path(self.temporary_directory.name) / "images"
        self.database = FakeDatabase()
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
            image_storage_dir=self.image_storage_dir,
        )
        self.category_repository = CategoryRepository(self.database, self.settings)
        self.place_repository = PlaceRepository(self.database, self.settings)
        self.categories = CategoryService(self.category_repository)
        self.places = PlaceService(
            self.place_repository,
            self.category_repository,
            self.image_storage_dir,
        )
        self.category = await self.categories.create_category("Landmark")

    async def asyncTearDown(self):
        self.temporary_directory.cleanup()

    async def test_creates_place_with_generated_id_slug_and_visibility(self):
        place = await self.places.create_place(
            self.category["CategoryId"],
            "Chợ Bến Thành",
            None,
            "Quận 1, TP.HCM",
        )

        self.assertEqual(1, place["PlaceId"])
        self.assertEqual("cho-ben-thanh", place["Slug"])
        self.assertIs(place["IsVisible"], True)
        self.assertTrue(
            (
                self.image_storage_dir
                / "1-cho-ben-thanh"
            ).is_dir()
        )
        self.assertEqual(
            {
                "PlaceId",
                "CategoryId",
                "PlaceName",
                "Slug",
                "Address",
                "IsVisible",
            },
            set(place),
        )

    async def test_update_visibility_and_filtered_list_use_repository(self):
        place = await self.places.create_place(
            self.category["CategoryId"],
            "City Museum",
            None,
            "District 1",
        )
        updated = await self.places.update_place(
            place["PlaceId"],
            {"place_name": "History Museum", "slug": "History Museum"},
        )
        self.assertEqual("history-museum", updated["Slug"])
        self.assertEqual("History Museum", updated["PlaceName"])

        hidden = await self.places.set_visibility(place["PlaceId"], False)
        self.assertIs(hidden["IsVisible"], False)
        visible_items, visible_total = await self.places.list_places(
            "History",
            self.category["CategoryId"],
            "visible",
            0,
            20,
        )
        hidden_items, hidden_total = await self.places.list_places(
            "History",
            self.category["CategoryId"],
            "hidden",
            0,
            20,
        )

        self.assertEqual(([], 0), (visible_items, visible_total))
        self.assertEqual(1, hidden_total)
        self.assertEqual(place["PlaceId"], hidden_items[0]["PlaceId"])

    async def test_place_delete_is_blocked_while_images_reference_it(self):
        place = await self.places.create_place(
            self.category["CategoryId"],
            "Museum",
            None,
            "District 1",
        )
        await self.database["PlaceImages"].insert_one(
            {"PlaceId": place["PlaceId"], "ImageId": "image"}
        )

        with self.assertRaises(HTTPException) as raised:
            await self.places.delete_place(place["PlaceId"])

        self.assertEqual(409, raised.exception.status_code)

    async def test_category_delete_is_blocked_while_places_reference_it(self):
        await self.places.create_place(
            self.category["CategoryId"],
            "Museum",
            None,
            "District 1",
        )

        with self.assertRaises(HTTPException) as raised:
            await self.categories.delete_category(self.category["CategoryId"])

        self.assertEqual(409, raised.exception.status_code)

    async def test_category_create_and_update_persist_description(self):
        category = await self.categories.create_category(
            "  Park  ",
            "  Public green space  ",
        )

        self.assertEqual("Park", category["CategoryName"])
        self.assertEqual("Public green space", category["Description"])

        updated = await self.categories.update_category(
            category["CategoryId"],
            "Botanical garden",
            "A garden open to visitors.",
        )

        self.assertEqual("Botanical garden", updated["CategoryName"])
        self.assertEqual("A garden open to visitors.", updated["Description"])

    async def test_category_rename_without_description_preserves_existing_description(self):
        category = await self.categories.create_category(
            "Museum",
            "Historic building",
        )
        updated = await self.categories.update_category(
            category["CategoryId"],
            "Tourist landmark",
        )

        self.assertEqual("Historic building", updated["Description"])


if __name__ == "__main__":
    unittest.main()
