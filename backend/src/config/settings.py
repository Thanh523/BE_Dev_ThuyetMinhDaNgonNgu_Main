import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv


BACKEND_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(BACKEND_ROOT / "atlas-credentials.env")
load_dotenv(BACKEND_ROOT / "src" / "atlas_credential.env")


def _read_csv(name: str, default: str) -> list[str]:
    return [value.strip() for value in os.getenv(name, default).split(",") if value.strip()]


def _read_mongodb_uri() -> str:
    configured_uri = os.getenv("MONGODB_URI", "").strip()
    if configured_uri.startswith(("mongodb://", "mongodb+srv://")):
        return configured_uri

    username = os.getenv("MONGODB_USERNAME", "").strip()
    password = os.getenv("MONGODB_PASSWORD", "")
    if configured_uri and "@" in configured_uri:
        return f"mongodb+srv://{configured_uri}"
    if username and password and configured_uri:
        return (

            f"mongodb+srv://{quote_plus(username)}:{quote_plus(password)}"
            f"@{configured_uri}/?retryWrites=true&w=majority"
        )
    return "mongodb://localhost:27017"


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
    audio_storage_dir: Path = Path("uploads/audio")
    categories_collection: str = "Categories"
    languages_collection: str = "Languages"
    audio_collection: str = "PlaceAudios"
    narrations_collection: str = "Narrations"
    audio_files_collection: str = "AudioFiles"
    counters_collection: str = "Counters"
    admin_accounts_collection: str = "AdminAccounts"
    admin_activity_logs_collection: str = "AdminActivityLogs"
    # Collection tài khoản người dùng theo ERD.
    user_accounts_collection: str = "UserAccounts"
    saved_places_collection: str = "SavedPlaces"
    listening_history_collection: str = "ListeningHistory"
    visitor_sessions_collection: str = "VisitorSessions"
    usage_events_collection: str = "UsageEvents"
    max_image_size_bytes: int = 10 * 1024 * 1024
    max_audio_size_bytes: int = 50 * 1024 * 1024


def get_settings() -> Settings:
    return Settings(
        mongodb_uri=_read_mongodb_uri(),
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
            "http://localhost:3000,http://localhost:5173,http://127.0.0.1:5173",
        ),
        image_storage_dir=Path(
            os.getenv(
                "IMAGE_STORAGE_DIR",
                str(BACKEND_ROOT / "uploads" / "images"),
            )
        ).resolve(),
        audio_storage_dir=Path(
            os.getenv(
                "AUDIO_STORAGE_DIR",
                str(BACKEND_ROOT / "uploads" / "audio"),
            )
        ).resolve(),
        categories_collection=os.getenv("MONGODB_CATEGORIES_COLLECTION", "Categories"),
        languages_collection=os.getenv("MONGODB_LANGUAGES_COLLECTION", "Languages"),
        audio_collection=os.getenv("MONGODB_AUDIO_COLLECTION", "PlaceAudios"),
        narrations_collection=os.getenv("MONGODB_NARRATIONS_COLLECTION", "Narrations"),
        audio_files_collection=os.getenv(
            "MONGODB_AUDIO_FILES_COLLECTION",
            "AudioFiles",
        ),
        counters_collection=os.getenv("MONGODB_COUNTERS_COLLECTION", "Counters"),
        admin_accounts_collection=os.getenv(
            "MONGODB_ADMIN_ACCOUNTS_COLLECTION",
            "AdminAccounts",
        ),
        admin_activity_logs_collection=os.getenv(
            "MONGODB_ADMIN_ACTIVITY_LOGS_COLLECTION",
            "AdminActivityLogs",
        ),
        # Cho phép đổi tên collection UserAccounts qua biến môi trường.
        user_accounts_collection=os.getenv(
            "MONGODB_USER_ACCOUNTS_COLLECTION",
            "UserAccounts",
        ),
        saved_places_collection=os.getenv(
            "MONGODB_SAVED_PLACES_COLLECTION",
            "SavedPlaces",
        ),
        listening_history_collection=os.getenv(
            "MONGODB_LISTENING_HISTORY_COLLECTION",
            "ListeningHistory",
        ),
        visitor_sessions_collection=os.getenv(
            "MONGODB_VISITOR_SESSIONS_COLLECTION",
            "VisitorSessions",
        ),
        usage_events_collection=os.getenv(
            "MONGODB_USAGE_EVENTS_COLLECTION",
            "UsageEvents",
        ),
        max_audio_size_bytes=int(
            os.getenv("MAX_AUDIO_SIZE_BYTES", str(50 * 1024 * 1024))
        ),
    )
