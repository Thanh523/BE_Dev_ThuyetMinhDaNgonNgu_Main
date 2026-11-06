import { useCallback, useEffect, useRef, useState } from "react";

const LANGUAGES = [
  { code: "vi", name: "Tiếng Việt" },
  { code: "en", name: "English" },
  { code: "zh-CN", name: "中文（简体）" },
  { code: "ja", name: "日本語" },
  { code: "ko", name: "한국어" },
  { code: "fr", name: "Français" },
];

async function request(apiUrl, token, path, options = {}) {
  const headers = new Headers(options.headers);
  headers.set("Authorization", `Bearer ${token}`);
  if (options.body && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(`${apiUrl.replace(/\/+$/, "")}${path}`, {
    ...options,
    headers,
  });
  const payload = response.status === 204
    ? null
    : await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(
      typeof payload?.detail === "string"
        ? payload.detail
        : `Yêu cầu thất bại (HTTP ${response.status}).`,
    );
  }
  return payload;
}

function formatDuration(seconds) {
  if (!Number.isFinite(seconds) || seconds <= 0) return "Chưa rõ thời lượng";
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  return `${minutes}:${String(remainingSeconds).padStart(2, "0")}`;
}

export default function AudioManagement({ apiUrl, token, setError, setNotice }) {
  const [places, setPlaces] = useState([]);
  const [audios, setAudios] = useState([]);
  const [placeId, setPlaceId] = useState("");
  const [uploadFile, setUploadFile] = useState(null);
  const uploadInputRef = useRef(null);
  const [uploadLanguage, setUploadLanguage] = useState("vi");
  const [uploadTitle, setUploadTitle] = useState("");
  const [voiceName, setVoiceName] = useState("");
  const [editing, setEditing] = useState(null);
  const [editTitle, setEditTitle] = useState("");
  const [editLanguage, setEditLanguage] = useState("");
  const [editVoiceName, setEditVoiceName] = useState("");
  const [editIsActive, setEditIsActive] = useState(true);
  const [busy, setBusy] = useState(false);

  const loadPlaces = useCallback(async () => {
    const result = await request(
      apiUrl,
      token,
      "/api/admin/places?visibility=all&skip=0&limit=100",
    );
    setPlaces(result.items);
    if (!placeId && result.items[0]) {
      setPlaceId(String(result.items[0].PlaceId));
    }
  }, [apiUrl, token, placeId]);

  const loadAudios = useCallback(async () => {
    if (!placeId) {
      setAudios([]);
      return;
    }
    setAudios(
      await request(
        apiUrl,
        token,
        `/api/admin/places/${encodeURIComponent(placeId)}/audios`,
      ),
    );
  }, [apiUrl, token, placeId]);

  useEffect(() => {
    loadPlaces().catch((error) => setError(error.message));
  }, [loadPlaces, setError]);

  useEffect(() => {
    loadAudios().catch((error) => setError(error.message));
  }, [loadAudios, setError]);

  async function uploadAudio(event) {
    event.preventDefault();
    if (!placeId) return setError("Hãy chọn địa điểm trước khi tải audio.");
    if (!uploadFile) return setError("Hãy chọn tệp audio.");
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const body = new FormData();
      body.append("file", uploadFile);
      body.append("language", uploadLanguage);
      body.append("title", uploadTitle);
      body.append("voice_name", voiceName);
      await request(
        apiUrl,
        token,
        `/api/admin/places/${encodeURIComponent(placeId)}/audios/upload`,
        { method: "POST", body },
      );
      setUploadFile(null);
      if (uploadInputRef.current) uploadInputRef.current.value = "";
      setUploadTitle("");
      setVoiceName("");
      setNotice("Đã tải và gắn audio vào địa điểm, ngôn ngữ đã chọn.");
      await loadAudios();
    } catch (error) {
      setError(error.message);
    } finally {
      setBusy(false);
    }
  }

  function startEditing(audio) {
    setEditing(audio.AudioId);
    setEditTitle(audio.Title);
    setEditLanguage(audio.Language);
    setEditVoiceName(audio.VoiceName || audio.Voice || "");
    setEditIsActive(audio.IsActive !== false);
  }

  async function saveAudio(audio) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await request(apiUrl, token, `/api/admin/audios/${audio.AudioId}`, {
        method: "PATCH",
        body: JSON.stringify({
          title: editTitle,
          language: editLanguage,
          voice_name: editVoiceName,
          is_active: editIsActive,
        }),
      });
      setEditing(null);
      await loadAudios();
      setNotice("Đã cập nhật thông tin audio.");
    } catch (error) {
      setError(error.message);
    } finally {
      setBusy(false);
    }
  }

  async function replaceFile(audio, file) {
    if (!file) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const body = new FormData();
      body.append("file", file);
      await request(
        apiUrl,
        token,
        `/api/admin/audios/${encodeURIComponent(audio.AudioId)}/file`,
        { method: "PUT", body },
      );
      await loadAudios();
      setNotice(`Đã thay thế tệp audio "${audio.Title}".`);
    } catch (error) {
      setError(error.message);
    } finally {
      setBusy(false);
    }
  }

  async function deleteAudio(audio) {
    if (!window.confirm(`Xóa audio "${audio.Title}" và tệp của nó?`)) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await request(
        apiUrl,
        token,
        `/api/admin/audios/${encodeURIComponent(audio.AudioId)}`,
        { method: "DELETE" },
      );
      await loadAudios();
      setNotice("Đã xóa audio.");
    } catch (error) {
      setError(error.message);
    } finally {
      setBusy(false);
    }
  }

  const selectedPlace = places.find(
    (place) => String(place.PlaceId) === placeId,
  );
  const selectedAudioFolder = selectedPlace
    ? `${selectedPlace.PlaceId}-${selectedPlace.Slug || selectedPlace.PlaceId}`
    : "";

  return (
    <div className="places-manager">
      <section className="panel">
        <div className="section-heading">
          <div>
            <p className="eyebrow">AUDIO MANAGEMENT</p>
            <h2>Chọn địa điểm</h2>
          </div>
        </div>
        <label>
          Địa điểm *
          <select
            required
            value={placeId}
            onChange={(event) => setPlaceId(event.target.value)}
          >
            <option value="">Chọn địa điểm</option>
            {places.map((place) => (
              <option key={place.PlaceId} value={place.PlaceId}>
                {place.PlaceName}
              </option>
            ))}
          </select>
        </label>
        {!places.length && (
          <p className="hint">Chưa có địa điểm. Hãy tạo địa điểm trước.</p>
        )}
      </section>

      <section className="panel">
        <div className="section-heading">
          <div>
            <p className="eyebrow">UPLOAD AUDIO</p>
            <h2>Tải tệp audio lên</h2>
          </div>
          <span className="muted-count">MP3 · WAV · OGG · M4A · FLAC</span>
        </div>
        <form className="place-form" onSubmit={uploadAudio}>
          <label>
            Ngôn ngữ *
            <select
              required
              value={uploadLanguage}
              onChange={(event) => setUploadLanguage(event.target.value)}
            >
              {LANGUAGES.map((item) => (
                <option key={item.code} value={item.code}>{item.name}</option>
              ))}
            </select>
          </label>
          <label>
            Tiêu đề
            <input
              maxLength={200}
              value={uploadTitle}
              onChange={(event) => setUploadTitle(event.target.value)}
              placeholder="Tên audio"
            />
          </label>
          <label>
            Tên giọng đọc
            <input
              maxLength={100}
              value={voiceName}
              onChange={(event) => setVoiceName(event.target.value)}
              placeholder="Không bắt buộc"
            />
          </label>
          <label className="audio-file-picker">
            Tệp âm thanh *
            <input
              accept=".mp3,.wav,.ogg,.oga,.m4a,.flac,audio/*"
              ref={uploadInputRef}
              onChange={(event) => setUploadFile(event.target.files?.[0] ?? null)}
              required
              type="file"
            />
          </label>
          <button
            className="button load-button"
            disabled={busy || !placeId}
            type="submit"
          >
            {busy ? "Đang tải audio..." : "Tải audio lên"}
          </button>
        </form>
        <p className="hint">
          Tối đa 50 MB. Hệ thống kiểm tra định dạng và đọc thời lượng từ tệp.
          {selectedAudioFolder
            ? ` Tệp sẽ được lưu tại backend/uploads/audio/${selectedAudioFolder}.`
            : ""}
        </p>
      </section>

      <section className="panel">
        <div className="section-heading">
          <div>
            <p className="eyebrow">PLACE AUDIOS</p>
            <h2>Danh sách audio{selectedPlace ? ` · ${selectedPlace.PlaceName}` : ""}</h2>
          </div>
          <span className="muted-count">{audios.length} audio</span>
        </div>
        {!audios.length && <p className="hint">Địa điểm này chưa có audio.</p>}
        <div className="audio-management-list">
          {audios.map((audio) => (
            <article className="management-card" key={audio.AudioId}>
              {editing === audio.AudioId ? (
                <form
                  className="audio-edit-form"
                  onSubmit={(event) => {
                    event.preventDefault();
                    saveAudio(audio);
                  }}
                >
                  <label>
                    Tiêu đề
                    <input
                      maxLength={200}
                      required
                      value={editTitle}
                      onChange={(event) => setEditTitle(event.target.value)}
                    />
                  </label>
                  <label>
                    Ngôn ngữ
                    <select
                      value={editLanguage}
                      onChange={(event) => setEditLanguage(event.target.value)}
                    >
                      {LANGUAGES.map((item) => (
                        <option key={item.code} value={item.code}>{item.name}</option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Tên giọng đọc
                    <input
                      maxLength={100}
                      required
                      value={editVoiceName}
                      onChange={(event) => setEditVoiceName(event.target.value)}
                    />
                  </label>
                  <label className="audio-active-toggle">
                    <input
                      checked={editIsActive}
                      onChange={(event) => setEditIsActive(event.target.checked)}
                      type="checkbox"
                    />
                    Đang hoạt động
                  </label>
                  <div className="card-actions">
                    <button className="button" disabled={busy} type="submit">Lưu</button>
                    <button
                      className="button button-outline"
                      disabled={busy}
                      onClick={() => setEditing(null)}
                      type="button"
                    >
                      Hủy
                    </button>
                  </div>
                </form>
              ) : (
                <>
                  <div className="section-heading audio-card-heading">
                    <div>
                      <h3>{audio.Title}</h3>
                      <p>
                        {audio.Language} · {audio.VoiceName || audio.Voice}
                        {" · "}{formatDuration(audio.DurationSeconds)}
                      </p>
                    </div>
                    <span className={`status-pill ${audio.IsActive === false ? "" : "status-connected"}`}>
                      {audio.IsActive === false ? "Đã ẩn" : "Đang hoạt động"}
                    </span>
                  </div>
                  {audio.SourceText && (
                    <details className="audio-text-details">
                      <summary>Xem nội dung thuyết minh</summary>
                      <p>{audio.SourceText}</p>
                    </details>
                  )}
                  <audio
                    controls
                    preload="none"
                    src={`${apiUrl.replace(/\/+$/, "")}${audio.FileUrl}`}
                  />
                </>
              )}
              <div className="card-actions">
                {editing !== audio.AudioId && (
                  <>
                    <button
                      className="button button-outline"
                      disabled={busy}
                      onClick={() => startEditing(audio)}
                      type="button"
                    >
                      Sửa thông tin
                    </button>
                    <label className="button button-outline audio-replace-button">
                      Thay tệp
                      <input
                        accept=".mp3,.wav,.ogg,.oga,.m4a,.flac,audio/*"
                        disabled={busy}
                        onChange={(event) => {
                          const file = event.target.files?.[0];
                          event.target.value = "";
                          replaceFile(audio, file);
                        }}
                        type="file"
                      />
                    </label>
                    <button
                      className="button button-danger"
                      disabled={busy}
                      onClick={() => deleteAudio(audio)}
                      type="button"
                    >
                      Xóa
                    </button>
                  </>
                )}
              </div>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
