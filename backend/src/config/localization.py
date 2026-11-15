DEFAULT_CONTENT_LANGUAGE = "vi"
SUPPORTED_CONTENT_LANGUAGES = ("vi", "en", "zh-CN", "ja", "ko", "fr")
TRANSLATABLE_CONTENT_LANGUAGES = tuple(
    language
    for language in SUPPORTED_CONTENT_LANGUAGES
    if language != DEFAULT_CONTENT_LANGUAGE
)
