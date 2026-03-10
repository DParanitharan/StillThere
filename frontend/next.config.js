/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() { //This is to proxy API requests to the backend during development
    return [
      {
        source: '/api/:path*',
        destination: 'http://127.0.0.1:8000/api/:path*/', //django server
      },
      {
        source: '/api/sessions/:path*',
        destination: 'http://localhost:8000/api/sessions/:path*',
      },
    ];
  },
};

module.exports = nextConfig;