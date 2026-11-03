import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


BACKEND_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(BACKEND_ROOT / "atlas-credentials.env")


def _read_csv(name: str, default: str) -> list[str]:
    return [value.strip() for value in os.getenv(name, default).split(",") if value.strip()]


@dataclass(frozen=True)
class Settings:
    mongodb_uri: str
    mongodb_database: str
    places_collection: str
    place_images_collection: str
    jwt_key: str | None
    jwt_algorithm: str
    jwt_role_claim: str
    jwt_issuer: str | None
    jwt_audience: str | None
    cors_origins: list[str]
    image_storage_dir: Path
    categories_collection: str = "Categories"
    counters_collection: str = "Counters"
    admin_accounts_collection: str = "AdminAccounts"
    admin_activity_logs_collection: str = "AdminActivityLogs"
    max_image_size_bytes: int = 10 * 1024 * 1024


def get_settings() -> Settings:
    return Settings(
        mongodb_uri=os.getenv("MONGODB_URI", "mongodb://localhost:27017"),
        mongodb_database=os.getenv("MONGODB_DATABASE", "SaigonEcho"),
        places_collection=os.getenv("MONGODB_PLACES_COLLECTION", "Places"),
        place_images_collection=os.getenv("MONGODB_PLACE_IMAGES_COLLECTION", "PlaceImages"),
        jwt_key=os.getenv("JWT_KEY"),
        jwt_algorithm=os.getenv("JWT_ALGORITHM", "HS256"),
        jwt_role_claim=os.getenv("JWT_ROLE_CLAIM", "role"),
        jwt_issuer=os.getenv("JWT_ISSUER"),
        jwt_audience=os.getenv("JWT_AUDIENCE"),
        cors_origins=_read_csv(
            "CORS_ORIGINS",
            "http://localhost:3000,http://localhost:5173",
        ),
        image_storage_dir=Path(
            os.getenv(
                "IMAGE_STORAGE_DIR",
                str(BACKEND_ROOT / "uploads" / "images"),
            )
        ).resolve(),
        categories_collection=os.getenv("MONGODB_CATEGORIES_COLLECTION", "Categories"),
        counters_collection=os.getenv("MONGODB_COUNTERS_COLLECTION", "Counters"),
        admin_accounts_collection=os.getenv(
            "MONGODB_ADMIN_ACCOUNTS_COLLECTION",
            "AdminAccounts",
        ),
        admin_activity_logs_collection=os.getenv(
            "MONGODB_ADMIN_ACTIVITY_LOGS_COLLECTION",
            "AdminActivityLogs",
        ),
    )
