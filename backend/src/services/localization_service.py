from fastapi import HTTPException

from src.config.localization import TRANSLATABLE_CONTENT_LANGUAGES


def normalize_translations(
    translations: dict | None,
    field_mapping: dict[str, str],
) -> dict[str, dict[str, str]]:
    if translations is None:
        return {}
    if not isinstance(translations, dict):
        raise HTTPException(status_code=422, detail="Translations must be an object.")

    normalized: dict[str, dict[str, str]] = {}
    for language, values in translations.items():
        if language not in TRANSLATABLE_CONTENT_LANGUAGES:
            raise HTTPException(
                status_code=422,
                detail=f"Unsupported translation language: {language}.",
            )
        if not isinstance(values, dict):
            raise HTTPException(
                status_code=422,
                detail=f"Translations for {language} must be an object.",
            )
        localized_fields: dict[str, str] = {}
        for request_field, database_field in field_mapping.items():
            value = values.get(request_field)
            if value is not None:
                text = value.strip()
                if text:
                    localized_fields[database_field] = text
        if localized_fields:
            normalized[language] = localized_fields
    return normalized
