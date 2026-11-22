/**
 * Rewrite `/api/*` sang FastAPI. Chỉ bật khi đặt API_ORIGIN hoặc đang `next dev` (mặc định 127.0.0.1:8000).
 * Production không có API_ORIGIN: không rewrite, vercel.json (Task 6.3) định tuyến.
 */
export function buildRewrites(env: { API_ORIGIN?: string; NODE_ENV?: string }) {
  const origin = env.API_ORIGIN || (env.NODE_ENV === "development" ? "http://127.0.0.1:8000" : undefined);
  return origin ? [{ source: "/api/:path*", destination: `${origin.replace(/\/+$/, "")}/api/:path*` }] : [];
}
