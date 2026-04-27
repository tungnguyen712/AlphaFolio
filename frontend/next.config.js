/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  experimental: {
    serverActions: {
      allowedOrigins: [
        "localhost:3000",
        process.env.VERCEL_URL ?? "",
        "alphafolio.vercel.app",
      ],
    },
  },
  eslint: {
    dirs: ["app", "components", "hooks", "lib"],
  },
};

module.exports = nextConfig;
