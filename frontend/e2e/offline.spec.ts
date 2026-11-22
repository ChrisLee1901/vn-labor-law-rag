// Chạy trên preview thật: BASE_URL=https://... pnpm e2e. Cần backend + DB thật nên bị skip khi chạy cục bộ.
import { expect, test } from "@playwright/test";
import { ask, QUESTION, REMOTE, sourcesPanel } from "./helpers";

test.skip(!REMOTE, "Cần BASE_URL của bản preview (backend + DB thật); không chạy được cục bộ.");

test("hỏi lương tối thiểu vùng I: có badge trạng thái và nguồn 293/2025/NĐ-CP", async ({ page }) => {
  test.setTimeout(150_000);
  await ask(page, QUESTION);

  // Mô hình có thể bật hoặc tắt; chấp nhận cả hai.
  await expect(page.getByRole("banner").getByRole("status")).toHaveText(/Chế độ ngoại tuyến|Mô hình trực tuyến/, { timeout: 30_000 });

  const panel = await sourcesPanel(page, 120_000);
  await expect(panel.getByRole("listitem").filter({ hasText: "293/2025/NĐ-CP" }).first()).toBeVisible({ timeout: 120_000 });
});
