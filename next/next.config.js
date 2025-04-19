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
        destination: 'http://pythonserver:5000/:path*',
      },
      {
        source: '/api/:path*',
        destination: 'http://nestjs:3001/:path*',
      }
    ]
  }
}

export default nextConfig;
