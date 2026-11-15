import { useCallback, useEffect, useState } from "react";

async function request(apiUrl, token, path, options = {}) {
  const headers = new Headers(options.headers);
  headers.set("Authorization", `Bearer ${token}`);
  if (options.body) headers.set("Content-Type", "application/json");
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

const EMPTY_FORM = { language_code: "", title: "", content: "", audio_id: "" };

export default function NarrationManagement({ apiUrl, token, setError, setNotice }) {
  const [places, setPlaces] = useState([]);
  const [languages, setLanguages] = useState([]);
  const [placeId, setPlaceId] = useState("");
  const [narrations, setNarrations] = useState([]);
  const [audios, setAudios] = useState([]);
  const [form, setForm] = useState(EMPTY_FORM);
  const [editingId, setEditingId] = useState(null);
  const [busy, setBusy] = useState(false);

  const loadPlaces = useCallback(async () => {
    const result = await request(
      apiUrl,
      token,
      "/api/admin/places?visibility=all&skip=0&limit=100",
    );
    setPlaces(result.items);
    if (!placeId && result.items[0]) setPlaceId(String(result.items[0].PlaceId));
  }, [apiUrl, token, placeId]);

  const loadLanguages = useCallback(async () => {
    setLanguages(await request(apiUrl, token, "/api/admin/narration-languages"));
  }, [apiUrl, token]);

  const loadNarrations = useCallback(async () => {
    if (!placeId) {
      setNarrations([]);
      return;
    }
    setNarrations(await request(
      apiUrl,
      token,
      `/api/admin/places/${encodeURIComponent(placeId)}/narrations`,
    ));
  }, [apiUrl, token, placeId]);

  const loadAudios = useCallback(async () => {
    if (!placeId) {
      setAudios([]);
      return;
    }
    setAudios(await request(
      apiUrl,
      token,
      `/api/admin/places/${encodeURIComponent(placeId)}/audios`,
    ));
  }, [apiUrl, token, placeId]);

  useEffect(() => {
    Promise.all([loadPlaces(), loadLanguages()]).catch((error) => setError(error.message));
  }, [loadPlaces, loadLanguages, setError]);

  useEffect(() => {
    loadNarrations().catch((error) => setError(error.message));
  }, [loadNarrations, setError]);

  useEffect(() => {
    loadAudios().catch((error) => setError(error.message));
  }, [loadAudios, setError]);

  function startCreate() {
    setEditingId(null);
    setForm({ ...EMPTY_FORM, language_code: languages[0]?.LanguageCode || "" });
    setError("");
    setNotice("");
  }

  function startEdit(narration) {
    setEditingId(narration.NarrationId);
    setForm({
      language_code: narration.LanguageCode,
      title: narration.Title,
      content: narration.Content,
      audio_id: audios.find(
        (audio) => String(audio.NarrationId) === String(narration.NarrationId),
      )?.AudioId || "",
    });
    setError("");
    setNotice("");
  }

  async function saveNarration(event) {
    event.preventDefault();
    if (!placeId) return setError("Hãy chọn địa điểm trước.");
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const previousAudioId = editingId
        ? audios.find((audio) => String(audio.NarrationId) === String(editingId))?.AudioId
        : null;
      const path = editingId
        ? `/api/admin/narrations/${editingId}`
        : `/api/admin/places/${placeId}/narrations`;
      const narrationPayload = {
        language_code: form.language_code,
        title: form.title,
        content: form.content,
      };
      const savedNarration = await request(apiUrl, token, path, {
        method: editingId ? "PATCH" : "POST",
        body: JSON.stringify(narrationPayload),
      });
      if (previousAudioId && previousAudioId !== form.audio_id) {
        await request(
          apiUrl,
          token,
          `/api/admin/audios/${encodeURIComponent(previousAudioId)}/narration`,
          {
            method: "PATCH",
            body: JSON.stringify({ narration_id: null }),
          },
        );
      }
      if (form.audio_id) {
        await request(
          apiUrl,
          token,
          `/api/admin/audios/${encodeURIComponent(form.audio_id)}/narration`,
          {
            method: "PATCH",
            body: JSON.stringify({ narration_id: savedNarration.NarrationId }),
          },
        );
      }
      setForm(EMPTY_FORM);
      setEditingId(null);
      setNotice(editingId ? "Đã cập nhật nội dung." : "Đã tạo nội dung thuyết minh.");
      await loadNarrations();
      await loadAudios();
    } catch (error) {
      setError(error.message);
    } finally {
      setBusy(false);
    }
  }

  async function deleteNarration(narration) {
    if (!window.confirm(`Xóa nội dung "${narration.Title}"?`)) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const linkedAudio = audios.find(
        (audio) => String(audio.NarrationId) === String(narration.NarrationId),
      );
      if (linkedAudio) {
        await request(
          apiUrl,
          token,
          `/api/admin/audios/${encodeURIComponent(linkedAudio.AudioId)}/narration`,
          {
            method: "PATCH",
            body: JSON.stringify({ narration_id: null }),
          },
        );
      }
      await request(apiUrl, token, `/api/admin/narrations/${narration.NarrationId}`, {
        method: "DELETE",
      });
      setNotice("Đã xóa nội dung thuyết minh.");
      await loadNarrations();
      await loadAudios();
    } catch (error) {
      setError(error.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel narration-management">
      <div className="section-heading">
        <div>
          <p className="eyebrow">NỘI DUNG</p>
          <h2>Quản lý thuyết minh</h2>
        </div>
        <button className="button" disabled={!placeId} onClick={startCreate} type="button">
          Thêm nội dung
        </button>
      </div>
      <label className="management-select">
        Địa điểm
        <select onChange={(event) => setPlaceId(event.target.value)} value={placeId}>
          <option value="">Chọn địa điểm</option>
          {places.map((place) => (
            <option key={place.PlaceId} value={place.PlaceId}>{place.PlaceName}</option>
          ))}
        </select>
      </label>

      {(editingId || form.language_code) && (
        <form className="narration-form" onSubmit={saveNarration}>
          <label>
            Ngôn ngữ
            <select
              disabled={Boolean(editingId)}
              onChange={(event) => setForm({ ...form, language_code: event.target.value })}
              value={form.language_code}
            >
              <option value="">Chọn ngôn ngữ</option>
              {languages.map((language) => (
                <option key={language.LanguageCode} value={language.LanguageCode}>
                  {language.LanguageName} ({language.LanguageCode})
                </option>
              ))}
            </select>
          </label>
          <label>
            Tiêu đề
            <input
              onChange={(event) => setForm({ ...form, title: event.target.value })}
              value={form.title}
            />
          </label>
          <label>
            Audio
            <select
              onChange={(event) => setForm({ ...form, audio_id: event.target.value })}
              value={form.audio_id || ""}
            >
              <option value="">Không gắn audio</option>
              {audios
                .filter((audio) => audio.Language === form.language_code)
                .map((audio) => (
                  <option key={audio.AudioId} value={audio.AudioId}>
                    {audio.Title} ({audio.AudioId.slice(0, 8)})
                  </option>
                ))}
            </select>
          </label>
          <label className="narration-content-field">
            Nội dung
            <textarea
              onChange={(event) => setForm({ ...form, content: event.target.value })}
              rows="6"
              value={form.content}
            />
          </label>
          <div className="form-actions">
            <button className="button" disabled={busy} type="submit">
              {busy ? "Đang lưu..." : editingId ? "Lưu thay đổi" : "Tạo nội dung"}
            </button>
            <button
              className="button button-outline"
              onClick={() => { setEditingId(null); setForm(EMPTY_FORM); }}
              type="button"
            >
              Hủy
            </button>
          </div>
        </form>
      )}

      <div className="narration-list">
        {!narrations.length && <p className="empty-note">Chưa có nội dung cho địa điểm này.</p>}
        {narrations.map((narration) => (
          <article className="management-card" key={narration.NarrationId}>
            <div className="section-heading">
              <div>
                <p className="eyebrow">{narration.LanguageCode}</p>
                <h3>{narration.Title}</h3>
              </div>
              <div className="card-actions">
                <button className="button button-outline" onClick={() => startEdit(narration)} type="button">
                  Sửa
                </button>
                <button className="button button-danger" onClick={() => deleteNarration(narration)} type="button">
                  Xóa
                </button>
              </div>
            </div>
            <p className="narration-content">{narration.Content}</p>
          </article>
        ))}
      </div>
    </section>
  );
}
