import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Dev cục bộ: chuyển /api/* sang FastAPI. Trên Vercel, vercel.json (Task 6.3) đảm nhiệm.
  async rewrites() {
    const origin = process.env.API_ORIGIN ?? "http://127.0.0.1:8000";
    return [{ source: "/api/:path*", destination: `${origin}/api/:path*` }];
  },
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
