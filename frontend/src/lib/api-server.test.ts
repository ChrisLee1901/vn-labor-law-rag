import { afterEach, describe, expect, it, vi } from "vitest";
import { DETAIL, DOCS } from "@/mocks/docs";
import { fetchDocDetail, fetchDocs, getApiBase } from "./api-server";

describe("getApiBase", () => {
  it("prefers API_ORIGIN, trimming trailing slashes", () => {
    expect(getApiBase({ API_ORIGIN: "https://api.test//", VERCEL_URL: "x.vercel.app", NODE_ENV: "development" })).toBe(
      "https://api.test",
    );
  });
  it("then NEXT_PUBLIC_SITE_URL, then VERCEL_URL", () => {
    expect(getApiBase({ NEXT_PUBLIC_SITE_URL: "https://site.test/", VERCEL_URL: "x.vercel.app" })).toBe("https://site.test");
    expect(getApiBase({ VERCEL_URL: "x.vercel.app", NODE_ENV: "production" })).toBe("https://x.vercel.app");
  });
  it("falls back to the local backend only in development", () => {
    expect(getApiBase({ NODE_ENV: "development" })).toBe("http://127.0.0.1:8000");
  });
  it("throws a clear error otherwise", () => {
    expect(() => getApiBase({ NODE_ENV: "production" })).toThrow(/API_ORIGIN/);
    expect(() => getApiBase({})).toThrow(/API_ORIGIN/);
  });
});

describe("fetchDocs / fetchDocDetail", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });
  const stub = (res: Partial<Response> & { json?: () => Promise<unknown> }) => {
    const f = vi.fn().mockResolvedValue({ ok: true, status: 200, ...res });
    vi.stubGlobal("fetch", f);
    vi.stubEnv("API_ORIGIN", "https://api.test");
    return f;
  };

  it("requests /api/docs with an hourly revalidate", async () => {
    const f = stub({ json: async () => DOCS });
    expect(await fetchDocs()).toEqual(DOCS);
    expect(f).toHaveBeenCalledWith("https://api.test/api/docs", { next: { revalidate: 3600 } });
  });
  it("rejects on non-2xx or non-array body", async () => {
    stub({ ok: false, status: 503 });
    await expect(fetchDocs()).rejects.toThrow();
    stub({ json: async () => ({ detail: "x" }) });
    await expect(fetchDocs()).rejects.toThrow();
  });
  it("returns null on 404 and throws on other errors for a detail", async () => {
    stub({ ok: false, status: 404 });
    expect(await fetchDocDetail("BLLD")).toBeNull();
    stub({ ok: false, status: 500 });
    await expect(fetchDocDetail("BLLD")).rejects.toThrow();
  });
  it("encodes the code and returns the body", async () => {
    const f = stub({ json: async () => DETAIL });
    expect(await fetchDocDetail("ND145-2020")).toEqual(DETAIL);
    expect(f).toHaveBeenCalledWith("https://api.test/api/docs/ND145-2020", { next: { revalidate: 3600 } });
  });
});
