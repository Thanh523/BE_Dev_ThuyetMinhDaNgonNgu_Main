import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import App from "./App.jsx";

afterEach(() => {
  cleanup();
  window.history.pushState({}, "", "/user");
});

describe("portal routing", () => {
  it("opens the User portal without an Admin link", async () => {
    window.history.pushState({}, "", "/user");
    render(<App />);

    expect(
      await screen.findByRole("heading", {
        name: "Mỗi góc phố đều có một câu chuyện.",
      }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /admin/i })).not.toBeInTheDocument();
  });

  it("opens the Admin login without a User portal link", async () => {
    window.history.pushState({}, "", "/admin/login");
    render(<App />);

    expect(await screen.findByText("Đăng nhập quản trị")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /trang user/i })).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/địa chỉ backend/i)).not.toBeInTheDocument();
  });
});
