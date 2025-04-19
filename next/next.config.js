/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  typescript: {
    // این گزینه خطاهای TypeScript را در زمان build نادیده می‌گیرد
    ignoreBuildErrors: true,
  },
  async rewrites() {
    return [
      {
        source: '/python-api/:path*',
        destination: 'https://a.networklearnzero.shop/python-api/:path*',
      },
      {
        source: '/api/:path*',
        destination: 'https://a.networklearnzero.shop/api/:path*',
      }
    ]
  }
}

export default nextConfig;
