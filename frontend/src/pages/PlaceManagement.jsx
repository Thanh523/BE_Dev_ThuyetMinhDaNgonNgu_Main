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

const EMPTY_PLACE = {
  category_id: "",
  place_name: "",
  slug: "",
  address: "",
};

export default function PlaceManagement({ apiUrl, token, setError, setNotice }) {
  const [places, setPlaces] = useState([]);
  const [categories, setCategories] = useState([]);
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [visibility, setVisibility] = useState("all");
  const [skip, setSkip] = useState(0);
  const [total, setTotal] = useState(0);
  const [busy, setBusy] = useState(false);
  const [editingPlace, setEditingPlace] = useState(null);
  const [placeForm, setPlaceForm] = useState(EMPTY_PLACE);
  const [selectedPlace, setSelectedPlace] = useState(null);

  const loadCategories = useCallback(async () => {
    const result = await adminRequest(apiUrl, token, "/api/admin/categories");
    setCategories(result);
  }, [apiUrl, token]);

  const loadPlaces = useCallback(async (offset = 0) => {
    const params = new URLSearchParams({
      search,
      visibility,
      skip: String(offset),
      limit: "20",
    });
    if (categoryFilter) {
      params.set("category_id", categoryFilter);
    }
    const result = await adminRequest(
      apiUrl,
      token,
      `/api/admin/places?${params.toString()}`,
    );
    setPlaces(result.items);
    setTotal(result.total);
    setSkip(result.skip);
  }, [apiUrl, token, search, visibility, categoryFilter]);

  const refresh = useCallback(async (offset = 0) => {
    setBusy(true);
    setError("");
    try {
      await Promise.all([loadCategories(), loadPlaces(offset)]);
    } catch (error) {
      setError(error.message);
    } finally {
      setBusy(false);
    }
  }, [loadCategories, loadPlaces, setError]);

  useEffect(() => {
    refresh(0);
  // Load initial data once per authenticated backend session; filter changes are submitted explicitly.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiUrl, token]);

  function updatePlaceField(field, value) {
    setPlaceForm((current) => ({ ...current, [field]: value }));
  }

  function startCreate() {
    setEditingPlace(null);
    setPlaceForm({
      ...EMPTY_PLACE,
      category_id: categories[0] ? String(categories[0].CategoryId) : "",
    });
    setSelectedPlace(null);
    setError("");
    setNotice("");
  }

  function startEdit(place) {
    setEditingPlace(place);
    setPlaceForm({
      category_id: String(place.CategoryId),
      place_name: place.PlaceName,
      slug: place.Slug,
      address: place.Address,
    });
    setSelectedPlace(null);
    setError("");
    setNotice("");
  }

  async function savePlace(event) {
    event.preventDefault();
    setError("");
    setNotice("");
    if (!placeForm.category_id) {
      setError("Hãy tạo và chọn danh mục trước khi lưu địa điểm.");
      return;
    }
    setBusy(true);
    const body = {
      category_id: Number(placeForm.category_id),
      place_name: placeForm.place_name,
      slug: placeForm.slug || undefined,
      address: placeForm.address,
    };
    try {
      if (editingPlace) {
        await adminRequest(
          apiUrl,
          token,
          `/api/admin/places/${editingPlace.PlaceId}`,
          { method: "PATCH", body: JSON.stringify(body) },
        );
        setNotice("Đã cập nhật địa điểm.");
      } else {
        await adminRequest(apiUrl, token, "/api/admin/places", {
          method: "POST",
          body: JSON.stringify(body),
        });
        setNotice("Đã thêm địa điểm.");
      }
      setEditingPlace(null);
      setPlaceForm(EMPTY_PLACE);
      await loadPlaces(0);
    } catch (error) {
      setError(error.message);
    } finally {
      setBusy(false);
    }
  }

  async function toggleVisibility(place) {
    const shouldShow = place.IsVisible === false;
    const action = shouldShow ? "hiện" : "ẩn";
    if (!window.confirm(`Xác nhận ${action} địa điểm "${place.PlaceName}"?`)) {
      return;
    }
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await adminRequest(
        apiUrl,
        token,
        `/api/admin/places/${place.PlaceId}/visibility`,
        {
          method: "PATCH",
        body: JSON.stringify({ is_visible: shouldShow }),
        },
      );
      setNotice(shouldShow ? "Đã hiện địa điểm." : "Đã ẩn địa điểm.");
      await loadPlaces(skip);
    } catch (error) {
      setError(error.message);
    } finally {
      setBusy(false);
    }
  }

  async function viewPlace(place) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await adminRequest(
        apiUrl,
        token,
        `/api/admin/places/${place.PlaceId}`,
      );
      setSelectedPlace(result);
    } catch (error) {
      setError(error.message);
    } finally {
      setBusy(false);
    }
  }

  async function deletePlace(place) {
    if (!window.confirm(`Xóa địa điểm "${place.PlaceName}"?`)) {
      return;
    }
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await adminRequest(
        apiUrl,
        token,
        `/api/admin/places/${place.PlaceId}`,
        { method: "DELETE" },
      );
      setNotice("Đã xóa địa điểm.");
      if (selectedPlace?.PlaceId === place.PlaceId) {
        setSelectedPlace(null);
      }
      await loadPlaces(skip);
    } catch (error) {
      setError(error.message);
    } finally {
      setBusy(false);
    }
  }

  const categoryNameById = new Map(
    categories.map((category) => [
      category.CategoryId,
      category.CategoryName,
    ]),
  );
  const pageNumber = Math.floor(skip / 20) + 1;
  const pageCount = Math.max(1, Math.ceil(total / 20));

  return (
    <div className="places-manager">
      <section className="panel">
        <div className="section-heading">
          <div>
            <p className="eyebrow">PLACE MANAGEMENT</p>
            <h2>{editingPlace ? "Cập nhật địa điểm" : "Thêm địa điểm"}</h2>
          </div>
          {editingPlace && (
            <button
              className="button button-outline"
              onClick={startCreate}
              type="button"
            >
              Hủy chỉnh sửa
            </button>
          )}
        </div>
        <form className="place-form" onSubmit={savePlace}>
          <label>
            Tên địa điểm *
            <input
              maxLength={200}
              onChange={(event) => updatePlaceField("place_name", event.target.value)}
              required
              value={placeForm.place_name}
            />
          </label>
          <label>
            Danh mục *
            <select
              onChange={(event) => updatePlaceField("category_id", event.target.value)}
              required
              value={placeForm.category_id}
            >
              <option value="">Chọn danh mục</option>
              {categories.map((category) => (
                <option key={category.CategoryId} value={category.CategoryId}>
                  {category.CategoryName}
                </option>
              ))}
            </select>
          </label>
          <label>
            Slug (để trống để tự tạo)
            <input
              maxLength={200}
              onChange={(event) => updatePlaceField("slug", event.target.value)}
              placeholder="vi-du-dia-diem"
              value={placeForm.slug}
            />
          </label>
          <label className="place-address-field">
            Địa chỉ *
            <input
              maxLength={1000}
              onChange={(event) => updatePlaceField("address", event.target.value)}
              required
              value={placeForm.address}
            />
          </label>
          <div className="place-form-actions">
            <span className="hint">PlaceId sẽ được hệ thống tự tăng.</span>
            <button
              className="button"
              disabled={busy || categories.length === 0}
              type="submit"
            >
              {busy ? "Đang lưu..." : editingPlace ? "Lưu thay đổi" : "Thêm địa điểm"}
            </button>
          </div>
          {categories.length === 0 && (
            <p className="empty-note">
              Chưa có danh mục. Hãy tạo danh mục ở mục bên dưới trước.
            </p>
          )}
        </form>
      </section>

      <section className="panel">
        <div className="section-heading">
          <div>
            <p className="eyebrow">DIRECTORY</p>
            <h2>Danh sách địa điểm</h2>
          </div>
          <span className="muted-count">{total} địa điểm</span>
        </div>
        <form
          className="place-filters"
          onSubmit={(event) => {
            event.preventDefault();
            loadPlaces(0);
          }}
        >
          <label>
            Tìm kiếm
            <input
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Tên, slug hoặc địa chỉ"
              value={search}
            />
          </label>
          <label>
            Danh mục
            <select
              onChange={(event) => setCategoryFilter(event.target.value)}
              value={categoryFilter}
            >
              <option value="">Tất cả danh mục</option>
              {categories.map((category) => (
                <option key={category.CategoryId} value={category.CategoryId}>
                  {category.CategoryName}
                </option>
              ))}
            </select>
          </label>
          <label>
            Trạng thái
            <select
              onChange={(event) => setVisibility(event.target.value)}
              value={visibility}
            >
              <option value="all">Tất cả</option>
              <option value="visible">Đang hiện</option>
              <option value="hidden">Đang ẩn</option>
            </select>
          </label>
          <button className="button" disabled={busy} type="submit">
            {busy ? "Đang tải..." : "Tìm / lọc"}
          </button>
        </form>
        {places.length ? (
          <>
            <div className="place-table-wrap">
              <table className="place-table">
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Địa điểm</th>
                    <th>Danh mục</th>
                    <th>Địa chỉ</th>
                    <th>Trạng thái</th>
                    <th>Thao tác</th>
                  </tr>
                </thead>
                <tbody>
                  {places.map((place) => (
                    <tr key={place.PlaceId}>
                      <td>{place.PlaceId}</td>
                      <td>
                        <strong>{place.PlaceName}</strong>
                        <small className="place-slug">{place.Slug}</small>
                      </td>
                      <td>{categoryNameById.get(place.CategoryId) ?? place.CategoryId}</td>
                      <td className="place-address-cell">{place.Address}</td>
                      <td>
                        <span className={`visibility-tag ${place.IsVisible === false ? "hidden" : ""}`}>
                          {place.IsVisible === false ? "Đang ẩn" : "Đang hiện"}
                        </span>
                      </td>
                      <td>
                        <div className="place-row-actions">
                          <button
                            className="text-button"
                            disabled={busy}
                            onClick={() => viewPlace(place)}
                            type="button"
                          >
                            Chi tiết
                          </button>
                          <button
                            className="text-button"
                            onClick={() => startEdit(place)}
                            type="button"
                          >
                            Sửa
                          </button>
                          <button
                            className="text-button"
                            disabled={busy}
                            onClick={() => toggleVisibility(place)}
                            type="button"
                          >
                            {place.IsVisible === false ? "Hiện" : "Ẩn"}
                          </button>
                          <button
                            className="text-button danger-text"
                            disabled={busy}
                            onClick={() => deletePlace(place)}
                            type="button"
                          >
                            Xóa
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="pagination">
              <span>Trang {pageNumber} / {pageCount}</span>
              <div>
                <button
                  className="button button-small button-outline"
                  disabled={busy || skip === 0}
                  onClick={() => loadPlaces(Math.max(0, skip - 20))}
                  type="button"
                >
                  Trước
                </button>
                <button
                  className="button button-small button-outline"
                  disabled={busy || skip + 20 >= total}
                  onClick={() => loadPlaces(skip + 20)}
                  type="button"
                >
                  Sau
                </button>
              </div>
            </div>
          </>
        ) : (
          <div className="empty-state compact-empty">
            <strong>{busy ? "Đang tải địa điểm..." : "Không tìm thấy địa điểm"}</strong>
            <span>Thử đổi điều kiện tìm kiếm hoặc thêm địa điểm mới.</span>
          </div>
        )}
      </section>

      {selectedPlace && (
        <section className="panel place-detail">
          <div className="section-heading">
            <div>
              <p className="eyebrow">PLACE DETAIL · #{selectedPlace.PlaceId}</p>
              <h2>{selectedPlace.PlaceName}</h2>
            </div>
            <button
              className="button button-outline"
              onClick={() => setSelectedPlace(null)}
              type="button"
            >
              Đóng
            </button>
          </div>
          <dl className="detail-grid">
            <div><dt>Danh mục</dt><dd>{categoryNameById.get(selectedPlace.CategoryId) ?? selectedPlace.CategoryId}</dd></div>
            <div><dt>Slug</dt><dd>{selectedPlace.Slug}</dd></div>
            <div><dt>Địa chỉ</dt><dd>{selectedPlace.Address}</dd></div>
            <div><dt>Trạng thái</dt><dd>{selectedPlace.IsVisible === false ? "Đang ẩn" : "Đang hiện"}</dd></div>
          </dl>
        </section>
      )}

    </div>
  );
}
