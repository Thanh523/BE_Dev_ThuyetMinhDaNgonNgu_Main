import { useCallback, useEffect, useState } from "react";

const PAGE_LIMIT = 20;

async function userRequest(apiUrl, token, path, options = {}) {
  const headers = new Headers(options.headers);
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  if (options.body) {
    headers.set("Content-Type", "application/json");
  }

  let response;
  try {
    response = await fetch(`${apiUrl.replace(/\/+$/, "")}${path}`, {
      ...options,
      headers,
    });
  } catch (requestError) {
    if (requestError instanceof TypeError) {
      throw new Error(
        `Không kết nối được backend tại ${apiUrl}. Kiểm tra backend đang chạy và CORS cho địa chỉ trang demo.`,
      );
    }
    throw requestError;
  }
  if (response.status === 204) {
    return null;
  }

  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = payload?.detail;
    throw new Error(
      typeof detail === "string"
        ? detail
        : `Yêu cầu thất bại (HTTP ${response.status}).`,
    );
  }
  return payload;
}

function formatDate(value) {
  if (!value) {
    return "—";
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : date.toLocaleString("vi-VN");
}

function newEventId() {
  return globalThis.crypto?.randomUUID?.()
    ?? `event-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export default function UserDemo({ apiUrl }) {
  const [authMode, setAuthMode] = useState("login");
  const [authForm, setAuthForm] = useState({
    full_name: "",
    email: "",
    password: "",
  });
  const [token, setToken] = useState("");
  const [profile, setProfile] = useState(null);
  const [savedPlaces, setSavedPlaces] = useState([]);
  const [listeningHistory, setListeningHistory] = useState([]);
  const [sessions, setSessions] = useState([]);
  const [usageEvents, setUsageEvents] = useState([]);
  const [selectedSessionId, setSelectedSessionId] = useState("");
  const [placeId, setPlaceId] = useState("");
  const [listeningForm, setListeningForm] = useState({
    audio_id: "",
    played_seconds: "0",
    is_completed: false,
  });
  const [eventForm, setEventForm] = useState({
    client_event_id: newEventId(),
    event_type: "audio_play",
    narration_id: "",
    audio_id: "",
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  // Tải dữ liệu cá nhân bằng token user; API tự giới hạn dữ liệu theo tài khoản.
  const refreshActivity = useCallback(async (activeToken) => {
    const [currentProfile, saved, history, sessionPage, eventPage] =
      await Promise.all([
        userRequest(apiUrl, activeToken, "/api/user/auth/me"),
        userRequest(
          apiUrl,
          activeToken,
          `/api/user/saved-places?skip=0&limit=${PAGE_LIMIT}`,
        ),
        userRequest(
          apiUrl,
          activeToken,
          `/api/user/listening-history?skip=0&limit=${PAGE_LIMIT}`,
        ),
        userRequest(
          apiUrl,
          activeToken,
          `/api/user/sessions?skip=0&limit=${PAGE_LIMIT}`,
        ),
        userRequest(
          apiUrl,
          activeToken,
          `/api/user/usage-events?skip=0&limit=${PAGE_LIMIT}`,
        ),
      ]);
    setProfile(currentProfile);
    setSavedPlaces(saved.items);
    setListeningHistory(history.items);
    setSessions(sessionPage.items);
    setUsageEvents(eventPage.items);
    setSelectedSessionId((current) => (
      current && sessionPage.items.some(
        (session) => session.SessionId === current && !session.EndedAt,
      )
        ? current
        : sessionPage.items.find((session) => !session.EndedAt)?.SessionId ?? ""
    ));
  }, [apiUrl]);

  // Đăng ký không tự đăng nhập; sau khi tạo tài khoản, người dùng đăng nhập riêng.
  async function submitAuth(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      if (authMode === "register") {
        await userRequest(apiUrl, "", "/api/user/auth/register", {
          method: "POST",
          body: JSON.stringify(authForm),
        });
        setAuthMode("login");
        setAuthForm((current) => ({ ...current, password: "" }));
        setNotice("Đăng ký thành công. Hãy đăng nhập bằng tài khoản vừa tạo.");
      } else {
        const result = await userRequest(apiUrl, "", "/api/user/auth/login", {
          method: "POST",
          body: JSON.stringify({
            email: authForm.email,
            password: authForm.password,
          }),
        });
        setToken(result.access_token);
        setAuthForm((current) => ({ ...current, password: "" }));
        setNotice("Đăng nhập user thành công.");
      }
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  }

  function logout() {
    setToken("");
    setProfile(null);
    setSavedPlaces([]);
    setListeningHistory([]);
    setSessions([]);
    setUsageEvents([]);
    setSelectedSessionId("");
    setNotice("Đã đăng xuất user.");
    setError("");
  }

  // Tạo một request action dùng chung để thống nhất trạng thái tải và thông báo.
  async function runAction(action, successMessage, afterSuccess) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await action();
      if (afterSuccess) {
        await afterSuccess();
      }
      setNotice(successMessage);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  }

  async function savePlace(event) {
    event.preventDefault();
    const id = Number(placeId);
    if (!Number.isSafeInteger(id) || id <= 0) {
      setError("Nhập PlaceId là số nguyên dương.");
      return;
    }
    await runAction(
      () => userRequest(apiUrl, token, `/api/user/saved-places/${id}`, {
        method: "POST",
      }),
      "Đã lưu địa điểm.",
      () => refreshActivity(token),
    );
  }

  async function removePlace(id) {
    await runAction(
      () => userRequest(
        apiUrl,
        token,
        `/api/user/saved-places/${encodeURIComponent(id)}`,
        { method: "DELETE" },
      ),
      "Đã bỏ lưu địa điểm.",
      () => refreshActivity(token),
    );
  }

  async function recordListening(event) {
    event.preventDefault();
    await runAction(
      () => userRequest(apiUrl, token, "/api/user/listening-history", {
        method: "POST",
        body: JSON.stringify({
          audio_id: listeningForm.audio_id,
          played_seconds: Number(listeningForm.played_seconds),
          is_completed: listeningForm.is_completed,
        }),
      }),
      "Đã ghi lịch sử nghe.",
      () => refreshActivity(token),
    );
  }

  async function createSession() {
    await runAction(
      () => userRequest(apiUrl, token, "/api/user/sessions", { method: "POST" }),
      "Đã tạo phiên truy cập.",
      () => refreshActivity(token),
    );
  }

  async function updateSession(session, endSession) {
    await runAction(
      () => userRequest(
        apiUrl,
        token,
        `/api/user/sessions/${encodeURIComponent(session.SessionId)}`,
        {
          method: "PATCH",
          body: JSON.stringify({ end_session: endSession }),
        },
      ),
      endSession ? "Đã kết thúc phiên." : "Đã cập nhật LastSeenAt.",
      () => refreshActivity(token),
    );
  }

  async function recordEvent(event) {
    event.preventDefault();
    if (!selectedSessionId) {
      setError("Hãy tạo hoặc chọn phiên đang hoạt động trước.");
      return;
    }
    await runAction(
      () => userRequest(apiUrl, token, "/api/user/usage-events", {
        method: "POST",
        body: JSON.stringify({
          client_event_id: eventForm.client_event_id,
          session_id: selectedSessionId,
          event_type: eventForm.event_type,
          narration_id: eventForm.narration_id || null,
          audio_id: eventForm.audio_id || null,
        }),
      }),
      "Đã ghi sự kiện sử dụng.",
      async () => {
        setEventForm((current) => ({
          ...current,
          client_event_id: newEventId(),
        }));
        await refreshActivity(token);
      },
    );
  }

  // Nếu admin khóa user ở nơi khác, yêu cầu API kế tiếp sẽ thu hồi phiên demo này.
  useEffect(() => {
    if (!token) {
      return;
    }
    refreshActivity(token).catch((requestError) => {
      setError(requestError.message);
      setToken("");
    });
  }, [token, refreshActivity]);

  return (
    <section className="user-demo">
      {!token ? (
        <section className="panel">
          <div className="section-heading">
            <div>
              <p className="eyebrow">USER SELF-SERVICE</p>
              <h2>{authMode === "login" ? "Đăng nhập người dùng" : "Tạo tài khoản user"}</h2>
            </div>
            <span className="status-pill">Demo user</span>
          </div>
          <form className="user-demo-form" onSubmit={submitAuth}>
            {authMode === "register" && (
              <label>
                Họ tên
                <input
                  autoComplete="name"
                  maxLength={200}
                  onChange={(event) => setAuthForm((current) => ({
                    ...current,
                    full_name: event.target.value,
                  }))}
                  required
                  value={authForm.full_name}
                />
              </label>
            )}
            <label>
              Email
              <input
                autoComplete="email"
                maxLength={254}
                onChange={(event) => setAuthForm((current) => ({
                  ...current,
                  email: event.target.value,
                }))}
                required
                type="email"
                value={authForm.email}
              />
            </label>
            <label>
              Mật khẩu {authMode === "register" && "(12-128 ký tự)"}
              <input
                autoComplete={authMode === "register" ? "new-password" : "current-password"}
                maxLength={128}
                minLength={authMode === "register" ? 12 : 1}
                onChange={(event) => setAuthForm((current) => ({
                  ...current,
                  password: event.target.value,
                }))}
                required
                type="password"
                value={authForm.password}
              />
            </label>
            <div className="user-demo-actions">
              <button className="button" disabled={busy} type="submit">
                {busy
                  ? "Đang xử lý..."
                  : authMode === "login"
                    ? "Đăng nhập"
                    : "Đăng ký"}
              </button>
              <button
                className="button button-outline"
                disabled={busy}
                onClick={() => {
                  setAuthMode((current) => (
                    current === "login" ? "register" : "login"
                  ));
                  setError("");
                  setNotice("");
                }}
                type="button"
              >
                {authMode === "login" ? "Chưa có tài khoản? Đăng ký" : "Đã có tài khoản? Đăng nhập"}
              </button>
            </div>
          </form>
          <p className="hint">
            Demo gọi API backend; JWT user chỉ lưu trong bộ nhớ trang và không
            được dùng để truy cập chức năng admin.
          </p>
        </section>
      ) : (
        <>
          <section className="panel">
            <div className="section-heading">
              <div>
                <p className="eyebrow">USER SESSION</p>
                <h2>Xin chào, {profile?.FullName ?? "người dùng"}</h2>
                <p className="subtitle">{profile?.Email}</p>
              </div>
              <div className="user-demo-actions">
                <span className="status-pill status-connected">Đã đăng nhập</span>
                <button className="button button-outline" onClick={logout} type="button">
                  Đăng xuất
                </button>
              </div>
            </div>
            <p className="hint">
              UserId: {profile?.UserId} · Đăng nhập gần nhất:{" "}
              {formatDate(profile?.LastLoginAt)}
            </p>
          </section>

          <section className="user-demo-grid">
            <section className="panel">
              <div className="section-heading">
                <div>
                  <p className="eyebrow">SAVED PLACES</p>
                  <h2>Địa điểm đã lưu</h2>
                </div>
                <span className="muted-count">{savedPlaces.length} mục gần nhất</span>
              </div>
              <form className="user-demo-inline-form" onSubmit={savePlace}>
                <label>
                  PlaceId
                  <input
                    inputMode="numeric"
                    onChange={(event) => setPlaceId(event.target.value)}
                    placeholder="Ví dụ: 1"
                    required
                    value={placeId}
                  />
                </label>
                <button className="button" disabled={busy} type="submit">
                  Lưu địa điểm
                </button>
              </form>
              <ul className="user-demo-list">
                {savedPlaces.map((item) => (
                  <li key={item.SavedPlaceId}>
                    <span>Địa điểm #{item.PlaceId} · {formatDate(item.SavedAt)}</span>
                    <button
                      className="text-button danger-text"
                      disabled={busy}
                      onClick={() => removePlace(item.PlaceId)}
                      type="button"
                    >
                      Bỏ lưu
                    </button>
                  </li>
                ))}
                {savedPlaces.length === 0 && <li className="muted-row">Chưa lưu địa điểm nào.</li>}
              </ul>
            </section>

            <section className="panel">
              <div className="section-heading">
                <div>
                  <p className="eyebrow">LISTENING HISTORY</p>
                  <h2>Lịch sử nghe</h2>
                </div>
                <span className="muted-count">{listeningHistory.length} lượt gần nhất</span>
              </div>
              <form className="user-demo-form" onSubmit={recordListening}>
                <label>
                  AudioId
                  <input
                    onChange={(event) => setListeningForm((current) => ({
                      ...current,
                      audio_id: event.target.value,
                    }))}
                    required
                    value={listeningForm.audio_id}
                  />
                </label>
                <label>
                  Số giây đã nghe
                  <input
                    inputMode="numeric"
                    min="0"
                    onChange={(event) => setListeningForm((current) => ({
                      ...current,
                      played_seconds: event.target.value,
                    }))}
                    required
                    type="number"
                    value={listeningForm.played_seconds}
                  />
                </label>
                <label className="user-demo-checkbox">
                  <input
                    checked={listeningForm.is_completed}
                    onChange={(event) => setListeningForm((current) => ({
                      ...current,
                      is_completed: event.target.checked,
                    }))}
                    type="checkbox"
                  />
                  Đã nghe hoàn tất
                </label>
                <button className="button" disabled={busy} type="submit">
                  Ghi lịch sử
                </button>
              </form>
              <ul className="user-demo-list">
                {listeningHistory.map((item) => (
                  <li key={item.ListeningHistoryId}>
                    <span>
                      Audio {item.AudioId} · {item.PlayedSeconds}s ·{" "}
                      {item.IsCompleted ? "Hoàn thành" : "Chưa hoàn thành"} ·{" "}
                      {formatDate(item.ListenedAt)}
                    </span>
                  </li>
                ))}
                {listeningHistory.length === 0 && <li className="muted-row">Chưa có lịch sử nghe.</li>}
              </ul>
            </section>

            <section className="panel">
              <div className="section-heading">
                <div>
                  <p className="eyebrow">VISITOR SESSIONS</p>
                  <h2>Phiên truy cập</h2>
                </div>
                <button className="button" disabled={busy} onClick={createSession} type="button">
                  Tạo phiên
                </button>
              </div>
              <ul className="user-demo-list">
                {sessions.map((session) => (
                  <li key={session.SessionId} className="user-demo-session">
                    <label className="user-demo-radio">
                      <input
                        checked={selectedSessionId === session.SessionId}
                        disabled={Boolean(session.EndedAt)}
                        onChange={() => setSelectedSessionId(session.SessionId)}
                        type="radio"
                        name="active-session"
                      />
                      <span>
                        <strong>{session.SessionId}</strong>
                        <small>
                          Bắt đầu {formatDate(session.StartedAt)} · cập nhật{" "}
                          {formatDate(session.LastSeenAt)} ·{" "}
                          {session.EndedAt ? "Đã kết thúc" : "Đang hoạt động"}
                        </small>
                      </span>
                    </label>
                    {!session.EndedAt && (
                      <div className="user-demo-actions">
                        <button
                          className="text-button"
                          disabled={busy}
                          onClick={() => updateSession(session, false)}
                          type="button"
                        >
                          Cập nhật
                        </button>
                        <button
                          className="text-button danger-text"
                          disabled={busy}
                          onClick={() => updateSession(session, true)}
                          type="button"
                        >
                          Kết thúc
                        </button>
                      </div>
                    )}
                  </li>
                ))}
                {sessions.length === 0 && <li className="muted-row">Chưa tạo phiên nào.</li>}
              </ul>
            </section>

            <section className="panel">
              <div className="section-heading">
                <div>
                  <p className="eyebrow">USAGE EVENTS</p>
                  <h2>Sự kiện sử dụng</h2>
                </div>
                <span className="muted-count">{usageEvents.length} sự kiện gần nhất</span>
              </div>
              <form className="user-demo-form" onSubmit={recordEvent}>
                <label>
                  ClientEventId (duy nhất cho mỗi event)
                  <input
                    onChange={(event) => setEventForm((current) => ({
                      ...current,
                      client_event_id: event.target.value,
                    }))}
                    required
                    value={eventForm.client_event_id}
                  />
                </label>
                <label>
                  Loại sự kiện
                  <input
                    maxLength={100}
                    onChange={(event) => setEventForm((current) => ({
                      ...current,
                      event_type: event.target.value,
                    }))}
                    required
                    value={eventForm.event_type}
                  />
                </label>
                <label>
                  NarrationId (không bắt buộc)
                  <input
                    onChange={(event) => setEventForm((current) => ({
                      ...current,
                      narration_id: event.target.value,
                    }))}
                    value={eventForm.narration_id}
                  />
                </label>
                <label>
                  AudioId (không bắt buộc)
                  <input
                    onChange={(event) => setEventForm((current) => ({
                      ...current,
                      audio_id: event.target.value,
                    }))}
                    value={eventForm.audio_id}
                  />
                </label>
                <button
                  className="button"
                  disabled={busy || !selectedSessionId}
                  type="submit"
                >
                  Ghi event
                </button>
              </form>
              <p className="hint">
                Event gắn với phiên đang chọn. Gửi lại cùng ClientEventId và
                nội dung để thử cơ chế retry không tạo bản ghi trùng.
              </p>
              <ul className="user-demo-list">
                {usageEvents.map((item) => (
                  <li key={item.EventId}>
                    <span>
                      {item.EventType} · phiên {item.SessionId} ·{" "}
                      {formatDate(item.CreatedAt)}
                    </span>
                  </li>
                ))}
                {usageEvents.length === 0 && <li className="muted-row">Chưa có event nào.</li>}
              </ul>
            </section>
          </section>
        </>
      )}

      {error && <div className="message message-error" role="alert">{error}</div>}
      {notice && !error && <div className="message message-success" role="status">{notice}</div>}
    </section>
  );
}
