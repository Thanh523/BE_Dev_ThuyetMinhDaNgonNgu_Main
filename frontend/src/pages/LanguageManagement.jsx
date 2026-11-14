import { useCallback, useEffect, useState } from "react";

async function request(apiUrl, token, path, options = {}) {
  const headers = new Headers(options.headers);
  headers.set("Authorization", `Bearer ${token}`);
  if (options.body) headers.set("Content-Type", "application/json");
  const response = await fetch(`${apiUrl.replace(/\/+$/, "")}${path}`, {
    ...options,
    headers,
  });
  if (response.status === 204) return null;
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(
      typeof payload?.detail === "string"
        ? payload.detail
        : `Yêu cầu thất bại (HTTP ${response.status}).`,
    );
  }
  return payload;
}

const EMPTY_FORM = { language_code: "", language_name: "" };

export default function LanguageManagement({
  apiUrl,
  token,
  setError,
  setNotice,
}) {
  const [languages, setLanguages] = useState([]);
  const [search, setSearch] = useState("");
  const [submittedSearch, setSubmittedSearch] = useState("");
  const [form, setForm] = useState(EMPTY_FORM);
  const [editingCode, setEditingCode] = useState(null);
  const [busy, setBusy] = useState(false);

  const loadLanguages = useCallback(async () => {
    const query = submittedSearch
      ? `?search=${encodeURIComponent(submittedSearch)}`
      : "";
    setLanguages(await request(apiUrl, token, `/api/admin/languages${query}`));
  }, [apiUrl, token, submittedSearch]);

  useEffect(() => {
    let active = true;
    setBusy(true);
    setError("");
    loadLanguages()
      .catch((error) => {
        if (active) setError(error.message);
      })
      .finally(() => {
        if (active) setBusy(false);
      });
    return () => {
      active = false;
    };
  }, [loadLanguages, setError]);

  function startCreate() {
    setEditingCode(null);
    setForm(EMPTY_FORM);
    setError("");
    setNotice("");
  }

  function startEdit(language) {
    setEditingCode(language.LanguageCode);
    setForm({
      language_code: language.LanguageCode,
      language_name: language.LanguageName,
    });
    setError("");
    setNotice("");
  }

  function cancelEdit() {
    setEditingCode(null);
    setForm(EMPTY_FORM);
  }

  async function saveLanguage(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const path = editingCode
        ? `/api/admin/languages/${encodeURIComponent(editingCode)}`
        : "/api/admin/languages";
      await request(apiUrl, token, path, {
        method: editingCode ? "PATCH" : "POST",
        body: JSON.stringify(form),
      });
      setForm(EMPTY_FORM);
      setEditingCode(null);
      setNotice(editingCode ? "Đã cập nhật ngôn ngữ." : "Đã thêm ngôn ngữ.");
      await loadLanguages();
    } catch (error) {
      setError(error.message);
    } finally {
      setBusy(false);
    }
  }

  async function toggleStatus(language) {
    const action = language.IsActive ? "ẩn" : "hiện";
    if (!window.confirm(`Bạn có chắc muốn ${action} ngôn ngữ "${language.LanguageName}"?`)) {
      return;
    }
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await request(
        apiUrl,
        token,
        `/api/admin/languages/${encodeURIComponent(language.LanguageCode)}/status`,
        {
          method: "PATCH",
          body: JSON.stringify({ is_active: !language.IsActive }),
        },
      );
      setNotice(language.IsActive ? "Đã ẩn ngôn ngữ." : "Đã hiện ngôn ngữ.");
      await loadLanguages();
    } catch (error) {
      setError(error.message);
    } finally {
      setBusy(false);
    }
  }

  async function deleteLanguage(language) {
    if (!window.confirm(`Xóa ngôn ngữ "${language.LanguageName}"?`)) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await request(
        apiUrl,
        token,
        `/api/admin/languages/${encodeURIComponent(language.LanguageCode)}`,
        { method: "DELETE" },
      );
      setNotice("Đã xóa ngôn ngữ.");
      await loadLanguages();
    } catch (error) {
      setError(error.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel language-panel">
      <div className="section-heading">
        <div>
          <p className="eyebrow">LANGUAGES</p>
          <h2>Quản lý ngôn ngữ</h2>
        </div>
        <span className="muted-count">{languages.length} ngôn ngữ</span>
      </div>

      <form
        className="language-search"
        onSubmit={(event) => {
          event.preventDefault();
          setSubmittedSearch(search.trim());
        }}
      >
        <input
          aria-label="Tìm kiếm ngôn ngữ"
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Tìm theo mã hoặc tên ngôn ngữ"
          value={search}
        />
        <button className="button button-outline" type="submit">Tìm kiếm</button>
        {submittedSearch && (
          <button
            className="text-button"
            onClick={() => {
              setSearch("");
              setSubmittedSearch("");
            }}
            type="button"
          >
            Xóa tìm kiếm
          </button>
        )}
      </form>

      <form className="language-form" onSubmit={saveLanguage}>
        <label>
          Mã ngôn ngữ *
          <input
            maxLength={10}
            onChange={(event) => setForm((current) => ({
              ...current,
              language_code: event.target.value,
            }))}
            placeholder="vi, en, ja..."
            required
            value={form.language_code}
          />
        </label>
        <label>
          Tên ngôn ngữ *
          <input
            maxLength={100}
            onChange={(event) => setForm((current) => ({
              ...current,
              language_name: event.target.value,
            }))}
            placeholder="Tiếng Việt"
            required
            value={form.language_name}
          />
        </label>
        <div className="language-form-actions">
          <button className="button" disabled={busy} type="submit">
            {editingCode ? "Lưu thay đổi" : "Thêm ngôn ngữ"}
          </button>
          {editingCode && (
            <button className="button button-outline" onClick={cancelEdit} type="button">
              Hủy
            </button>
          )}
        </div>
      </form>

      <div className="place-table-wrap language-table-wrap">
        <table className="place-table language-table">
          <thead>
            <tr>
              <th>MÃ</th>
              <th>TÊN NGÔN NGỮ</th>
              <th>TRẠNG THÁI</th>
              <th>THAO TÁC</th>
            </tr>
          </thead>
          <tbody>
            {languages.map((language) => (
              <tr key={language.LanguageCode}>
                <td><strong>{language.LanguageCode}</strong></td>
                <td>{language.LanguageName}</td>
                <td>
                  <span className={`status-pill ${language.IsActive ? "status-active" : "status-inactive"}`}>
                    {language.IsActive ? "Đang hiện" : "Đang ẩn"}
                  </span>
                </td>
                <td>
                  <div className="place-row-actions">
                    <button className="text-button" disabled={busy} onClick={() => startEdit(language)} type="button">
                      Sửa
                    </button>
                    <button className="text-button" disabled={busy} onClick={() => toggleStatus(language)} type="button">
                      {language.IsActive ? "Ẩn" : "Hiện"}
                    </button>
                    <button className="text-button danger-text" disabled={busy} onClick={() => deleteLanguage(language)} type="button">
                      Xóa
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {languages.length === 0 && (
              <tr>
                <td className="category-empty" colSpan="4">
                  {busy ? "Đang tải ngôn ngữ..." : "Không tìm thấy ngôn ngữ."}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
