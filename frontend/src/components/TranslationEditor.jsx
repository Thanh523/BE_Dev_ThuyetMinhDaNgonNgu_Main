import { useState } from "react";
import { USER_LANGUAGES } from "../i18n/userTranslations.js";

const LANGUAGES = USER_LANGUAGES
  .filter((language) => language.code !== "vi")
  .map((language) => ({ code: language.code, name: language.nativeName }));

async function suggestTranslation(apiUrl, token, text, targetLanguage) {
  const response = await fetch(
    `${apiUrl.replace(/\/+$/, "")}/api/admin/translations/suggest`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        text,
        source_language: "vi",
        target_language: targetLanguage,
      }),
    },
  );
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(
      typeof payload?.detail === "string"
        ? payload.detail
        : `Không thể dịch nội dung (HTTP ${response.status}).`,
    );
  }
  if (typeof payload?.translated_text !== "string" || !payload.translated_text.trim()) {
    throw new Error("DeepL không trả về nội dung bản dịch.");
  }
  return payload.translated_text;
}

export default function TranslationEditor({
  apiUrl,
  token,
  fields,
  translations,
  onChange,
  setError,
  disabled = false,
}) {
  const [activeLanguage, setActiveLanguage] = useState(LANGUAGES[0].code);
  const [suggestingField, setSuggestingField] = useState("");
  const language = LANGUAGES.find((item) => item.code === activeLanguage);

  async function suggest(field) {
    const sourceText = field.sourceText.trim();
    if (!sourceText) {
      setError("Nhập nội dung tiếng Việt trước khi yêu cầu DeepL dịch.");
      return;
    }

    setSuggestingField(field.key);
    setError("");
    try {
      const translated = await suggestTranslation(
        apiUrl,
        token,
        sourceText,
        activeLanguage,
      );
      onChange({
        ...translations,
        [activeLanguage]: {
          ...translations[activeLanguage],
          [field.key]: translated,
        },
      });
    } catch (error) {
      setError(error.message);
    } finally {
      setSuggestingField("");
    }
  }

  return (
    <section className="translation-editor">
      <p className="hint">
        Bản dịch do DeepL gợi ý cần được kiểm tra trước khi lưu.
      </p>
      <div aria-label="Ngôn ngữ bản dịch" className="translation-language-tabs">
        {LANGUAGES.map((item) => (
          <button
            aria-pressed={activeLanguage === item.code}
            className={activeLanguage === item.code ? "active" : ""}
            disabled={disabled || Boolean(suggestingField)}
            key={item.code}
            onClick={() => setActiveLanguage(item.code)}
            type="button"
          >
            {item.name}
          </button>
        ))}
      </div>
      <div className="translation-fields">
        {fields.map((field) => (
          <label key={field.key}>
            {field.label} · {language.name}
            {field.multiline ? (
              <textarea
                disabled={disabled || Boolean(suggestingField)}
                maxLength={field.maxLength}
                onChange={(event) => onChange({
                  ...translations,
                  [activeLanguage]: {
                    ...translations[activeLanguage],
                    [field.key]: event.target.value,
                  },
                })}
                rows={3}
                value={translations[activeLanguage]?.[field.key] || ""}
              />
            ) : (
              <input
                disabled={disabled || Boolean(suggestingField)}
                maxLength={field.maxLength}
                onChange={(event) => onChange({
                  ...translations,
                  [activeLanguage]: {
                    ...translations[activeLanguage],
                    [field.key]: event.target.value,
                  },
                })}
                value={translations[activeLanguage]?.[field.key] || ""}
              />
            )}
            <button
              className="text-button translation-suggest-button"
              disabled={
                disabled
                || Boolean(suggestingField)
                || !field.sourceText.trim()
              }
              onClick={() => suggest(field)}
              type="button"
            >
              {suggestingField === field.key ? "Đang dịch..." : "Gợi ý dịch bằng DeepL"}
            </button>
          </label>
        ))}
      </div>
    </section>
  );
}
