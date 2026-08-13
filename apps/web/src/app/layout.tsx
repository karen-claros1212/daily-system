import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Daily System — Panel Administrativo',
  description: 'Panel administrativo productivo para gestión de rutas, caja y cartera',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="es">
      <body>{children}</body>
    </html>
  );
}
