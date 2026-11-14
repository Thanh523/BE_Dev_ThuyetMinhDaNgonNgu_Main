import { useCallback, useEffect, useState } from "react";

async function loadLogs(apiUrl, token) {
  const response = await fetch(
    `${apiUrl.replace(/\/+$/, "")}/api/admin/activity-logs?limit=100`,
    { headers: { Authorization: `Bearer ${token}` } },
  );
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

function formatDate(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : date.toLocaleString("vi-VN");
}

export default function ActivityLogManagement({ apiUrl, token, setError }) {
  const [logs, setLogs] = useState([]);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    setBusy(true);
    setError("");
    try {
      setLogs(await loadLogs(apiUrl, token));
    } catch (error) {
      setError(error.message);
    } finally {
      setBusy(false);
    }
  }, [apiUrl, token, setError]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return (
    <section className="panel activity-log-management">
      <div className="section-heading">
        <div>
          <p className="eyebrow">AUDIT</p>
          <h2>Nhật ký hoạt động admin</h2>
        </div>
        <button className="button button-outline" disabled={busy} onClick={refresh} type="button">
          {busy ? "Đang tải..." : "Làm mới"}
        </button>
      </div>
      {!logs.length && !busy && <p className="empty-note">Chưa có hoạt động nào được ghi nhận.</p>}
      <div className="activity-log-list">
        {logs.map((log) => (
          <article className="activity-log-row" key={log.log_id}>
            <div>
              <strong>{log.action} · {log.entity_name}</strong>
              <p>{log.description}</p>
            </div>
            <time dateTime={log.created_at}>{formatDate(log.created_at)}</time>
          </article>
        ))}
      </div>
    </section>
  );
}
