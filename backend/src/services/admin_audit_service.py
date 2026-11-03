from src.repositories.admin_activity_repository import AdminActivityRepository
from src.services.admin_activity_service import AdminActivityService


async def log_admin_activity(
    database,
    collection_name: str,
    admin_id: str,
    action: str,
    entity_name: str,
    entity_id: str,
    description: str,
) -> None:
    service = AdminActivityService(
        AdminActivityRepository(database, collection_name),
    )
    await service.log(admin_id, action, entity_name, entity_id, description)
