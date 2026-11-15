import { useState } from "react";
import UserPortalQr from "./components/UserPortalQr.jsx";
import UserDemo from "./pages/UserDemo.jsx";
import {
  translateUserText,
  USER_LANGUAGES,
} from "./i18n/userTranslations.js";

const DEFAULT_API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

export default function UserApp() {
  const [locale, setLocale] = useState(null);
  const t = (text) => translateUserText(locale || "vi", text);

  if (!locale) {
    return (
      <main className="page-shell user-shell user-language-shell">
        <header className="page-header">
          <div className="brand-lockup">
            <div className="brand-mark" aria-hidden="true">SE</div>
            <div>
              <p className="eyebrow">SAIGON ECHO</p>
              <strong className="brand-name">{t("Âm thanh kể chuyện")}</strong>
            </div>
          </div>
          <div className="portal-context">
            <span className="portal-dot" aria-hidden="true" />
            <span>{t("Không gian khám phá")}</span>
          </div>
        </header>
        <div className="user-entry-layout">
          <section aria-labelledby="language-picker-title" className="user-language-picker panel">
            <p className="eyebrow">SAIGON ECHO</p>
            <h1 id="language-picker-title">{t("Chọn ngôn ngữ để tiếp tục")}</h1>
            <p>{t("Ngôn ngữ này sẽ được dùng cho giao diện và nội dung địa điểm đã dịch.")}</p>
            <div className="user-language-options">
              {USER_LANGUAGES.map((language) => (
                <button
                  className="user-language-option"
                  key={language.code}
                  onClick={() => setLocale(language.code)}
                  type="button"
                >
                  <strong>{language.nativeName}</strong>
                  <span>{language.name}</span>
                </button>
              ))}
            </div>
          </section>
          <UserPortalQr />
        </div>
        <footer className="page-footer">{t("Saigon Echo · User Portal")}</footer>
      </main>
    );
  }

  return (
    <main className="page-shell user-shell">
      <header className="page-header">
        <div className="brand-lockup">
          <div className="brand-mark" aria-hidden="true">SE</div>
          <div>
            <p className="eyebrow">SAIGON ECHO</p>
            <strong className="brand-name">{t("Âm thanh kể chuyện")}</strong>
          </div>
        </div>
        <div className="portal-context">
          <span className="portal-dot" aria-hidden="true" />
          <span>{t("Không gian khám phá")}</span>
          <button
            className="user-locale-switch"
            onClick={() => setLocale(null)}
            type="button"
          >
            {USER_LANGUAGES.find((language) => language.code === locale)?.nativeName}
          </button>
        </div>
      </header>
      <section className="user-hero" aria-labelledby="user-hero-title">
        <div className="user-hero-copy">
          <p className="eyebrow">{t("ĐI CHẬM LẠI · NGHE NHIỀU HƠN")}</p>
          <h1 id="user-hero-title">{t("Mỗi góc phố đều có một câu chuyện.")}</h1>
          <p className="subtitle">
            {t("Khám phá những địa điểm đáng nhớ và nghe thành phố kể chuyện bằng ngôn ngữ của bạn.")}
          </p>
        </div>
        <div className="user-hero-orbit" aria-hidden="true">
          <span className="hero-orbit-ring hero-orbit-ring-one" />
          <span className="hero-orbit-ring hero-orbit-ring-two" />
          <span className="hero-hero-mark">SE</span>
        </div>
      </section>
      <UserDemo apiUrl={DEFAULT_API_URL} locale={locale} />
      <footer className="page-footer">{t("Saigon Echo · User Portal")}</footer>
    </main>
  );
}
