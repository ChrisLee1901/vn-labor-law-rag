import type { NextConfig } from "next";
import { buildRewrites } from "./src/lib/api-rewrites";

const nextConfig: NextConfig = {
  async rewrites() {
    return buildRewrites(process.env);
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
