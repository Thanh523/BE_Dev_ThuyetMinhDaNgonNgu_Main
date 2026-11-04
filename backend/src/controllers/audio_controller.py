from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field
from pymongo.errors import PyMongoError

from src.config.database import get_database
from src.config.settings import get_settings
from src.middlewares.admin_auth import require_admin
from src.repositories.place_audio_repository import PlaceAudioRepository
from src.repositories.place_image_repository import parse_place_id
from src.services.admin_audit_service import log_admin_activity
from src.services.audio_service import AudioService, LANGUAGE_NAMES


router = APIRouter(
    prefix="/api/admin",
    tags=["Audio management"],
    dependencies=[Depends(require_admin)],
)


class AudioCreate(BaseModel):
    source_text: str = Field(min_length=1, max_length=10000)
    language: str = Field(min_length=2, max_length=10)
    title: str = Field(default="", max_length=200)


class AudioUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class AudioView(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    audio_id: str = Field(alias="AudioId")
    place_id: int | str = Field(alias="PlaceId")
    language: str = Field(alias="Language")
    title: str = Field(alias="Title")
    source_text: str = Field(alias="SourceText")
    translated_text: str = Field(alias="TranslatedText")
    file_url: str = Field(alias="FileUrl")
    voice: str = Field(alias="Voice")
    created_at: datetime = Field(alias="CreatedAt")
    updated_at: datetime = Field(alias="UpdatedAt")


def _service(database) -> AudioService:
    settings = get_settings()
    return AudioService(
        PlaceAudioRepository(
            database,
            settings.places_collection,
            settings.audio_collection,
        ),
        settings,
    )


async def _log(database, claims: dict, action: str, audio_id: str, description: str) -> None:
    settings = get_settings()
    try:
        await log_admin_activity(
            database,
            settings.admin_activity_logs_collection,
            admin_id=claims["AdminId"],
            action=action,
            entity_name="PlaceAudios",
            entity_id=audio_id,
            description=description,
        )
    except PyMongoError as error:
        raise HTTPException(status_code=503, detail="Audio operation completed, but its activity log could not be saved.") from error


@router.get("/places/{place_id}/audios", response_model=list[AudioView], response_model_by_alias=False)
async def list_audios(place_id: str, database=Depends(get_database)) -> list[dict]:
    return await _service(database).list_for_place(parse_place_id(place_id))


@router.post("/places/{place_id}/audios", response_model=AudioView, response_model_by_alias=False, status_code=201)
async def create_audio(
    place_id: str,
    request: AudioCreate,
    database=Depends(get_database),
    claims: dict = Depends(require_admin),
) -> dict:
    audio = await _service(database).create(
        parse_place_id(place_id),
        request.source_text,
        request.language,
        request.title,
    )
    await _log(database, claims, "CREATE", audio["AudioId"], f"Created audio for place {audio['PlaceId']}.")
    return audio


@router.patch("/audios/{audio_id}", response_model=AudioView, response_model_by_alias=False)
async def update_audio(
    audio_id: str,
    request: AudioUpdate,
    database=Depends(get_database),
    claims: dict = Depends(require_admin),
) -> dict:
    audio = await _service(database).update(audio_id, request.title)
    await _log(database, claims, "UPDATE", audio_id, "Updated audio title.")
    return audio


@router.delete("/audios/{audio_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_audio(
    audio_id: str,
    database=Depends(get_database),
    claims: dict = Depends(require_admin),
) -> Response:
    await _service(database).delete(audio_id)
    await _log(database, claims, "DELETE", audio_id, "Deleted audio and its file.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/audio-options")
async def audio_options() -> dict:
    return {"languages": [{"code": code, "name": name} for code, name in LANGUAGE_NAMES.items()]}
