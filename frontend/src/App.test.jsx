import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import App from "./App.jsx";
import "./AdminApp.jsx";
import "./UserApp.jsx";

afterEach(() => {
  cleanup();
  window.history.pushState({}, "", "/user");
});

describe("portal routing", () => {
  it("opens the User portal without an Admin link", async () => {
    window.history.pushState({}, "", "/user");
    const { container } = render(<App />);

    expect(
      await screen.findByRole("heading", {
        name: "Chọn ngôn ngữ để tiếp tục",
      }, { timeout: 5000 }),
    ).toBeInTheDocument();
    expect(container.querySelector(".user-portal-qr-code")).toBeInTheDocument();
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
