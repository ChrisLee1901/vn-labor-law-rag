// Chat với SSE giả (docs/ai-sdk-protocol.md). Test 1 chặn /api/chat bằng page.route nên chạy được với mọi bản app.
// route.fulfill không stream từng đoạn được, nên test 2 ("hiện dần") dùng /api/chat của stub-api.mjs, chỉ chạy cục bộ.
import { expect, test } from "@playwright/test";
import { ask, QUESTION, REMOTE, sourcesPanel, STUB_ORIGIN } from "./helpers";

const chunks = [
  { type: "start", messageId: "mock-1" },
  { type: "data-status", data: { llm: "online", mode: "rag" } },
  { type: "source-url", sourceId: "S1", url: "/van-ban/ND293-2025#D3", title: "293/2025/NĐ-CP, Điều 3. Mức lương tối thiểu" },
  { type: "source-url", sourceId: "S2", url: "/van-ban/BLLD#D25", title: "45/2019/QH14, Điều 25. Thử việc" },
  { type: "text-start", id: "t1" },
  { type: "text-delta", id: "t1", delta: "Mức lương tối thiểu vùng I năm 2026 là " },
  { type: "text-delta", id: "t1", delta: "**5.310.000 đồng/tháng** [S1]. Thử việc tối đa 60 ngày [S2]." },
  { type: "text-end", id: "t1" },
  { type: "data-trace", data: { trace_id: "mock-trace" } },
  { type: "finish" },
];
const body = chunks.map((c) => `data: ${JSON.stringify(c)}\n\n`).join("") + "data: [DONE]\n\n";

test("trả lời mock: có câu trả lời, hover trích dẫn hiện thẻ nguồn, panel nguồn mở được", async ({ page }) => {
  let sent: unknown;
  await page.route("**/api/chat", (route) => {
    sent = route.request().postDataJSON();
    return route.fulfill({
      status: 200,
      headers: { "content-type": "text/event-stream", "cache-control": "no-cache", "x-vercel-ai-ui-message-stream": "v1" },
      body,
    });
  });
  await ask(page, QUESTION);

  await expect(page.getByText("5.310.000 đồng/tháng")).toBeVisible();
  expect(JSON.stringify(sent)).toContain(QUESTION);

  await page.getByRole("button", { name: /^Nguồn S1:/ }).hover();
  const card = page.locator('[data-slot="hover-card-content"]');
  await expect(card).toContainText("293/2025/NĐ-CP, Điều 3. Mức lương tối thiểu");
  await expect(card.getByRole("link", { name: "Xem điều luật" })).toHaveAttribute("href", "/van-ban/ND293-2025#D3");

  await page.mouse.move(0, 0); // đóng thẻ hover, nếu không thẻ che nút "Nguồn (n)" ở mobile
  await expect(card).toBeHidden();

  const panel = await sourcesPanel(page);
  await expect(panel.getByRole("listitem")).toHaveCount(2);
  await expect(panel).toContainText("45/2019/QH14, Điều 25. Thử việc");
});

test("câu trả lời hiện dần theo từng đoạn stream", async ({ page, request }) => {
  test.skip(REMOTE, "Dùng /api/chat của stub cục bộ; không áp dụng cho bản preview.");
  await ask(page, QUESTION);

  await expect(page.getByText("Mức lương tối thiểu vùng I năm 2026 là")).toBeVisible();
  await expect(page.getByText("Đang trả lời…")).toBeVisible();
  await expect(page.getByText("5.310.000 đồng/tháng")).toHaveCount(0);

  await request.post(`${STUB_ORIGIN}/__release`);
  await expect(page.getByText("5.310.000 đồng/tháng")).toBeVisible();
  await expect(page.getByText("Đang trả lời…")).toHaveCount(0);
});
