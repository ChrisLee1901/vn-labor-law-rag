import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { articleFor, effectiveness, excerpt, getDocDetail, getDocs, parseSourceUrl, resetDocsCache } from "./docs-cache";

const NOW = new Date(2026, 10, 22);

describe("effectiveness", () => {
  it("labels the three states", () => {
    expect(effectiveness({ effective_from: "2026-01-01", effective_to: null }, NOW).label).toBe("Đang hiệu lực");
    expect(effectiveness({ effective_from: "2027-01-01", effective_to: null }, NOW).label).toBe(
      "Chưa hiệu lực (từ 01/01/2027)",
    );
    expect(effectiveness({ effective_from: "2020-01-01", effective_to: "2026-01-01" }, NOW)).toMatchObject({
      label: "Hết hiệu lực",
      tone: "expired",
    });
  });
  it("computes today in Vietnam time (UTC+7), not the host timezone", () => {
    const doc = { effective_from: "2026-02-14", effective_to: null };
    // 18:00Z ngày 13/02 = 01:00 ngày 14/02 giờ VN: đã có hiệu lực.
    expect(effectiveness(doc, new Date("2026-02-13T18:00:00Z")).tone).toBe("active");
    // 16:59Z = 23:59 ngày 13/02 giờ VN: chưa.
    expect(effectiveness(doc, new Date("2026-02-13T16:59:00Z")).tone).toBe("future");
  });
  it("treats effective_to as exclusive", () => {
    expect(effectiveness({ effective_from: "2020-01-01", effective_to: "2026-11-22" }, NOW).tone).toBe("expired");
    expect(effectiveness({ effective_from: "2020-01-01", effective_to: "2026-11-23" }, NOW).tone).toBe("active");
  });
});

describe("parseSourceUrl / articleFor / excerpt", () => {
  it("parses article and appendix anchors", () => {
    expect(parseSourceUrl("/van-ban/ND293-2025#D3")).toEqual({ code: "ND293-2025", kind: "D", n: 3 });
    expect(parseSourceUrl("/van-ban/BLLD#PL2")).toEqual({ code: "BLLD", kind: "PL", n: 2 });
    expect(parseSourceUrl("https://x.test/a")).toBeNull();
  });
  it("matches by kind and number", () => {
    const articles = [
      { id: "a", number: 2, suffix: null, title: null, chapter: null, content: "dieu", kind: "dieu" as const },
      { id: "b", number: 2, suffix: null, title: null, chapter: null, content: "pl", kind: "phu_luc" as const },
    ];
    expect(articleFor(articles, { code: "x", kind: "PL", n: 2 })?.content).toBe("pl");
    expect(articleFor(articles, { code: "x", kind: "D", n: 9 })).toBeUndefined();
  });
  it("truncates to ~300 chars", () => {
    expect(excerpt("a".repeat(500))).toHaveLength(301);
    expect(excerpt("ngắn  \n gọn")).toBe("ngắn gọn");
  });
});

describe("cache", () => {
  beforeEach(resetDocsCache);
  afterEach(() => vi.unstubAllGlobals());

  it("de-duplicates in-flight requests and caches the result", async () => {
    const f = vi.fn(async () => Response.json([]));
    vi.stubGlobal("fetch", f);
    await Promise.all([getDocs(), getDocs()]);
    await getDocs();
    expect(f).toHaveBeenCalledTimes(1);
  });

  it("drops a failed request so it can be retried", async () => {
    const f = vi.fn().mockResolvedValueOnce(new Response("", { status: 500 })).mockResolvedValue(Response.json({ doc: {}, articles: [] }));
    vi.stubGlobal("fetch", f);
    await expect(getDocDetail("BLLD")).rejects.toThrow();
    await expect(getDocDetail("BLLD")).resolves.toBeTruthy();
    expect(f).toHaveBeenCalledTimes(2);
  });
});
