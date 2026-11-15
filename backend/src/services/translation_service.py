import json
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi import HTTPException


DEEPL_API_FREE_URL = "https://api-free.deepl.com/v2/translate"
DEEPL_API_PRO_URL = "https://api.deepl.com/v2/translate"
DEEPL_TARGET_LANGUAGE_CODES = {"zh-CN": "ZH-HANS"}
DEEPL_SOURCE_LANGUAGE_CODES = {"zh-CN": "ZH"}
TRANSLATION_RETRY_DELAYS = (0.5, 1, 2)


def translate_text(
    text: str,
    target_language: str,
    source_language: str | None,
    api_key: str | None,
) -> str:
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="DeepL API is not configured. Set DEEPL_API_KEY.",
        )

    target_code = DEEPL_TARGET_LANGUAGE_CODES.get(
        target_language,
        target_language.upper(),
    )
    body = {"text": [text], "target_lang": target_code}
    if source_language:
        body["source_lang"] = DEEPL_SOURCE_LANGUAGE_CODES.get(
            source_language,
            source_language.upper(),
        )
    base_url = DEEPL_API_FREE_URL if api_key.endswith(":fx") else DEEPL_API_PRO_URL
    request = Request(
        base_url,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"DeepL-Auth-Key {api_key}",
        },
        method="POST",
    )
    for attempt in range(len(TRANSLATION_RETRY_DELAYS) + 1):
        try:
            with urlopen(request, timeout=15) as response:
                payload = json.loads(response.read().decode("utf-8"))
            break
        except HTTPError as error:
            error.close()
            if (
                error.code == 429 or 500 <= error.code < 600
            ) and attempt < len(TRANSLATION_RETRY_DELAYS):
                time.sleep(TRANSLATION_RETRY_DELAYS[attempt])
                continue
            if error.code == 456:
                raise HTTPException(
                    status_code=503,
                    detail="DeepL API quota is exhausted (HTTP 456).",
                ) from error
            if error.code in (401, 403):
                raise HTTPException(
                    status_code=503,
                    detail="DeepL rejected the API key. Check DEEPL_API_KEY.",
                ) from error
            if error.code == 400:
                raise HTTPException(
                    status_code=422,
                    detail="DeepL rejected the source or target language.",
                ) from error
            if error.code == 429:
                raise HTTPException(
                    status_code=429,
                    detail="DeepL API rate limit reached. Please try again later.",
                ) from error
            raise HTTPException(
                status_code=502,
                detail=f"DeepL API request failed (HTTP {error.code}).",
            ) from error
        except (URLError, TimeoutError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise HTTPException(
                status_code=502,
                detail="DeepL API could not be reached or returned invalid data.",
            ) from error

    translations = payload.get("translations") if isinstance(payload, dict) else None
    if not isinstance(translations, list) or not translations:
        raise HTTPException(
            status_code=502,
            detail="DeepL API returned no translation.",
        )
    translated_text = translations[0].get("text") if isinstance(translations[0], dict) else None
    if not isinstance(translated_text, str) or not translated_text.strip():
        raise HTTPException(
            status_code=502,
            detail="DeepL API returned no translation.",
        )
    return translated_text.strip()
