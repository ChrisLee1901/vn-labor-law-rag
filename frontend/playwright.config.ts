import { defineConfig } from "@playwright/test";

const APP_PORT = 3100;
const STUB_PORT = 8787;
const STUB_ORIGIN = `http://127.0.0.1:${STUB_PORT}`;
const baseURL = process.env.BASE_URL ?? `http://127.0.0.1:${APP_PORT}`;

// BASE_URL đặt = chạy trên preview thật (không dựng gì cục bộ). Không đặt = dựng stub API + app production cục bộ.
export default defineConfig({
  testDir: "./e2e",
  workers: 1, // stub-api giữ một cổng "release" dùng chung, nên các test chạy lần lượt
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"], ["html", { open: "never" }]],
  use: { baseURL, trace: "retain-on-failure" },
  projects: [
    { name: "desktop", use: { viewport: { width: 1280, height: 800 } } },
    { name: "mobile", use: { viewport: { width: 390, height: 844 } } },
  ],
  webServer: process.env.BASE_URL
    ? undefined
    : [
        {
          command: "node e2e/stub-api.mjs",
          url: `${STUB_ORIGIN}/api/health`,
          env: { E2E_STUB_PORT: String(STUB_PORT) },
          reuseExistingServer: !process.env.CI,
        },
        {
          // API_ORIGIN phải có cả lúc build: next.config rewrites được ghi vào routes-manifest khi build.
          command: `pnpm build && pnpm start -p ${APP_PORT}`,
          url: baseURL,
          timeout: 300_000,
          env: { API_ORIGIN: STUB_ORIGIN },
          reuseExistingServer: !process.env.CI,
        },
      ],
});
