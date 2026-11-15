import { expect, test } from "@playwright/test";

test("User portal has no Admin navigation", async ({ page }) => {
  await page.goto("/user");

  await expect(
    page.getByRole("heading", { name: "Mỗi góc phố đều có một câu chuyện." }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: /admin/i })).toHaveCount(0);
});

test("Admin login has no User navigation or backend URL field", async ({ page }) => {
  await page.goto("/admin/login");

  await expect(page.getByRole("heading", { name: "Đăng nhập quản trị" })).toBeVisible();
  await expect(page.getByRole("link", { name: /trang user/i })).toHaveCount(0);
  await expect(page.getByLabel("Địa chỉ backend")).toHaveCount(0);
});
