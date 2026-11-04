import { useCallback, useEffect, useState } from "react";

async function request(apiUrl, token, path, options = {}) {
  const headers = new Headers(options.headers);
  headers.set("Authorization", `Bearer ${token}`);
  if (options.body) headers.set("Content-Type", "application/json");
  const response = await fetch(`${apiUrl.replace(/\/+$/, "")}${path}`, {
    ...options,
    headers,
  });
  const payload = response.status === 204 ? null : await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(typeof payload?.detail === "string" ? payload.detail : `Yêu cầu thất bại (HTTP ${response.status}).`);
  }
  return payload;
}

export default function AudioManagement({ apiUrl, token, setError, setNotice }) {
  const [places, setPlaces] = useState([]);
  const [audios, setAudios] = useState([]);
  const [placeId, setPlaceId] = useState("");
  const [language, setLanguage] = useState("en");
  const [title, setTitle] = useState("");
  const [sourceText, setSourceText] = useState("");
  const [editing, setEditing] = useState(null);
  const [editTitle, setEditTitle] = useState("");
  const [busy, setBusy] = useState(false);

  const loadPlaces = useCallback(async () => {
    const result = await request(apiUrl, token, "/api/admin/places?visibility=all&skip=0&limit=100");
    setPlaces(result.items);
    if (!placeId && result.items[0]) setPlaceId(String(result.items[0].PlaceId));
  }, [apiUrl, token, placeId]);

  const loadAudios = useCallback(async () => {
    if (!placeId) return setAudios([]);
    setAudios(await request(apiUrl, token, `/api/admin/places/${placeId}/audios`));
  }, [apiUrl, token, placeId]);

  useEffect(() => { loadPlaces().catch((error) => setError(error.message)); }, [loadPlaces, setError]);
  useEffect(() => { loadAudios().catch((error) => setError(error.message)); }, [loadAudios, setError]);

  async function createAudio(event) {
    event.preventDefault();
    if (!placeId) return setError("Hãy chọn địa điểm.");
    setBusy(true); setError(""); setNotice("");
    try {
      await request(apiUrl, token, `/api/admin/places/${placeId}/audios`, {
        method: "POST",
        body: JSON.stringify({ source_text: sourceText, language, title }),
      });
      setSourceText(""); setTitle(""); setNotice("Đã dịch và tạo audio.");
      await loadAudios();
    } catch (error) { setError(error.message); } finally { setBusy(false); }
  }

  async function saveTitle(audio) {
    setBusy(true); setError("");
    try {
      await request(apiUrl, token, `/api/admin/audios/${audio.AudioId}`, {
        method: "PATCH", body: JSON.stringify({ title: editTitle }),
      });
      setEditing(null); await loadAudios(); setNotice("Đã cập nhật tiêu đề audio.");
    } catch (error) { setError(error.message); } finally { setBusy(false); }
  }

  async function deleteAudio(audio) {
    if (!window.confirm(`Xóa audio "${audio.Title}"?`)) return;
    setBusy(true); setError("");
    try {
      await request(apiUrl, token, `/api/admin/audios/${audio.AudioId}`, { method: "DELETE" });
      await loadAudios(); setNotice("Đã xóa audio.");
    } catch (error) { setError(error.message); } finally { setBusy(false); }
  }

  return (
    <div className="places-manager">
      <section className="panel">
        <div className="section-heading"><div><p className="eyebrow">AUDIO MANAGEMENT</p><h2>Tạo thuyết minh audio</h2></div></div>
        <form className="place-form" onSubmit={createAudio}>
          <label>Địa điểm *
            <select required value={placeId} onChange={(event) => setPlaceId(event.target.value)}>
              <option value="">Chọn địa điểm</option>
              {places.map((place) => <option key={place.PlaceId} value={place.PlaceId}>{place.PlaceName}</option>)}
            </select>
          </label>
          <label>Ngôn ngữ *
            <select value={language} onChange={(event) => setLanguage(event.target.value)}>
              <option value="vi">Tiếng Việt</option><option value="en">English</option>
              <option value="zh-CN">Chinese</option><option value="ja">Japanese</option>
              <option value="ko">Korean</option><option value="fr">French</option>
            </select>
          </label>
          <label>Tiêu đề<input maxLength={200} value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Ví dụ: Giới thiệu Dinh Độc Lập" /></label>
          <label>Nội dung tiếng Việt *
            <textarea required maxLength={10000} rows="7" value={sourceText} onChange={(event) => setSourceText(event.target.value)} placeholder="Nhập nội dung thuyết minh..." />
          </label>
          <button className="button load-button" disabled={busy || !placeId} type="submit">{busy ? "Đang tạo audio..." : "Dịch và tạo audio"}</button>
        </form>
        <p className="hint">Mỗi địa điểm chỉ tạo một audio cho mỗi ngôn ngữ. Audio được lưu dạng MP3.</p>
      </section>
      <section className="panel">
        <div className="section-heading"><h2>Audio của địa điểm</h2></div>
        {!audios.length && <p className="hint">Chưa có audio.</p>}
        {audios.map((audio) => (
          <article className="management-card" key={audio.AudioId}>
            {editing === audio.AudioId ? (
              <form onSubmit={(event) => { event.preventDefault(); saveTitle(audio); }}>
                <input value={editTitle} onChange={(event) => setEditTitle(event.target.value)} required />
                <button className="button" disabled={busy}>Lưu</button>
                <button className="button button-outline" type="button" onClick={() => setEditing(null)}>Hủy</button>
              </form>
            ) : <><h3>{audio.Title}</h3><p>{audio.Language} · {audio.Voice}</p></>}
            <audio controls src={`${apiUrl.replace(/\/+$/, "")}${audio.FileUrl}`} />
            <div className="card-actions">
              <button className="button button-outline" onClick={() => { setEditing(audio.AudioId); setEditTitle(audio.Title); }} type="button">Sửa tiêu đề</button>
              <button className="button button-danger" onClick={() => deleteAudio(audio)} type="button">Xóa</button>
            </div>
          </article>
        ))}
      </section>
    </div>
  );
}
