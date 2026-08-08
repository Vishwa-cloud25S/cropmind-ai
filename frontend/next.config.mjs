/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone", // small production container (frontend/Dockerfile)
};

export default nextConfig;
