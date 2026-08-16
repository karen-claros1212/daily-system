'use client';

import { useState } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import type { SessionUser } from '@/lib/rbac';
import { hasCapability } from '@/lib/rbac';
import { SessionRenewer } from '@/lib/auth/useSessionRenewer';
import {
  IconDashboard,
  IconRoute,
  IconCaja,
  IconReportes,
  IconSuscripcion,
  IconDispositivo,
  IconLogout,
  IconMenu,
  IconShield,
  IconUsers,
  IconShieldCheck,
  IconContactos,
  IconCredito,
} from '@/components/ui/icons';
import { IconButton } from '@/components/ui/button';

interface AppShellProps {
  children: React.ReactNode;
  /** Identidad canónica (de /api/auth/me). Define la navegación por capabilities. */
  session?: SessionUser | null;
}

interface NavItem {
  id: string;
  label: string;
  icon: React.ReactNode;
}

const ICONS: Record<string, React.ReactNode> = {
  dashboard: <IconDashboard size={18} aria-hidden="true" />,
  routes: <IconRoute size={18} aria-hidden="true" />,
  caja: <IconCaja size={18} aria-hidden="true" />,
  reportes: <IconReportes size={18} aria-hidden="true" />,
  suscripcion: <IconSuscripcion size={18} aria-hidden="true" />,
  dispositivos: <IconDispositivo size={18} aria-hidden="true" />,
  usuarios: <IconUsers size={18} aria-hidden="true" />,
  auditoria: <IconShieldCheck size={18} aria-hidden="true" />,
  clientes: <IconContactos size={18} aria-hidden="true" />,
  creditos: <IconCredito size={18} aria-hidden="true" />,
};

// Títulos humanos por ruta para breadcrumbs (label se mantiene por capabilities).
const TITLES: Record<string, string> = {
  dashboard: 'Dashboard',
  routes: 'Rutas',
  caja: 'Caja',
  reportes: 'Reportes',
  suscripcion: 'Suscripción',
  dispositivos: 'Dispositivos',
  usuarios: 'Usuarios',
  auditoria: 'Auditoría',
  clientes: 'Clientes',
  creditos: 'Créditos',
};

export function AppShell({ children, session = null }: AppShellProps) {
  const router = useRouter();
  const pathname = usePathname();
  const [sidebarOpen, setSidebarOpen] = useState(true);

  const currentPage = pathname?.split('/').filter(Boolean)[0] || 'dashboard';

  const handleNav = (page: string) => {
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
  // El backend conserva la autoridad: esto solo refleja la superficie.
  const navItems: NavItem[] = [
    ...(hasCapability(session, 'jornada:ver') || hasCapability(session, 'jornadas:ver')
      ? [{ id: 'dashboard', label: 'Dashboard', icon: ICONS.dashboard }]
      : []),
    ...(hasCapability(session, 'ruta:ver') || hasCapability(session, 'rutas:ver')
      ? [{ id: 'routes', label: 'Rutas', icon: ICONS.routes }]
      : []),
    ...(hasCapability(session, 'jornada:ver')
      ? [{ id: 'caja', label: 'Caja', icon: ICONS.caja }]
      : []),
    ...(hasCapability(session, 'inversionista:resumen')
      ? [{ id: 'reportes', label: 'Reportes', icon: ICONS.reportes }]
      : []),
    ...(hasCapability(session, 'inversionista:suscripcion')
      ? [{ id: 'suscripcion', label: 'Suscripción', icon: ICONS.suscripcion }]
      : []),
    ...(hasCapability(session, 'dispositivos:registrar')
      ? [{ id: 'dispositivos', label: 'Dispositivos', icon: ICONS.dispositivos }]
      : []),
    ...(hasCapability(session, 'usuarios:gestionar')
      ? [{ id: 'usuarios', label: 'Usuarios', icon: ICONS.usuarios }]
      : []),
    ...(hasCapability(session, 'clientes:ver')
      ? [{ id: 'clientes', label: 'Clientes', icon: ICONS.clientes }]
      : []),
    ...(hasCapability(session, 'creditos:ver')
      ? [{ id: 'creditos', label: 'Créditos', icon: ICONS.creditos }]
      : []),
    ...(hasCapability(session, 'audit:ver')
      ? [{ id: 'auditoria', label: 'Auditoría', icon: ICONS.auditoria }]
      : []),
  ];

  const rolLabel = session?.rol ?? '…';
  const sectionTitle = TITLES[currentPage] ?? 'Daily System';

  return (
    <div className="min-h-screen flex bg-bg">
      {/* Renovación proactiva de sesión: logout + redirect al login si la cookie
          caduca o el dispositivo se revoca/bump en el backend (Commit 5). */}
      <SessionRenewer session={session} />
      {/* Sidebar */}
      <aside
        className={`bg-primary text-white flex flex-col transition-all duration-200 ${
          sidebarOpen ? 'w-60' : 'w-16'
        }`}
        aria-label="Menú principal"
      >
        <div className="p-4 flex items-center gap-3">
          <div className="w-9 h-9 bg-tertiary text-primary rounded-md flex items-center justify-center flex-shrink-0">
            <IconShield size={18} aria-hidden="true" />
          </div>
          {sidebarOpen && <span className="font-bold text-lg">Daily System</span>}
        </div>

        <nav className="flex-1 px-2 mt-4">
          {navItems.map((item) => (
            <button
              key={item.id}
              onClick={() => handleNav(item.id)}
              className={`nav-link mb-1 ${sidebarOpen ? '' : 'justify-center'}`}
              title={item.label}
              aria-label={item.label}
              aria-current={currentPage === item.id ? 'page' : undefined}
            >
              {item.icon}
              {sidebarOpen && <span>{item.label}</span>}
            </button>
          ))}
        </nav>

        <div className="p-4">
          <button
            onClick={handleLogout}
            className={`nav-link ${sidebarOpen ? '' : 'justify-center'}`}
            aria-label="Cerrar sesión"
          >
            <IconLogout size={18} aria-hidden="true" />
            {sidebarOpen && <span>Cerrar sesión</span>}
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 min-w-0 flex flex-col">
        <header className="flex items-center justify-between gap-3 px-4 py-3 border-b border-outline bg-surface">
          <div className="flex items-center gap-2 min-w-0">
            <IconButton
              icon={<IconMenu size={18} aria-hidden="true" />}
              label={sidebarOpen ? 'Colapsar menú' : 'Expandir menú'}
              onClick={() => setSidebarOpen((v) => !v)}
            />
            {/* Breadcrumb */}
            <nav aria-label="Breadcrumb" className="flex items-center gap-1.5 text-sm">
              <span className="text-textSecondary">Daily System</span>
              {currentPage !== 'dashboard' && (
                <>
                  <span aria-hidden="true" className="text-textSecondary">/</span>
                  <span className="font-medium text-textPrimary">{sectionTitle}</span>
                </>
              )}
            </nav>
          </div>
          <div className="text-sm text-textSecondary truncate">
            {session?.usuario_nombre ?? 'Sesión'} · {rolLabel}
          </div>
        </header>
        <div className="p-4 lg:p-6 flex-1">{children}</div>
      </main>
    </div>
  );
}