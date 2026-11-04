import { useCallback, useEffect, useState } from "react";

async function request(apiUrl, token, path, options = {}) {
  const headers = new Headers(options.headers);
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  if (options.body && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${apiUrl.replace(/\/+$/, "")}${path}`, {
    ...options,
    headers,
  });
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

async function loadAllPlaces(apiUrl, token) {
  const places = [];
  let skip = 0;
  let total = 0;
  do {
    const params = new URLSearchParams({
      visibility: "all",
      skip: String(skip),
      limit: "100",
    });
    const page = await request(
      apiUrl,
      token,
      `/api/admin/places?${params.toString()}`,
    );
    places.push(...page.items);
    total = page.total;
    skip += page.items.length;
    if (page.items.length === 0) {
      break;
    }
  } while (skip < total);
  return places;
}

function compareImages(left, right) {
  return (
    (left.place_name ?? "").localeCompare(right.place_name ?? "") ||
    left.sort_order - right.sort_order
  );
}

function ImageCard({ image, apiUrl, token, onUpdated, onDeleted, reportError }) {
  const [caption, setCaption] = useState(image.caption ?? "");
  const [sortOrder, setSortOrder] = useState(String(image.sort_order ?? ""));
  const [busy, setBusy] = useState(false);

  async function saveChanges(event) {
    event.preventDefault();
    const order = Number(sortOrder);
    if (!Number.isInteger(order) || order < 1) {
      reportError("Thứ tự ảnh phải là số nguyên lớn hơn 0.");
      return;
    }

    setBusy(true);
    try {
      const updated = await request(
        apiUrl,
        token,
        `/api/admin/images/${encodeURIComponent(image.image_id)}`,
        {
          method: "PATCH",
          body: JSON.stringify({ caption, sort_order: order }),
        },
      );
      onUpdated(updated);
    } catch (error) {
      reportError(error.message);
    } finally {
      setBusy(false);
    }
  }

  async function deleteImage() {
    if (!window.confirm("Bạn có chắc muốn xóa ảnh này không?")) {
      return;
    }

    setBusy(true);
    try {
      await request(
        apiUrl,
        token,
        `/api/admin/images/${encodeURIComponent(image.image_id)}`,
        { method: "DELETE" },
      );
      onDeleted(image.image_id);
    } catch (error) {
      reportError(error.message);
    } finally {
      setBusy(false);
    }
  }

  const imageUrl = new URL(image.file_url, `${apiUrl.replace(/\/+$/, "")}/`).href;

  return (
    <article className="image-card">
      <div className="image-preview">
        <img src={imageUrl} alt={image.caption || `Ảnh thứ tự ${image.sort_order}`} />
        <span className="order-badge">#{image.sort_order}</span>
      </div>
      <form className="image-fields" onSubmit={saveChanges}>
        <p className="image-place-name">
          {image.place_name || "Địa điểm không tồn tại"}
        </p>
        <label>
          Caption
          <input
            maxLength={1000}
            onChange={(event) => setCaption(event.target.value)}
            placeholder="Nhập chú thích ảnh"
            value={caption}
          />
        </label>
        <label>
          Thứ tự
          <input
            min="1"
            onChange={(event) => setSortOrder(event.target.value)}
            required
            type="number"
            value={sortOrder}
          />
        </label>
        <div className="card-actions">
          <button className="button button-small" disabled={busy} type="submit">
            Lưu thay đổi
          </button>
          <button
            className="button button-small button-danger"
            disabled={busy}
            onClick={deleteImage}
            type="button"
          >
            Xóa
          </button>
        </div>
      </form>
    </article>
  );
}

export default function ImageManagement({
  apiUrl,
  token,
  setError,
  setNotice,
}) {
  const [placeId, setPlaceId] = useState("");
  const [places, setPlaces] = useState([]);
  const [images, setImages] = useState([]);
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);

  const loadDashboard = useCallback(async () => {
    if (!apiUrl.trim() || !token) {
      return;
    }
    setLoading(true);
    try {
      const [placeResults, imageResults] = await Promise.all([
        loadAllPlaces(apiUrl, token),
        request(apiUrl, token, "/api/admin/images"),
      ]);
      setPlaces(placeResults);
      setImages(imageResults);
      setPlaceId((current) =>
        placeResults.some((place) => String(place.PlaceId) === current)
          ? current
          : placeResults[0]
            ? String(placeResults[0].PlaceId)
            : "",
      );
    } catch (error) {
      setError(error.message);
    } finally {
      setLoading(false);
    }
  }, [apiUrl, token, setError]);

  useEffect(() => {
    loadDashboard();
  }, [loadDashboard]);

  function updateSelectedFiles(fileList) {
    const files = Array.from(fileList ?? []);
    setSelectedFiles(
      files.map((file) => ({ file, caption: "", sortOrder: "" })),
    );
    setError("");
    setNotice("");
  }

  function updateFileField(index, field, value) {
    setSelectedFiles((current) =>
      current.map((item, itemIndex) =>
        itemIndex === index ? { ...item, [field]: value } : item,
      ),
    );
  }

  async function uploadImages(event) {
    event.preventDefault();
    setError("");
    setNotice("");
    if (!apiUrl.trim()) {
      setError("Vui lòng nhập địa chỉ backend.");
      return;
    }
    if (!token) {
      setError("Vui lòng đăng nhập admin trước.");
      return;
    }
    if (!placeId) {
      setError("Vui lòng chọn địa điểm.");
      return;
    }
    if (selectedFiles.length === 0) {
      setError("Hãy chọn ít nhất một ảnh để tải lên.");
      return;
    }

    const hasSortOrders = selectedFiles.some((item) => item.sortOrder.trim());
    if (
      hasSortOrders &&
      selectedFiles.some((item) => !item.sortOrder.trim())
    ) {
      setError("Hãy nhập thứ tự cho tất cả ảnh, hoặc để trống tất cả để tự sắp xếp.");
      return;
    }

    const formData = new FormData();
    selectedFiles.forEach((item) => formData.append("files", item.file));
    if (selectedFiles.some((item) => item.caption.trim())) {
      selectedFiles.forEach((item) => formData.append("captions", item.caption));
    }
    if (hasSortOrders) {
      selectedFiles.forEach((item) => formData.append("sort_orders", item.sortOrder));
    }

    setUploading(true);
    try {
      const uploaded = await request(
        apiUrl,
        token,
        `/api/admin/places/${encodeURIComponent(placeId.trim())}/images`,
        { method: "POST", body: formData },
      );
      setImages((current) =>
        [
          ...current,
          ...uploaded.map((image) => ({
            ...image,
            place_name: places.find(
              (place) => String(place.PlaceId) === placeId,
            )?.PlaceName,
          })),
        ].sort(compareImages),
      );
      setSelectedFiles([]);
      setNotice(`Đã tải lên ${uploaded.length} ảnh.`);
    } catch (error) {
      setError(error.message);
    } finally {
      setUploading(false);
    }
  }

  function replaceImage(updated) {
    setImages((current) =>
      current
        .map((image) =>
          image.image_id === updated.image_id
            ? {
                ...image,
                ...updated,
                place_name: updated.place_name ?? image.place_name,
              }
            : image,
        )
        .sort(compareImages),
    );
    setError("");
    setNotice("Đã cập nhật ảnh.");
  }

  function removeImage(imageId) {
    setImages((current) =>
      current.filter((image) => image.image_id !== imageId),
    );
    setError("");
    setNotice("Đã xóa ảnh.");
  }

  return (
    <>
      <section className="panel upload-panel">
        <div className="section-heading">
          <div>
            <p className="eyebrow">THƯ VIỆN</p>
            <h2>Tải ảnh mới</h2>
          </div>
          <span className="muted-count">
            {selectedFiles.length ? `${selectedFiles.length} ảnh đã chọn` : "JPEG · PNG · WebP"}
          </span>
        </div>
        <form onSubmit={uploadImages}>
          <label className="upload-place-select">
            Địa điểm
            <select
              disabled={loading || places.length === 0}
              onChange={(event) => setPlaceId(event.target.value)}
              required
              value={placeId}
            >
              <option value="" disabled>Chọn địa điểm</option>
              {places.map((place) => (
                <option key={place.PlaceId} value={String(place.PlaceId)}>
                  {place.PlaceName}
                </option>
              ))}
            </select>
          </label>
          {places.length === 0 && !loading && (
            <p className="hint">
              Chưa có địa điểm. Hãy tạo địa điểm trước khi tải ảnh lên.
            </p>
          )}
          <label className="file-picker">
            <span className="upload-icon" aria-hidden="true">↑</span>
            <span>
              <strong>Chọn ảnh từ thiết bị</strong>
              <small>Tối đa 10 MB mỗi ảnh · Có thể chọn nhiều ảnh</small>
            </span>
            <input
              accept="image/jpeg,image/png,image/webp"
              multiple
              onChange={(event) => updateSelectedFiles(event.target.files)}
              type="file"
            />
          </label>
          {selectedFiles.length > 0 && (
            <div className="selected-list">
              {selectedFiles.map((item, index) => (
                <div className="selected-row" key={`${item.file.name}-${index}`}>
                  <span className="selected-name" title={item.file.name}>
                    {item.file.name}
                  </span>
                  <input
                    aria-label={`Caption cho ${item.file.name}`}
                    maxLength={1000}
                    onChange={(event) =>
                      updateFileField(index, "caption", event.target.value)
                    }
                    placeholder="Caption (không bắt buộc)"
                    value={item.caption}
                  />
                  <input
                    aria-label={`Thứ tự cho ${item.file.name}`}
                    min="1"
                    onChange={(event) =>
                      updateFileField(index, "sortOrder", event.target.value)
                    }
                    placeholder="Tự động"
                    type="number"
                    value={item.sortOrder}
                  />
                </div>
              ))}
            </div>
          )}
          <div className="upload-footer">
            <span className="hint">Để trống thứ tự để tự xếp ảnh vào cuối danh sách.</span>
            <button
              className="button"
              disabled={uploading || selectedFiles.length === 0 || !placeId}
              type="submit"
            >
              {uploading ? "Đang tải ảnh..." : "Tải ảnh lên"}
            </button>
          </div>
        </form>
      </section>
      <section className="gallery-section">
        <div className="section-heading gallery-heading">
          <div>
            <p className="eyebrow">PLACE IMAGES</p>
            <h2>Thư viện ảnh địa điểm</h2>
          </div>
          <span className="muted-count">
            {loading ? "Đang tải ảnh..." : `${images.length} ảnh`}
          </span>
        </div>
        {images.length > 0 ? (
          <div className="image-grid">
            {images.map((image) => (
              <ImageCard
                apiUrl={apiUrl}
                image={image}
                key={image.image_id}
                onDeleted={removeImage}
                onUpdated={replaceImage}
                reportError={setError}
                token={token}
              />
            ))}
          </div>
        ) : (
          <div className="empty-state">
            <div className="empty-icon" aria-hidden="true">▧</div>
            <strong>{loading ? "Đang tải thư viện ảnh..." : "Chưa có ảnh nào được tải"}</strong>
            {!loading && (
              <span>Ảnh của các địa điểm sẽ tự hiển thị tại đây sau khi tải lên.</span>
            )}
          </div>
        )}
      </section>
    </>
  );
}
