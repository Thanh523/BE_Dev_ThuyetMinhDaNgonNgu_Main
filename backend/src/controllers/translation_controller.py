import asyncio
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from src.config.settings import get_settings
from src.middlewares.admin_auth import require_admin
from src.services.translation_service import translate_text


router = APIRouter(
    prefix="/api/admin/translations",
    tags=["Translation suggestions"],
    dependencies=[Depends(require_admin)],
)


SupportedLanguage = Literal["vi", "en", "zh-CN", "ja", "ko", "fr"]


class TranslationSuggestionRequest(BaseModel):
    text: str = Field(min_length=1, max_length=100000)
    source_language: SupportedLanguage = "vi"
    target_language: SupportedLanguage


@router.post("/suggest")
async def suggest_translation(request: TranslationSuggestionRequest) -> dict[str, str]:
    translated_text = await asyncio.to_thread(
        translate_text,
        request.text.strip(),
        request.target_language,
        request.source_language,
        get_settings().deepl_api_key,
    )
    return {"translated_text": translated_text}
