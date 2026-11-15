import { useState } from "react";
import { Navigate, NavLink, useLocation, useNavigate } from "react-router-dom";
import AudioManagement from "./pages/AudioManagement.jsx";
import CategoryManagement from "./pages/CategoryManagement.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import ImageManagement from "./pages/ImageManagement.jsx";
import LanguageManagement from "./pages/LanguageManagement.jsx";
import ActivityLogManagement from "./pages/ActivityLogManagement.jsx";
import NarrationManagement from "./pages/NarrationManagement.jsx";
import PlaceManagement from "./pages/PlaceManagement.jsx";
import UserManagement from "./pages/UserManagement.jsx";

const DEFAULT_API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

function normalizedToken(token) {
  return token.trim().replace(/^Bearer\s+/i, "");
}

const adminPages = [
  { path: "dashboard", label: "Thống kê" },
  { path: "places", label: "Địa điểm" },
  { path: "placeimages", label: "Hình ảnh" },
  { path: "categories", label: "Danh mục" },
  { path: "languages", label: "Ngôn ngữ" },
  { path: "users", label: "Người dùng" },
  { path: "audio", label: "Audio" },
  { path: "narrations", label: "Thuyết minh" },
  { path: "activity-logs", label: "Nhật ký" },
];

export default function AdminApp() {
  const navigate = useNavigate();
  const location = useLocation();
  const [token, setToken] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const isLoginPage = location.pathname === "/admin/login";
  const activePage = location.pathname.split("/")[2] || "dashboard";

  async function login(event) {
    event.preventDefault();
    setError("");
    setNotice("");
    if (!username.trim() || !password) {
      setError("Nhập username và mật khẩu admin.");
      return;
    }

    setLoading(true);
    try {
      const baseUrl = DEFAULT_API_URL.replace(/\/+$/, "");
      const requestUrls = [
        `${baseUrl}/api/admin/auth/login`,
        `${baseUrl.replace(
          /^http:\/\/localhost(?=:|\/|$)/i,
          "http://127.0.0.1",
        )}/api/admin/auth/login`,
      ].filter((url, index, urls) => urls.indexOf(url) === index);
      let lastNetworkError = null;
      let result = null;

      for (const requestUrl of requestUrls) {
        let response;
        try {
          response = await fetch(requestUrl, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username: username.trim(), password }),
          });
        } catch (requestError) {
          lastNetworkError = requestError;
          continue;
        }

        result = await response.json().catch(() => null);
        if (!response.ok) {
          const detail = result?.detail;
          throw new Error(
            `Đăng nhập trả về HTTP ${response.status}` +
            (typeof detail === "string" ? `: ${detail}` : ".") +
            ` URL: ${requestUrl}`,
          );
        }
        break;
      }

      if (!result) {
        const reason = lastNetworkError instanceof Error
          ? lastNetworkError.message
          : String(lastNetworkError);
        throw new Error(
          `Không thể kết nối máy chủ đăng nhập. ` +
          `Đã thử: ${requestUrls.join(" hoặc ")}. Chi tiết: ${reason}`,
        );
      }
      setToken(result.access_token);
      setPassword("");
      setNotice("Đăng nhập thành công. Phiên đăng nhập hết hạn sau 8 giờ.");
      navigate("/admin/dashboard");
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
    navigate("/admin/login");
  }

  if (!token && !isLoginPage) {
    return <Navigate replace to="/admin/login" />;
  }
  if (token && !isLoginPage && !adminPages.some((page) => page.path === activePage)) {
    return <Navigate replace to="/admin/dashboard" />;
  }

  const normalizedAuthToken = normalizedToken(token);

  return (
    <main className="page-shell admin-shell">
      <header className="page-header">
        <div className="brand-lockup">
          <div className="brand-mark" aria-hidden="true">SE</div>
          <div>
            <p className="eyebrow">SAIGON ECHO · STUDIO</p>
            <strong className="brand-name">Bảng điều khiển</strong>
          </div>
        </div>
        <div className="admin-header-copy">
          <p className="eyebrow">KHÔNG GIAN QUẢN TRỊ</p>
          <h1>Điều hành nội dung thành phố</h1>
          <p className="subtitle">Quản lý địa điểm, audio và trải nghiệm người nghe.</p>
        </div>
      </header>

      {isLoginPage ? (
        <section className="panel connection-panel admin-login-panel">
          <div className="section-heading">
            <div>
              <p className="eyebrow">KHU VỰC ADMIN</p>
              <h2>Đăng nhập quản trị</h2>
            </div>
            <span className="status-pill">Chưa đăng nhập</span>
          </div>
          <form className="admin-login-form" onSubmit={login}>
            <label>
              Username hoặc email
              <input
                autoComplete="username"
                onChange={(event) => setUsername(event.target.value)}
                value={username}
              />
            </label>
            <label>
              Mật khẩu admin
              <input
                autoComplete="current-password"
                onChange={(event) => setPassword(event.target.value)}
                type="password"
                value={password}
              />
            </label>
            <button className="button load-button" disabled={loading} type="submit">
              {loading ? "Đang đăng nhập..." : "Đăng nhập"}
            </button>
          </form>
          <p className="hint">JWT admin chỉ được giữ trong bộ nhớ của phiên trang hiện tại.</p>
        </section>
      ) : (
        <>
          {error && <div className="message message-error" role="alert">{error}</div>}
          {notice && !error && <div className="message message-success" role="status">{notice}</div>}
          <nav className="admin-tabs" aria-label="Điều hướng quản trị">
            {adminPages.map((page) => (
              <NavLink
                className={({ isActive }) => (isActive ? "active" : "")}
                key={page.path}
                to={`/admin/${page.path}`}
              >
                {page.label}
              </NavLink>
            ))}
            <button className="admin-logout-button" onClick={logout} type="button">
              Đăng xuất
            </button>
          </nav>
          {activePage === "dashboard" && (
            <Dashboard apiUrl={DEFAULT_API_URL} setError={setError} token={normalizedAuthToken} />
          )}
          {activePage === "places" && (
            <PlaceManagement
              apiUrl={DEFAULT_API_URL}
              setError={setError}
              setNotice={setNotice}
              token={normalizedAuthToken}
            />
          )}
          {activePage === "placeimages" && (
            <ImageManagement
              apiUrl={DEFAULT_API_URL}
              setError={setError}
              setNotice={setNotice}
              token={normalizedAuthToken}
            />
          )}
          {activePage === "categories" && (
            <CategoryManagement
              apiUrl={DEFAULT_API_URL}
              setError={setError}
              setNotice={setNotice}
              token={normalizedAuthToken}
            />
          )}
          {activePage === "languages" && (
            <LanguageManagement
              apiUrl={DEFAULT_API_URL}
              setError={setError}
              setNotice={setNotice}
              token={normalizedAuthToken}
            />
          )}
          {activePage === "users" && (
            <UserManagement
              apiUrl={DEFAULT_API_URL}
              setError={setError}
              setNotice={setNotice}
              token={normalizedAuthToken}
            />
          )}
          {activePage === "audio" && (
            <AudioManagement
              apiUrl={DEFAULT_API_URL}
              setError={setError}
              setNotice={setNotice}
              token={normalizedAuthToken}
            />
          )}
          {activePage === "narrations" && (
            <NarrationManagement
              apiUrl={DEFAULT_API_URL}
              setError={setError}
              setNotice={setNotice}
              token={normalizedAuthToken}
            />
          )}
          {activePage === "activity-logs" && (
            <ActivityLogManagement
              apiUrl={DEFAULT_API_URL}
              setError={setError}
              token={normalizedAuthToken}
            />
          )}
        </>
      )}
      <footer className="page-footer">Saigon Echo · Admin Portal</footer>
    </main>
  );
}
