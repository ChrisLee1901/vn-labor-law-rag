import { describe, expect, it } from "vitest";
import { buildRewrites } from "@/lib/api-rewrites";

describe("buildRewrites", () => {
  it("dev: mặc định trỏ 127.0.0.1:8000", () => {
    expect(buildRewrites({ NODE_ENV: "development" })).toEqual([
      { source: "/api/:path*", destination: "http://127.0.0.1:8000/api/:path*" },
    ]);
  });
  it("API_ORIGIN ghi đè, bỏ dấu / cuối", () => {
    expect(buildRewrites({ NODE_ENV: "production", API_ORIGIN: "https://api.example.com/" })[0].destination).toBe(
      "https://api.example.com/api/:path*",
    );
  });
  it("production không có API_ORIGIN: không rewrite", () => {
    expect(buildRewrites({ NODE_ENV: "production" })).toEqual([]);
    expect(buildRewrites({})).toEqual([]);
  });
});
