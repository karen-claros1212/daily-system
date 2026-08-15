/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // En Next 16 los dev-tools (botón flotante + badge de issues) se montan por
  // defecto en bottom-left y quedan sobre la sidebar de la app (interceptando
  // clicks en E2E). Se reposicionan fuera del área de navegación.
  devIndicators: { position: 'top-right' },
  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          {
            key: 'Content-Security-Policy',
            value: [
              "default-src 'self'",
              "script-src 'self' 'unsafe-inline'",
              "style-src 'self' 'unsafe-inline'",
              "img-src 'self' data: blob:",
              "font-src 'self' data:",
              "connect-src 'self' ws://localhost:3000",
              "object-src 'none'",
              "base-uri 'self'",
              "frame-ancestors 'none'",
              "form-action 'self'",
            ].join('; '),
          },
          { key: 'X-Content-Type-Options', value: 'nosniff' },
          { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
          {
            key: 'Permissions-Policy',
            value: 'camera=(), microphone=(), geolocation=(), payment=(), usb=(), speech-synthesis=()',
          },
        ],
      },
    ];
  },
};

export default nextConfig;