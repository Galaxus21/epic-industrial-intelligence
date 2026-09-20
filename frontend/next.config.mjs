/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
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
