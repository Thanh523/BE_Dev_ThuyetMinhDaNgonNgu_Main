import asyncio
import getpass
import re
import uuid
from datetime import datetime, timezone

from pymongo import AsyncMongoClient
from pymongo.errors import DuplicateKeyError, PyMongoError

from src.config.settings import get_settings
from src.repositories.admin_account_repository import AdminAccountRepository
from src.repositories.admin_activity_repository import AdminActivityRepository
from src.services.admin_activity_service import AdminActivityService
from src.services.admin_auth_service import hash_password


async def create_admin() -> None:
    settings = get_settings()
    if not settings.jwt_key:
        raise SystemExit(
            "JWT_KEY is not configured. Set it in backend/atlas-credentials.env "
            "before creating an admin account."
        )
    if (
        settings.jwt_algorithm == "HS256"
        and len(settings.jwt_key.encode("utf-8")) < 32
    ):
        raise SystemExit("JWT_KEY must be at least 32 bytes for HS256.")

    username = input("Admin username: ").strip().casefold()
    if len(username) < 3 or len(username) > 64 or any(char.isspace() for char in username):
        raise SystemExit("Username must be 3-64 characters and contain no spaces.")
    email = input("Admin email: ").strip().casefold()
    if len(email) > 254 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise SystemExit("Enter a valid email address.")

    password = getpass.getpass("Admin password (at least 12 characters): ")
    confirmation = getpass.getpass("Confirm admin password: ")
    if len(password) < 12:
        raise SystemExit("Password must contain at least 12 characters.")
    if len(password) > 128:
        raise SystemExit("Password must be no longer than 128 characters.")
    if password != confirmation:
        raise SystemExit("Passwords do not match.")

    client = AsyncMongoClient(settings.mongodb_uri)
    try:
        database = client[settings.mongodb_database]
        accounts = AdminAccountRepository(
            database,
            settings.admin_accounts_collection,
        )
        activity_repository = AdminActivityRepository(
            database,
            settings.admin_activity_logs_collection,
        )
        await accounts.ensure_indexes()
        await activity_repository.ensure_indexes()
        now = datetime.now(timezone.utc)
        admin_id = uuid.uuid4().hex
        await accounts.create(
            {
                "AdminId": admin_id,
                "Username": username,
                "Email": email,
                "PasswordHash": hash_password(password),
                "Role": "admin",
                "IsActive": True,
                "CreatedAt": now,
                "UpdatedAt": now,
                "LastLoginAt": None,
            }
        )
        await AdminActivityService(activity_repository).log(
            admin_id=admin_id,
            action="CREATE",
            entity_name="AdminAccounts",
            entity_id=admin_id,
            description="Admin account created through bootstrap CLI.",
        )
    except DuplicateKeyError:
        raise SystemExit("That admin username or email already exists.") from None
    except PyMongoError as error:
        raise SystemExit(
            f"Could not create the admin account ({type(error).__name__})."
        ) from error
    finally:
        await client.close()

    print(f"Admin account '{username}' created.")


if __name__ == "__main__":
    asyncio.run(create_admin())
