/** @type {import('next').NextConfig} */
// BACKEND_URL is a server-side env var (not NEXT_PUBLIC_*), read at Next.js startup time.
// Local dev: unset → defaults to http://127.0.0.1:8000
// Docker:    set to http://backend:8000 via docker-compose environment
const backendUrl = process.env.BACKEND_URL || "http://127.0.0.1:8000";

const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/:path*/`,
      },
    ];
  },
};

module.exports = nextConfig;
