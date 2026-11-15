import { useCallback, useEffect, useMemo, useRef, useState } from "react";

async function adminRequest(apiUrl, token, path) {
  const baseUrl = apiUrl.replace(/\/+$/, "");
  const requestUrls = [
    `${baseUrl}${path}`,
    `${baseUrl.replace(
      /^http:\/\/localhost(?=:|\/|$)/i,
      "http://127.0.0.1",
    )}${path}`,
  ].filter((url, index, urls) => urls.indexOf(url) === index);
  let lastNetworkError = null;

  for (const requestUrl of requestUrls) {
    let response;
    try {
      response = await fetch(
        requestUrl,
        { headers: { Authorization: `Bearer ${token}` } },
      );
    } catch (error) {
      lastNetworkError = error;
      continue;
    }

    const payload = await response.json().catch(() => null);
    if (!response.ok) {
      const detail = payload?.detail;
      throw new Error(
        `Dashboard trả về HTTP ${response.status}` +
        (typeof detail === "string" ? `: ${detail}` : ".") +
        ` URL: ${requestUrl}`,
      );
    }
    return payload;
  }

  const reason = lastNetworkError instanceof Error
    ? lastNetworkError.message
    : String(lastNetworkError);
  throw new Error(
    `Không thể kết nối Dashboard tới ${requestUrls.join(" hoặc ")}. ` +
    `Kiểm tra backend đang chạy và CORS. Chi tiết: ${reason}`,
  );
}

const numberFormatter = new Intl.NumberFormat("vi-VN");

function formatNumber(value) {
  return value == null ? "—" : numberFormatter.format(value);
}

function MetricCard({ label, value, error }) {
  return (
    <article className="dashboard-metric">
      <p className="dashboard-metric-label">{label}</p>
      {error ? (
        <p className="dashboard-item-error">{error}</p>
      ) : (
        <strong className="dashboard-metric-value">{formatNumber(value)}</strong>
      )}
    </article>
  );
}

function UsageList({ items, error, emptyMessage, labelKey }) {
  if (error) {
    return <p className="dashboard-item-error">{error}</p>;
  }
  if (!items.length) {
    return <p className="dashboard-empty">{emptyMessage}</p>;
  }

  const maximum = Math.max(...items.map((item) => item.count), 1);
  return (
    <div className="dashboard-usage-list">
      {items.map((item) => (
        <div className="dashboard-usage-row" key={item[labelKey]}>
          <div className="dashboard-usage-heading">
            <span>{labelKey === "place_id" ? item.place_name : item.language_name}</span>
            <strong>{formatNumber(item.count)}</strong>
          </div>
          <div className="dashboard-bar-track" aria-hidden="true">
            <span
              className="dashboard-bar"
              style={{ width: `${(item.count / maximum) * 100}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

function OnlineAccounts({
  accounts,
  error,
  guestCount,
  guestError,
}) {
  if (!error && !guestError && !accounts.length && !guestCount) {
    return (
      <p className="dashboard-empty">
        Hiện không có người dùng đang hoạt động.
      </p>
    );
  }

  return (
    <div className="dashboard-online-list">
      {error && <p className="dashboard-item-error">{error}</p>}
      {guestError && <p className="dashboard-item-error">{guestError}</p>}
      {accounts.map((account) => (
        <div className="dashboard-online-row" key={account.user_id}>
          <div className="dashboard-online-avatar" aria-hidden="true">
            {(account.full_name || "?").slice(0, 1).toUpperCase()}
          </div>
          <div className="dashboard-online-details">
            <strong>{account.full_name}</strong>
            <span>{account.email}</span>
          </div>
          <span className="dashboard-online-status">Đang hoạt động</span>
        </div>
      ))}
      {guestCount > 0 && (
        <div className="dashboard-online-row">
          <div className="dashboard-online-avatar" aria-hidden="true">K</div>
          <div className="dashboard-online-details">
            <strong>Khách chưa đăng nhập</strong>
            <span>{formatNumber(guestCount)} phiên truy cập đang hoạt động</span>
          </div>
          <span className="dashboard-online-status">Đang hoạt động</span>
        </div>
      )}
    </div>
  );
}

export default function Dashboard({ apiUrl, token, setError }) {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const [dateRange, setDateRange] = useState({ from: "", to: "" });
  const [appliedRange, setAppliedRange] = useState({ from: "", to: "" });
  const [rangeError, setRangeError] = useState("");
  const requestInFlight = useRef(false);

  const loadDashboard = useCallback(async () => {
    if (requestInFlight.current) {
      return;
    }
    requestInFlight.current = true;
    setBusy(true);
    setError("");
    try {
      const params = new URLSearchParams();
      if (appliedRange.from) {
        params.set("access_from", appliedRange.from);
      }
      if (appliedRange.to) {
        params.set("access_to", appliedRange.to);
      }
      const query = params.toString();
      setData(await adminRequest(
        apiUrl,
        token,
        `/api/admin/dashboard${query ? `?${query}` : ""}`,
      ));
    } catch (error) {
      setData(null);
      setError(error.message);
    } finally {
      requestInFlight.current = false;
      setBusy(false);
    }
  }, [apiUrl, token, setError, appliedRange]);

  useEffect(() => {
    loadDashboard();
  }, [loadDashboard]);

  useEffect(() => {
    const refreshIfVisible = () => {
      if (document.visibilityState === "visible") {
        loadDashboard();
      }
    };
    const interval = window.setInterval(refreshIfVisible, 5000);
    document.addEventListener("visibilitychange", refreshIfVisible);
    return () => {
      window.clearInterval(interval);
      document.removeEventListener("visibilitychange", refreshIfVisible);
    };
  }, [loadDashboard]);

  const placeItems = useMemo(() => data?.usage_by_place || [], [data]);
  const languageItems = useMemo(() => data?.usage_by_language || [], [data]);
  const applyDateRange = (event) => {
    event.preventDefault();
    if (dateRange.from && dateRange.to && dateRange.from > dateRange.to) {
      setRangeError("Ngày bắt đầu phải trước hoặc bằng ngày kết thúc.");
      return;
    }
    setRangeError("");
    setAppliedRange({ ...dateRange });
  };

  return (
    <section className="panel dashboard-panel">
      <div className="section-heading">
        <div>
          <p className="eyebrow">TỔNG QUAN</p>
          <h2>Thống kê hệ thống</h2>
        </div>
        <button
          className="button button-outline"
          disabled={busy}
          onClick={loadDashboard}
          type="button"
        >
          {busy ? "Đang tải..." : "Làm mới"}
        </button>
      </div>

      <form className="dashboard-access-filter" onSubmit={applyDateRange}>
        <label>
          Từ ngày
          <input
            type="date"
            value={dateRange.from}
            onChange={(event) => setDateRange((current) => ({
              ...current,
              from: event.target.value,
            }))}
          />
        </label>
        <label>
          Đến ngày
          <input
            type="date"
            value={dateRange.to}
            onChange={(event) => setDateRange((current) => ({
              ...current,
              to: event.target.value,
            }))}
          />
        </label>
        <button className="button button-outline" disabled={busy} type="submit">
          Lọc lượt truy cập
        </button>
        {rangeError && <p className="dashboard-item-error">{rangeError}</p>}
      </form>

      {!data && busy && <p className="dashboard-empty">Đang tải số liệu...</p>}
      {data && (
        <>
          <div className="dashboard-metrics">
            <MetricCard
              error={data.access_error}
              label="Lượt truy cập"
              value={data.access_count}
            />
            <MetricCard
              error={data.places_error}
              label="Số lượng địa điểm"
              value={data.places_count}
            />
            <MetricCard
              error={data.narrations_error}
              label="Nội dung thuyết minh"
              value={data.narrations_count}
            />
            <MetricCard
              error={data.online_visitors_error}
              label="Người dùng đang online"
              value={data.online_visitors_count}
            />
          </div>

          <div className="dashboard-grid">
            <section className="dashboard-card">
              <div className="dashboard-card-heading">
                <div>
                  <p className="eyebrow">MỨC ĐỘ QUAN TÂM</p>
                  <h3>Lượt sử dụng theo địa điểm</h3>
                </div>
                <span className="muted-count">{placeItems.length} địa điểm</span>
              </div>
              <UsageList
                emptyMessage="Chưa có địa điểm để thống kê."
                error={data.usage_by_place_error}
                items={placeItems}
                labelKey="place_id"
              />
            </section>

            <section className="dashboard-card">
              <div className="dashboard-card-heading">
                <div>
                  <p className="eyebrow">NGÔN NGỮ</p>
                  <h3>Lượt sử dụng theo ngôn ngữ</h3>
                </div>
                <span className="muted-count">{languageItems.length} ngôn ngữ</span>
              </div>
              <UsageList
                emptyMessage="Chưa có ngôn ngữ để thống kê."
                error={data.usage_by_language_error}
                items={languageItems}
                labelKey="language_code"
              />
            </section>
          </div>
          <section className="dashboard-card dashboard-online-card">
            <div className="dashboard-card-heading">
              <div>
                <p className="eyebrow">TRẠNG THÁI NGƯỜI DÙNG</p>
                <h3>Người dùng đang online</h3>
              </div>
              <span className="muted-count">
                Tự làm mới mỗi 5 giây · timeout dự phòng {data.online_timeout_minutes} phút
              </span>
            </div>
            <OnlineAccounts
              accounts={data.online_accounts}
              error={data.online_accounts_error}
              guestCount={data.online_guests_count}
              guestError={data.online_guests_error}
            />
          </section>
        </>
      )}
    </section>
  );
}
