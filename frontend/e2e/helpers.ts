import { expect, type Locator, type Page } from "@playwright/test";

/** true khi chạy trên preview thật (BASE_URL), false khi chạy với stub API cục bộ. */
export const REMOTE = Boolean(process.env.BASE_URL);
export const STUB_ORIGIN = `http://127.0.0.1:${process.env.E2E_STUB_PORT ?? 8787}`;

export const QUESTION = "Mức lương tối thiểu vùng I năm 2026?";

export async function ask(page: Page, question: string) {
  await page.goto("/");
  const input = page.getByRole("textbox", { name: "Câu hỏi" });
  await input.fill(question);
  await input.press("Enter");
}

/** Panel nguồn: cột bên phải ở desktop (>= 1024px), sheet mở bằng nút "Nguồn (n)" ở màn hình nhỏ. */
export async function sourcesPanel(page: Page, timeout = 15_000): Promise<Locator> {
  if ((page.viewportSize()?.width ?? 0) >= 1024) return page.getByRole("complementary", { name: "Nguồn trích dẫn" });
  await page.getByRole("button", { name: /^Nguồn \(\d+\)$/ }).click({ timeout });
  const sheet = page.getByRole("dialog", { name: /^Nguồn \(\d+\)$/ });
  await expect(sheet).toBeVisible();
  return sheet;
}

export async function noHorizontalScroll(page: Page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
}
