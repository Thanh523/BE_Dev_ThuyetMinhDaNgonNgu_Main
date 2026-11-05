import { useState } from "react";
import CategoryManagement from "./pages/CategoryManagement.jsx";
import ImageManagement from "./pages/ImageManagement.jsx";
import PlaceManagement from "./pages/PlaceManagement.jsx";

import UserManagement from "./pages/UserManagement.jsx";

import AudioManagement from "./pages/AudioManagement.jsx";

const DEFAULT_API_URL = "http://localhost:8000";

function normalizedToken(token) {
  return token.trim().replace(/^Bearer\s+/i, "");
}

export default function App() {
  const [apiUrl, setApiUrl] = useState(DEFAULT_API_URL);
  const [token, setToken] = useState("");
  const [activePage, setActivePage] = useState("placeimages");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  function validateConnection() {
    if (!apiUrl.trim()) {
      setError("Vui lòng nhập địa chỉ backend.");
      return false;
    }
    return true;
  }

  async function login(event) {
    event.preventDefault();
    setError("");
    setNotice("");
    if (!validateConnection()) {
      return;
    }
    if (!username.trim() || !password) {
      setError("Nhập username và mật khẩu admin.");
      return;
    }

    setLoading(true);
    try {
      const response = await fetch(
        `${apiUrl.replace(/\/+$/, "")}/api/admin/auth/login`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ username: username.trim(), password }),
        },
      );
      const result = await response.json().catch(() => null);
      if (!response.ok) {
        const detail = result?.detail;
        throw new Error(
          typeof detail === "string"
            ? detail
            : `Yêu cầu thất bại (HTTP ${response.status}).`,
        );
      }
      setToken(result.access_token);
      setPassword("");
      setActivePage("placeimages");
      setNotice("Đăng nhập thành công. Phiên đăng nhập hết hạn sau 8 giờ.");
    } catch (loginError) {
      setError(loginError.message);
    } finally {
      setLoading(false);
    }
  }

  function logout() {
    setToken("");
    setNotice("Đã đăng xuất.");
    setError("");
  }

  const normalizedAuthToken = normalizedToken(token);

  return (
    <main className="page-shell">
      <header className="page-header">
        <div className="brand-mark" aria-hidden="true">SE</div>
        <div>
          <p className="eyebrow">SAIGON ECHO · DEMO</p>
          <h1>Saigon Echo Admin</h1>
          <p className="subtitle">
            Quản lý địa điểm, hình ảnh và danh mục trên các trang riêng.
          </p>
        </div>
      </header>

      <section className="panel connection-panel">
        <div className="section-heading">
          <div>
            <p className="eyebrow">ĐĂNG NHẬP</p>
            <h2>Backend và địa điểm</h2>
          </div>
          <span className={`status-pill ${token ? "status-connected" : ""}`}>
            {token ? "Đã đăng nhập" : "Chưa đăng nhập"}
          </span>
        </div>
        <form className="connection-form" onSubmit={login}>
          <label>
            Địa chỉ backend
            <input
              onChange={(event) => setApiUrl(event.target.value)}
              placeholder="http://localhost:8000"
              type="url"
              value={apiUrl}
            />
          </label>
          <label>
            Username hoặc email
            <input
              autoComplete="username"
              onChange={(event) => setUsername(event.target.value)}
              placeholder="Username hoặc email admin"
              value={username}
            />
          </label>
          <label>
            Mật khẩu admin
            <input
              autoComplete="current-password"
              onChange={(event) => setPassword(event.target.value)}
              placeholder="Mật khẩu"
              type="password"
              value={password}
            />
          </label>
          <div className="connection-actions">
            <button className="button load-button" disabled={loading} type="submit">
              {loading ? "Đang đăng nhập..." : "Đăng nhập"}
            </button>
            {token && (
              <button
                className="button button-outline"
                onClick={logout}
                type="button"
              >
                Đăng xuất
              </button>
            )}
          </div>
        </form>
        <p className="hint">
          Đăng nhập sẽ tự cấp JWT admin có hiệu lực 8 giờ. Token chỉ nằm trong
          bộ nhớ trang này và sẽ mất khi tải lại hoặc đóng trang.
        </p>
      </section>

      {error && (
        <div className="message message-error" role="alert">
          {error}
        </div>
      )}
      {notice && !error && (
        <div className="message message-success" role="status">
          {notice}
        </div>
      )}

      {token && (
        <nav className="admin-tabs" aria-label="Quản lý">
          <button
            aria-pressed={activePage === "places"}
            className={activePage === "places" ? "active" : ""}
            onClick={() => setActivePage("places")}
            type="button"
          >
            Địa điểm
          </button>
          <button
            aria-pressed={activePage === "placeimages"}
            className={activePage === "placeimages" ? "active" : ""}
            onClick={() => setActivePage("placeimages")}
            type="button"
          >
            Hình ảnh
          </button>
          <button
            aria-pressed={activePage === "categories"}
            className={activePage === "categories" ? "active" : ""}
            onClick={() => setActivePage("categories")}
            type="button"
          >
            Danh mục
          </button>
          <button

            aria-pressed={activePage === "users"}
            className={activePage === "users" ? "active" : ""}
            onClick={() => setActivePage("users")}
            type="button"
          >
            Người dùng

            aria-pressed={activePage === "audio"}
            className={activePage === "audio" ? "active" : ""}
            onClick={() => setActivePage("audio")}
            type="button"
          >
            Audio
          </button>
        </nav>
      )}

      {token && activePage === "places" && (
        <PlaceManagement
          apiUrl={apiUrl}
          setError={setError}
          setNotice={setNotice}
          token={normalizedAuthToken}
        />
      )}
      {token && activePage === "placeimages" && (
        <ImageManagement
          apiUrl={apiUrl}
          setError={setError}
          setNotice={setNotice}
          token={normalizedAuthToken}
        />
      )}
      {token && activePage === "categories" && (
        <CategoryManagement
          apiUrl={apiUrl}
          setError={setError}
          setNotice={setNotice}
          token={normalizedAuthToken}
        />
      )}

      {token && activePage === "users" && (
        <UserManagement

      {token && activePage === "audio" && (
        <AudioManagement
          apiUrl={apiUrl}
          setError={setError}
          setNotice={setNotice}
          token={normalizedAuthToken}
        />
      )}
      <footer className="page-footer">Saigon Echo · Admin demo</footer>
    </main>
  );
}
