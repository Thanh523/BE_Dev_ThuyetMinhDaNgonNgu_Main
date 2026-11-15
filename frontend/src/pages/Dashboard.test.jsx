import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import Dashboard from "./Dashboard.jsx";

const dashboard = {
  access_count: 7,
  access_error: null,
  places_count: 2,
  places_error: null,
  narrations_count: 3,
  narrations_error: null,
  online_accounts_count: 1,
  online_accounts: [
    {
      user_id: "user-1",
      full_name: "Nguyen Van A",
      email: "a@example.com",
      last_seen_at: null,
    },
  ],
  online_accounts_error: null,
  online_guests_count: 2,
  online_guests_error: null,
  online_visitors_count: 3,
  online_visitors_error: null,
  online_timeout_minutes: 5,
  usage_by_place: [],
  usage_by_place_error: null,
  usage_by_language: [],
  usage_by_language_error: null,
};

describe("Dashboard", () => {
  it("filters website visits by date and includes online guests", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => dashboard,
    });
    vi.stubGlobal("fetch", fetchMock);
    const setError = vi.fn();

    render(
      <Dashboard
        apiUrl="http://127.0.0.1:8000"
        token="admin-token"
        setError={setError}
      />,
    );

    expect(await screen.findByText("Khách chưa đăng nhập")).toBeInTheDocument();
    expect(
      screen.getByText("Người dùng đang online", {
        selector: ".dashboard-metric-label",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Người dùng đang online", {
        selector: ".dashboard-metric-label",
      }).parentElement.querySelector(".dashboard-metric-value"),
    ).toHaveTextContent("3");

    fireEvent.change(screen.getByLabelText("Từ ngày"), {
      target: { value: "2026-11-01" },
    });
    fireEvent.change(screen.getByLabelText("Đến ngày"), {
      target: { value: "2026-11-15" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Lọc lượt truy cập" }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenLastCalledWith(
        "http://127.0.0.1:8000/api/admin/dashboard?access_from=2026-11-01&access_to=2026-11-15",
        expect.objectContaining({
          headers: { Authorization: "Bearer admin-token" },
        }),
      );
    });
    expect(setError).toHaveBeenLastCalledWith("");
  });
});
