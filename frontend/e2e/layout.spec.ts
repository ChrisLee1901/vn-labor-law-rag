// Không tràn ngang ở cả hai viewport (project mobile là phép thử chính). Trang chi tiết lấy từ thẻ đầu của /van-ban.
import { expect, test } from "@playwright/test";
import { noHorizontalScroll } from "./helpers";

for (const path of ["/", "/van-ban", "/gioi-thieu"]) {
  test(`không tràn ngang: ${path}`, async ({ page }) => {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
    await noHorizontalScroll(page);
  });
}

test("không tràn ngang: trang chi tiết văn bản", async ({ page }) => {
  await page.goto("/van-ban");
  await page.getByRole("main").getByRole("listitem").first().getByRole("link").click();
  await expect(page.getByRole("heading", { level: 3 }).first()).toBeVisible();
  await noHorizontalScroll(page);
});
