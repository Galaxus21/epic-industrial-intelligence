/** @type {import('next').NextConfig} */

// The rewrite proxy aborts a backend request after this long without data (default 30 s in next 14.2.5,
// server/lib/router-utils/proxy-request.js) and leaves the browser waiting. Streams send heartbeats
// (backend/app/api/eventStream.py); a plain JSON model reply sends nothing until it is done, so the limit must sit
// above the longest one, modelReplyTimeoutMs (6 min) in src/lib/api.ts.
const proxyTimeoutMs = 7 * 60 * 1000;

const nextConfig = {
  output: "standalone",
  experimental: {
    proxyTimeout: proxyTimeoutMs,
  },
  async rewrites() {
    // next.config is evaluated at BUILD time inside Docker.
    // INTERNAL_API_URL from docker-compose environment is runtime-only, so
    // it won't be set during `next build`.  Use the Docker service name
    // "backend" as the default — it resolves correctly inside the Docker
    // network.  For local dev (no Docker) set INTERNAL_API_URL=http://localhost:8000.
    const backendUrl = process.env.INTERNAL_API_URL || "http://backend:8000";
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
