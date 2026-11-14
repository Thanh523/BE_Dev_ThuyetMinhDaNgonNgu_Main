import { NavLink } from "react-router-dom";
import UserDemo from "./pages/UserDemo.jsx";

const DEFAULT_API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

export default function UserApp() {
  return (
    <main className="page-shell user-shell">
      <header className="page-header">
        <div className="brand-mark" aria-hidden="true">SE</div>
        <div>
          <p className="eyebrow">SAIGON ECHO · USER</p>
          <h1>Khám phá thành phố bằng âm thanh</h1>
          <p className="subtitle">
            Tìm địa điểm, nghe thuyết minh đa ngôn ngữ và lưu lại hành trình của bạn.
          </p>
        </div>
        <NavLink className="portal-link" to="/admin">Admin</NavLink>
      </header>
      <UserDemo apiUrl={DEFAULT_API_URL} />
      <footer className="page-footer">Saigon Echo · User Portal</footer>
    </main>
  );
}
