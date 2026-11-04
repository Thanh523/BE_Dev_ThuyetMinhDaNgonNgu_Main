import { useCallback, useEffect, useState } from "react";

const PAGE_SIZE = 20;

async function adminRequest(apiUrl, token, path, options = {}) {
  const headers = new Headers(options.headers);
  headers.set("Authorization", `Bearer ${token}`);
  if (options.body) {
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

function formatDate(value) {
  if (!value) {
    return "—";
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : date.toLocaleString("vi-VN");
}

export default function UserManagement({
  apiUrl,
  token,
  setError,
  setNotice,
}) {
  const [users, setUsers] = useState([]);
  const [searchInput, setSearchInput] = useState("");
  const [statusInput, setStatusInput] = useState("all");
  const [filters, setFilters] = useState({ search: "", status: "all" });
  const [skip, setSkip] = useState(0);
  const [total, setTotal] = useState(0);
  const [busy, setBusy] = useState(false);

  // Tải một trang user theo bộ lọc đã áp dụng; API chỉ trả dữ liệu an toàn để hiển thị.
  const loadUsers = useCallback(async (offset, activeFilters) => {
    const params = new URLSearchParams({
      search: activeFilters.search,
      skip: String(offset),
      limit: String(PAGE_SIZE),
    });
    if (activeFilters.status !== "all") {
      params.set("is_active", String(activeFilters.status === "active"));
    }

    setBusy(true);
    setError("");
    try {
      const result = await adminRequest(
        apiUrl,
        token,
        `/api/admin/users?${params.toString()}`,
      );
      setUsers(result.items);
      setTotal(result.total);
      setSkip(result.skip);
    } catch (error) {
      setError(error.message);
    } finally {
      setBusy(false);
    }
  }, [apiUrl, token, setError]);

  // Tải lại khi đăng nhập, đổi backend, chuyển trang hoặc áp dụng bộ lọc.
  useEffect(() => {
    loadUsers(skip, filters);
  }, [loadUsers, skip, filters]);

  function applyFilters(event) {
    event.preventDefault();
    setFilters({ search: searchInput.trim(), status: statusInput });
    setSkip(0);
  }

  // Xác nhận trước khi khóa/mở tài khoản và tải lại trang hiện tại sau khi lưu.
  async function toggleUserStatus(user) {
    const nextIsActive = !user.IsActive;
    const action = nextIsActive ? "mở khóa" : "khóa";
    if (!window.confirm(`Xác nhận ${action} tài khoản "${user.FullName}"?`)) {
      return;
    }

    setBusy(true);
    setError("");
    setNotice("");
    try {
      await adminRequest(
        apiUrl,
        token,
        `/api/admin/users/${encodeURIComponent(user.UserId)}/status`,
        {
          method: "PATCH",
          body: JSON.stringify({ is_active: nextIsActive }),
        },
      );
      setNotice(nextIsActive ? "Đã mở khóa tài khoản." : "Đã khóa tài khoản.");
      await loadUsers(skip, filters);
    } catch (error) {
      setError(error.message);
    } finally {
      setBusy(false);
    }
  }

  const lastPageStart = Math.max(0, Math.ceil(total / PAGE_SIZE) - 1) * PAGE_SIZE;
  const pageNumber = total === 0 ? 0 : Math.floor(skip / PAGE_SIZE) + 1;
  const pageCount = Math.ceil(total / PAGE_SIZE);

  return (
    <section className="panel user-panel">
      <div className="section-heading">
        <div>
          <p className="eyebrow">USER ACCOUNTS</p>
          <h2>Quản lý người dùng</h2>
        </div>
        <span className="muted-count">{total} người dùng</span>
      </div>

      <form className="user-filters" onSubmit={applyFilters}>
        <label>
          Tìm theo tên hoặc email
          <input
            maxLength={200}
            onChange={(event) => setSearchInput(event.target.value)}
            placeholder="Nhập tên hoặc email"
            value={searchInput}
          />
        </label>
        <label>
          Trạng thái tài khoản
          <select
            onChange={(event) => setStatusInput(event.target.value)}
            value={statusInput}
          >
            <option value="all">Tất cả</option>
            <option value="active">Đang hoạt động</option>
            <option value="inactive">Đã khóa</option>
          </select>
        </label>
        <button className="button" disabled={busy} type="submit">
          Tìm kiếm
        </button>
      </form>

      <div className="place-table-wrap user-table-wrap">
        <table className="place-table user-table">
          <thead>
            <tr>
              <th>MÃ USER</th>
              <th>HỌ TÊN</th>
              <th>EMAIL</th>
              <th>TRẠNG THÁI</th>
              <th>NGÀY TẠO</th>
              <th>ĐĂNG NHẬP GẦN NHẤT</th>
              <th>THAO TÁC</th>
            </tr>
          </thead>
          <tbody>
            {users.map((user) => (
              <tr key={user.UserId}>
                <td>{user.UserId}</td>
                <td><strong>{user.FullName}</strong></td>
                <td>{user.Email}</td>
                <td>
                  <span className={`visibility-tag ${user.IsActive ? "" : "hidden"}`}>
                    {user.IsActive ? "Hoạt động" : "Đã khóa"}
                  </span>
                </td>
                <td>{formatDate(user.CreatedAt)}</td>
                <td>{formatDate(user.LastLoginAt)}</td>
                <td>
                  <button
                    className={`text-button ${user.IsActive ? "danger-text" : ""}`}
                    disabled={busy}
                    onClick={() => toggleUserStatus(user)}
                    type="button"
                  >
                    {user.IsActive ? "Khóa" : "Mở khóa"}
                  </button>
                </td>
              </tr>
            ))}
            {users.length === 0 && (
              <tr>
                <td className="user-empty" colSpan="7">
                  {busy
                    ? "Đang tải người dùng..."
                    : "Không tìm thấy người dùng phù hợp."}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="pagination">
        <span>
          Trang {pageNumber} / {pageCount}
        </span>
        <div>
          <button
            className="button button-outline"
            disabled={busy || skip === 0}
            onClick={() => setSkip(Math.max(0, skip - PAGE_SIZE))}
            type="button"
          >
            Trước
          </button>
          <button
            className="button button-outline"
            disabled={busy || skip >= lastPageStart}
            onClick={() => setSkip(Math.min(lastPageStart, skip + PAGE_SIZE))}
            type="button"
          >
            Sau
          </button>
        </div>
      </div>
    </section>
  );
}
