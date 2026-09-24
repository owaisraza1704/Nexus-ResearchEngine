import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  typedRoutes: true,
  output: 'standalone',
  agentRules: false,
  async rewrites() {
    return [
      {
        source: '/api/backend/:path*',
        destination: `${process.env.NEXUS_API_URL || 'http://127.0.0.1:8000'}/:path*`,
      },
    ];
  },
};

export default nextConfig;
