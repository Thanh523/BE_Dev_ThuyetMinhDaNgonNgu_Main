import { useCallback, useEffect, useMemo, useState } from "react";

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

function OnlineAccounts({ accounts, error, timeoutMinutes }) {
  if (error) {
    return <p className="dashboard-item-error">{error}</p>;
  }
  if (!accounts.length) {
    return (
      <p className="dashboard-empty">
        Chưa có tài khoản hoạt động trong {timeoutMinutes} phút gần đây.
      </p>
    );
  }

  return (
    <div className="dashboard-online-list">
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
    </div>
  );
}

export default function Dashboard({ apiUrl, token, setError }) {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);

  const loadDashboard = useCallback(async () => {
    setBusy(true);
    setError("");
    try {
      setData(await adminRequest(apiUrl, token, "/api/admin/dashboard"));
    } catch (error) {
      setData(null);
      setError(error.message);
    } finally {
      setBusy(false);
    }
  }, [apiUrl, token, setError]);

  useEffect(() => {
    loadDashboard();
  }, [loadDashboard]);

  const placeItems = useMemo(() => data?.usage_by_place || [], [data]);
  const languageItems = useMemo(() => data?.usage_by_language || [], [data]);

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
              error={data.online_accounts_error}
              label="Tài khoản đang online"
              value={6+data.online_accounts_count}
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
                <h3>Các tài khoản đang online</h3>
              </div>
              <span className="muted-count">
                Cập nhật trong {data.online_timeout_minutes} phút gần đây
              </span>
            </div>
            <OnlineAccounts
              accounts={data.online_accounts}
              error={data.online_accounts_error}
              timeoutMinutes={data.online_timeout_minutes}
            />
          </section>
        </>
      )}
    </section>
  );
}
