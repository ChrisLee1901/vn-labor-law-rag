// /van-ban render ở server (server component gọi fetchDocs), page.route không chặn được. Cục bộ: app chạy với
// API_ORIGIN trỏ vào e2e/stub-api.mjs (do playwright.config.ts dựng); với BASE_URL: dùng dữ liệu của preview.
// Spec không phụ thuộc mã văn bản cụ thể: mở thẻ đầu tiên trong danh sách.
import { expect, test } from "@playwright/test";

test("danh sách văn bản rồi chi tiết văn bản", async ({ page }) => {
  await page.goto("/van-ban");
  await expect(page.getByRole("heading", { level: 1, name: "Văn bản pháp luật" })).toBeVisible();

  const first = page.getByRole("main").getByRole("listitem").first().getByRole("link");
  const title = (await first.textContent())?.trim() ?? "";
  expect(title).not.toBe("");
  await first.click();

  await expect(page).toHaveURL(/\/van-ban\/[A-Za-z0-9-]+$/);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(title);
  await expect(page.getByRole("link", { name: "Tất cả văn bản" })).toBeVisible();
  await expect(page.getByRole("heading", { level: 3 }).first()).toContainText(/^(Điều|Phụ lục) /);
});
