import { useCallback, useEffect, useState } from "react";

async function adminRequest(apiUrl, token, path, options = {}) {
  const headers = new Headers(options.headers);
  headers.set("Authorization", `Bearer ${token}`);
  if (options.body) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(
    `${apiUrl.replace(/\/+$/, "")}${path}`,
    { ...options, headers },
  );
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

const EMPTY_FORM = { category_name: "", description: "" };

export default function CategoryManagement({
  apiUrl,
  token,
  setError,
  setNotice,
}) {
  const [categories, setCategories] = useState([]);
  const [form, setForm] = useState(EMPTY_FORM);
  const [editingCategory, setEditingCategory] = useState(null);
  const [busy, setBusy] = useState(false);

  const loadCategories = useCallback(async () => {
    const result = await adminRequest(apiUrl, token, "/api/admin/categories");
    setCategories(result);
  }, [apiUrl, token]);

  useEffect(() => {
    let active = true;
    setBusy(true);
    setError("");
    adminRequest(apiUrl, token, "/api/admin/categories")
      .then((result) => {
        if (active) setCategories(result);
      })
      .catch((error) => {
        if (active) setError(error.message);
      })
      .finally(() => {
        if (active) setBusy(false);
      });
    return () => {
      active = false;
    };
  }, [apiUrl, token, setError]);

  async function saveCategory(event) {
    event.preventDefault();
    setError("");
    setNotice("");
    setBusy(true);
    try {
      const path = editingCategory
        ? `/api/admin/categories/${editingCategory.CategoryId}`
        : "/api/admin/categories";
      await adminRequest(apiUrl, token, path, {
        method: editingCategory ? "PATCH" : "POST",
        body: JSON.stringify(form),
      });
      setForm(EMPTY_FORM);
      const wasEditing = Boolean(editingCategory);
      setEditingCategory(null);
      setNotice(wasEditing ? "Đã cập nhật danh mục." : "Đã thêm danh mục.");
      await loadCategories();
    } catch (error) {
      setError(error.message);
    } finally {
      setBusy(false);
    }
  }

  async function deleteCategory(category) {
    if (!window.confirm(`Xóa danh mục "${category.CategoryName}"?`)) {
      return;
    }
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await adminRequest(
        apiUrl,
        token,
        `/api/admin/categories/${category.CategoryId}`,
        { method: "DELETE" },
      );
      if (editingCategory?.CategoryId === category.CategoryId) {
        setEditingCategory(null);
        setForm(EMPTY_FORM);
      }
      setNotice("Đã xóa danh mục.");
      await loadCategories();
    } catch (error) {
      setError(error.message);
    } finally {
      setBusy(false);
    }
  }

  function startEditing(category) {
    setEditingCategory(category);
    setForm({
      category_name: category.CategoryName,
      description: category.Description || "",
    });
    setError("");
    setNotice("");
  }

  function cancelEditing() {
    setEditingCategory(null);
    setForm(EMPTY_FORM);
  }

  return (
    <section className="panel category-panel">
      <div className="section-heading">
        <div>
          <p className="eyebrow">CATEGORIES</p>
          <h2>Quản lý danh mục</h2>
        </div>
        <span className="muted-count">{categories.length} danh mục</span>
      </div>
      <form className="category-form" onSubmit={saveCategory}>
        <label>
          Tên danh mục *
          <input
            maxLength={100}
            onChange={(event) => setForm((current) => ({
              ...current,
              category_name: event.target.value,
            }))}
            required
            value={form.category_name}
          />
        </label>
        <label>
          Mô tả
          <textarea
            maxLength={1000}
            onChange={(event) => setForm((current) => ({
              ...current,
              description: event.target.value,
            }))}
            rows={2}
            value={form.description}
          />
        </label>
        <div className="category-form-actions">
          <button className="button" disabled={busy} type="submit">
            {editingCategory ? "Lưu thay đổi" : "Thêm danh mục"}
          </button>
          {editingCategory && (
            <button
              className="button button-outline"
              onClick={cancelEditing}
              type="button"
            >
              Hủy
            </button>
          )}
        </div>
      </form>
      <div className="place-table-wrap category-table-wrap">
        <table className="place-table category-table">
          <thead>
            <tr>
              <th>MÃ DANH MỤC</th>
              <th>TÊN DANH MỤC</th>
              <th>MÔ TẢ</th>
              <th>THAO TÁC</th>
            </tr>
          </thead>
          <tbody>
            {categories.map((category) => (
              <tr key={category.CategoryId}>
                <td>{category.CategoryId}</td>
                <td><strong>{category.CategoryName}</strong></td>
                <td className="category-description">
                  {category.Description || "—"}
                </td>
                <td>
                  <div className="place-row-actions">
                    <button
                      className="text-button"
                      disabled={busy}
                      onClick={() => startEditing(category)}
                      type="button"
                    >
                      Sửa
                    </button>
                    <button
                      className="text-button danger-text"
                      disabled={busy}
                      onClick={() => deleteCategory(category)}
                      type="button"
                    >
                      Xóa
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {categories.length === 0 && (
              <tr>
                <td className="category-empty" colSpan="4">
                  {busy
                    ? "Đang tải danh mục..."
                    : "Chưa có danh mục. Hãy thêm danh mục bằng biểu mẫu phía trên."}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
