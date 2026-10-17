import type { NextConfig } from "next";

const api = process.env.NEXT_PUBLIC_API_URL ?? "https://ashiksharon005-verdict-api.hf.space";
const supabase = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
const origin = (u: string) => {
  try {
    return new URL(u).origin;
  } catch {
    return "";
  }
};
const connect = ["'self'", origin(api), origin(supabase), supabase ? `wss://${new URL(supabase).host}` : "", "https://challenges.cloudflare.com"]
  .filter(Boolean)
  .join(" ");

// Next.js injects small inline bootstrap scripts, so script-src needs 'unsafe-inline' unless a nonce
// pipeline is added. 'unsafe-eval' is only allowed in dev (React refresh).
const csp = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline' https://challenges.cloudflare.com${process.env.NODE_ENV === "production" ? "" : " 'unsafe-eval'"}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self'",
  `connect-src ${connect}`,
  "frame-src https://challenges.cloudflare.com",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
].join("; ");

const nextConfig: NextConfig = {
  poweredByHeader: false,
  reactStrictMode: true,
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "Content-Security-Policy", value: csp },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
          { key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains" },
        ],
      },
    ];
  },
};

export default nextConfig;
