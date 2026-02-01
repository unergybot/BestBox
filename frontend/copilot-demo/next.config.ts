import createNextIntlPlugin from 'next-intl/plugin';
import path from "path";
import type { NextConfig } from "next";

const withNextIntl = createNextIntlPlugin();

const nextConfig: NextConfig = {
  /* config options here */
  allowedDevOrigins: [
    "http://192.168.1.107:3000",
    "http://localhost:3000",
    "192.168.1.107:3000",
    "192.168.1.107",
  ],

  turbopack: {
    root: path.resolve(__dirname, "../../"),
  },
  experimental: {
  },
  async rewrites() {
    return [
      {
        source: '/api/proxy/llm/:path*',
        destination: 'http://127.0.0.1:8001/:path*',  // vLLM on CUDA
      },
      {
        source: '/api/proxy/embeddings/:path*',
        destination: 'http://127.0.0.1:8081/:path*',
      },
      {
        source: '/api/proxy/reranker/:path*',
        destination: 'http://127.0.0.1:8082/:path*',
      },
      {
        source: '/api/proxy/s2s/:path*',
        destination: 'http://127.0.0.1:18765/:path*',  // S2S Gateway
      },
      {
        source: '/api/proxy/qdrant/:path*',
        destination: 'http://127.0.0.1:6333/:path*',
      },
    ];
  },
};

export default withNextIntl(nextConfig);
