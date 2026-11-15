import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App.jsx";
import "./AdminApp.jsx";
import "./UserApp.jsx";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  delete navigator.sendBeacon;
  window.sessionStorage.clear();
  window.history.pushState({}, "", "/user");
});

describe("portal routing", () => {
  it("opens the User portal without an Admin link", async () => {
    const fetchMock = vi.fn(async (input) => {
      const { pathname } = new URL(String(input));
      const isVisitStart = pathname === "/api/user/website-visits";
      const payload = isVisitStart
        ? {
          VisitId: "9f1ea97b-24d4-45ee-a1c3-fc17d14ec8d4",
          StartedAt: new Date().toISOString(),
          LastSeenAt: new Date().toISOString(),
          EndedAt: null,
        }
        : pathname === "/api/user/categories"
          ? []
          : { items: [], total: 0 };
      return {
        ok: true,
        status: isVisitStart ? 201 : 200,
        json: async () => payload,
      };
    });
    vi.stubGlobal("fetch", fetchMock);
    const sendBeaconMock = vi.fn(() => true);
    Object.defineProperty(navigator, "sendBeacon", {
      configurable: true,
      value: sendBeaconMock,
    });
    window.sessionStorage.setItem(
      "saigon-echo-website-visit",
      "9f1ea97b-24d4-45ee-a1c3-fc17d14ec8d4",
    );
    window.history.pushState({}, "", "/user");
    const { container } = render(<App />);

    expect(
      await screen.findByRole("heading", {
        name: "Chọn ngôn ngữ để tiếp tục",
      }, { timeout: 5000 }),
    ).toBeInTheDocument();
    expect(container.querySelector(".user-portal-qr-code")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/user/website-visits"),
      expect.objectContaining({ method: "POST" }),
    );
    expect(screen.getByRole("link")).toHaveAttribute(
      "href",
      new URL("/user", window.location.href).toString(),
    );
    fireEvent.click(screen.getByRole("button", { name: /tiếng việt/i }));
    expect(
      await screen.findByRole("heading", {
        name: "Mỗi góc phố đều có một câu chuyện.",
      }, { timeout: 5000 }),
    ).toBeInTheDocument();
    fireEvent(window, new Event("pagehide"));
    expect(sendBeaconMock).toHaveBeenCalledWith(
      expect.stringContaining(
        "/api/user/website-visits/9f1ea97b-24d4-45ee-a1c3-fc17d14ec8d4/end",
      ),
      expect.any(Blob),
    );
    expect(screen.queryByRole("link", { name: /admin/i })).not.toBeInTheDocument();
  });

  it("opens the Admin login without a User portal link", async () => {
    window.history.pushState({}, "", "/admin/login");
    render(<App />);

    expect(await screen.findByText("Đăng nhập quản trị", {}, { timeout: 5000 })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /trang user/i })).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/địa chỉ backend/i)).not.toBeInTheDocument();
  });
});
