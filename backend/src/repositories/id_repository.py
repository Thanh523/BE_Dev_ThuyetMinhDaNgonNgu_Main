from pymongo import ReturnDocument

from src.config.settings import Settings


async def next_integer_id(
    database,
    settings: Settings,
    sequence: str,
    collection: str,
    id_field: str,
) -> int:
    current = await database[collection].find_one(
        {id_field: {"$type": "number"}},
        {id_field: 1},
        sort=[(id_field, -1)],
    )
    maximum = current.get(id_field, 0) if current else 0
    counter = database[settings.counters_collection]
    await counter.update_one(
        {"_id": sequence},
        {"$max": {"value": maximum}},
        upsert=True,
    )
    result = await counter.find_one_and_update(
        {"_id": sequence},
        {"$inc": {"value": 1}},
        return_document=ReturnDocument.AFTER,
    )
    return int(result["value"])
