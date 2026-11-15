import UserDemo from "./pages/UserDemo.jsx";

const DEFAULT_API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

export default function UserApp() {
  return (
    <main className="page-shell user-shell">
      <header className="page-header">
        <div className="brand-lockup">
          <div className="brand-mark" aria-hidden="true">SE</div>
          <div>
            <p className="eyebrow">SAIGON ECHO</p>
            <strong className="brand-name">Âm thanh kể chuyện</strong>
          </div>
        </div>
        <div className="portal-context">
          <span className="portal-dot" aria-hidden="true" />
          <span>Không gian khám phá</span>
        </div>
      </header>
      <section className="user-hero" aria-labelledby="user-hero-title">
        <div className="user-hero-copy">
          <p className="eyebrow">ĐI CHẬM LẠI · NGHE NHIỀU HƠN</p>
          <h1 id="user-hero-title">Mỗi góc phố đều có một câu chuyện.</h1>
          <p className="subtitle">
            Khám phá những địa điểm đáng nhớ và nghe thành phố kể chuyện bằng ngôn ngữ của bạn.
          </p>
        </div>
        <div className="user-hero-orbit" aria-hidden="true">
          <span className="hero-orbit-ring hero-orbit-ring-one" />
          <span className="hero-orbit-ring hero-orbit-ring-two" />
          <span className="hero-hero-mark">SE</span>
        </div>
      </section>
      <UserDemo apiUrl={DEFAULT_API_URL} />
      <footer className="page-footer">Saigon Echo · User Portal</footer>
    </main>
  );
}
