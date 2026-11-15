import { useEffect, useRef, useState } from "react";
import UserPortalQr from "./components/UserPortalQr.jsx";
import UserDemo from "./pages/UserDemo.jsx";
import {
  translateUserText,
  USER_LANGUAGES,
} from "./i18n/userTranslations.js";

const DEFAULT_API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";
const VISIT_ID_STORAGE_KEY = "saigon-echo-website-visit";

async function updateWebsiteVisit(apiUrl, visitId, method, token, body) {
  const headers = new Headers();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  if (body) {
    headers.set("Content-Type", "application/json");
  }

  const visitPath = method === "start"
    ? ""
    : `/${encodeURIComponent(visitId)}${method === "claim" ? "/claim" : method === "release" ? "/release" : ""}`;
  const response = await fetch(
    `${apiUrl.replace(/\/+$/, "")}/api/user/website-visits${visitPath}`,
    {
      method: method === "start" ? "POST" : "PATCH",
      headers,
      body: body ? JSON.stringify(body) : undefined,
    },
  );
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = payload?.detail;
    throw new Error(
      typeof detail === "string"
        ? detail
        : `Ghi nhận lượt truy cập thất bại (HTTP ${response.status}).`,
    );
  }
  return payload;
}

export default function UserApp() {
  const [locale, setLocale] = useState(null);
  const [userToken, setUserToken] = useState("");
  const [visitReady, setVisitReady] = useState(false);
  const visitId = useRef(null);
  const previousToken = useRef("");
  const t = (text) => translateUserText(locale || "vi", text);

  useEffect(() => {
    let active = true;
    let heartbeat;
    try {
      visitId.current = sessionStorage.getItem(VISIT_ID_STORAGE_KEY);
      if (!visitId.current) {
        visitId.current = crypto.randomUUID();
        sessionStorage.setItem(VISIT_ID_STORAGE_KEY, visitId.current);
      }
    } catch (error) {
      console.error("Could not persist the website visit ID.", error);
      return undefined;
    }

    const startVisit = async () => {
      await updateWebsiteVisit(
        DEFAULT_API_URL,
        visitId.current,
        "start",
        "",
        { visit_id: visitId.current },
      );
      if (!active) {
        return;
      }
      setVisitReady(true);
      heartbeat = window.setInterval(() => {
        updateWebsiteVisit(
          DEFAULT_API_URL,
          visitId.current,
          "heartbeat",
          "",
          { end_visit: false },
        ).catch((error) => {
          console.error("Could not update the website visit heartbeat.", error);
        });
      }, 60 * 1000);
    };

    startVisit().catch((error) => {
      console.error("Could not start website visit tracking.", error);
    });

    return () => {
      active = false;
      if (heartbeat) {
        window.clearInterval(heartbeat);
      }
    };
  }, []);

  useEffect(() => {
    const priorToken = previousToken.current;
    previousToken.current = userToken;
    if (!visitReady || !visitId.current) {
      return;
    }

    if (userToken) {
      updateWebsiteVisit(
        DEFAULT_API_URL,
        visitId.current,
        "claim",
        userToken,
      ).catch((error) => {
        console.error("Could not link the website visit to the account.", error);
      });
    } else if (priorToken) {
      updateWebsiteVisit(
        DEFAULT_API_URL,
        visitId.current,
        "release",
        priorToken,
      ).catch((error) => {
        console.error("Could not unlink the website visit from the account.", error);
      });
    }
  }, [userToken, visitReady]);

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
      <UserDemo
        apiUrl={DEFAULT_API_URL}
        locale={locale}
        onTokenChange={setUserToken}
      />
      <footer className="page-footer">{t("Saigon Echo · User Portal")}</footer>
    </main>
  );
}
