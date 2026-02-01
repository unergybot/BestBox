import createNextIntlPlugin from 'next-intl/plugin';
import path from "path";
import type { NextConfig } from "next";

const withNextIntl = createNextIntlPlugin();

// Backend service ports - can be overridden via environment variables
const LLM_PORT = process.env.NEXT_PUBLIC_LLM_PORT || '8080';
const EMBEDDINGS_PORT = process.env.NEXT_PUBLIC_EMBEDDINGS_PORT || '8081';
const RERANKER_PORT = process.env.NEXT_PUBLIC_RERANKER_PORT || '8082';
const S2S_PORT = process.env.NEXT_PUBLIC_S2S_PORT || '8765';
const QDRANT_PORT = process.env.NEXT_PUBLIC_QDRANT_PORT || '6333';

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
        destination: `http://127.0.0.1:${LLM_PORT}/:path*`,
      },
      {
        source: '/api/proxy/embeddings/:path*',
        destination: `http://127.0.0.1:${EMBEDDINGS_PORT}/:path*`,
      },
      {
        source: '/api/proxy/reranker/:path*',
        destination: `http://127.0.0.1:${RERANKER_PORT}/:path*`,
      },
      {
        source: '/api/proxy/s2s/:path*',
        destination: `http://127.0.0.1:${S2S_PORT}/:path*`,
      },
      {
        source: '/api/proxy/qdrant/:path*',
        destination: `http://127.0.0.1:${QDRANT_PORT}/:path*`,
      },
    ];
  },
};

export default withNextIntl(nextConfig);
