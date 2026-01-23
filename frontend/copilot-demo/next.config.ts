import createNextIntlPlugin from 'next-intl/plugin';
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
};

export default withNextIntl(nextConfig);
