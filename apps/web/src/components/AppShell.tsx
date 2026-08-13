'use client';

import { useState, useEffect } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import type { SessionUser } from '@/lib/rbac';
import { hasCapability } from '@/lib/rbac';

interface AppShellProps {
  children: React.ReactNode;
  /** Identidad canónica (de /api/auth/me). Define la navegación por capabilities. */
  session?: SessionUser | null;
}

export function AppShell({ children, session = null }: AppShellProps) {
  const router = useRouter();
  const pathname = usePathname();
  const [currentPage, setCurrentPage] = useState('dashboard');
  const [sidebarOpen, setSidebarOpen] = useState(true);

  useEffect(() => {
    const path = pathname?.split('/').pop() || 'dashboard';
    setCurrentPage(path);
  }, [pathname]);

  const handleNav = (page: string) => {
    setCurrentPage(page);
    router.push(`/${page}`);
  };

  const handleLogout = async () => {
    try {
      await fetch('/api/auth/logout', { method: 'POST' });
    } finally {
      router.push('/');
    }
  };

  // Navegación construida a partir de capabilities reales del backend
  // (ver src/rbac.py). Default-deny: sin capability, el ítem no aparece.
  // El backend sigue siendo la autoridad: esto solo refleja la superficie.
  const navItems = [
    ...(hasCapability(session, 'jornada:ver') || hasCapability(session, 'jornadas:ver')
      ? [{ id: 'dashboard', label: 'Dashboard', icon: '📊' }]
      : []),
    ...(hasCapability(session, 'ruta:ver') || hasCapability(session, 'rutas:ver')
      ? [{ id: 'routes', label: 'Rutas', icon: '🗺️' }]
      : []),
    ...(hasCapability(session, 'jornada:ver')
      ? [{ id: 'caja', label: 'Caja', icon: '💵' }]
      : []),
    ...(hasCapability(session, 'inversionista:resumen')
      ? [{ id: 'reportes', label: 'Reportes', icon: '📈' }]
      : []),
  ];

  const rolLabel = session?.rol ?? '…';

  return (
    <div className="min-h-screen flex">
      {/* Sidebar */}
      <aside
        className={`bg-primary text-white flex flex-col transition-all duration-200 ${
          sidebarOpen ? 'w-60' : 'w-16'
        }`}
      >
        <div className="p-4 flex items-center gap-3">
          <div className="w-9 h-9 bg-tertiary text-primary rounded-md flex items-center justify-center font-bold text-lg flex-shrink-0">
            D
          </div>
          {sidebarOpen && <span className="font-bold text-lg">Daily System</span>}
        </div>

        <nav className="flex-1 px-2 mt-4">
          {navItems.map((item) => (
            <button
              key={item.id}
              onClick={() => handleNav(item.id)}
              className={`w-full flex items-center gap-3 px-3 py-2 rounded-md mb-1 transition-colors ${
                currentPage === item.id
                  ? 'bg-white/10 text-white'
                  : 'text-white/70 hover:bg-white/10 hover:text-white'
              }`}
              title={item.label}
              aria-label={item.label}
            >
              <span className="text-lg flex-shrink-0">{item.icon}</span>
              {sidebarOpen && <span>{item.label}</span>}
            </button>
          ))}
        </nav>

        <div className="p-4">
          <button
            onClick={handleLogout}
            className={`w-full flex items-center gap-3 px-3 py-2 rounded-md text-white/70 hover:bg-white/10 hover:text-white transition-colors ${
              sidebarOpen ? '' : 'justify-center'
            }`}
            aria-label="Cerrar sesión"
          >
            <span className="text-lg">🚪</span>
            {sidebarOpen && <span>Cerrar sesión</span>}
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 min-w-0">
        <div className="flex items-center justify-between p-4 border-b border-outline">
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="text-text-secondary hover:text-text-primary transition-colors p-2 rounded-md"
            aria-label={sidebarOpen ? 'Colapsar menú' : 'Expandir menú'}
          >
            ☰
          </button>
          <div className="text-sm text-text-secondary">
            {session?.usuario_nombre ?? 'Sesión'} · {rolLabel}
          </div>
        </div>
        <div className="p-4 lg:p-6">
          {children}
        </div>
      </main>
    </div>
  );
}