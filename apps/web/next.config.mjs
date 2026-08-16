/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // En Next 16 los dev-tools (botón flotante + badge de issues) se montan por
  // defecto en bottom-left y quedan sobre la sidebar de la app (interceptando
  // clicks en E2E). Se reposicionan fuera del área de navegación.
  devIndicators: { position: 'top-right' },
  async headers() {
    // React en modo desarrollo requiere unsafe-eval; el CSP estricto de
    // producción lo bloquea y dispara el overlay de errores de Next.js (un
    // segundo [role="dialog"]) que rompe los E2E. Solo se afloja en dev.
    const isDev = process.env.NODE_ENV !== 'production';
    const scriptSrc = ["script-src 'self' 'unsafe-inline'", ...(isDev ? ["'unsafe-eval'"] : [])].join(' ');
    return [
      {
        source: '/:path*',
        headers: [
          {
            key: 'Content-Security-Policy',
            value: [
              "default-src 'self'",
              scriptSrc,
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