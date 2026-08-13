'use client';

import type { InversionistaSummary } from '@/lib/api/client';

interface DashboardProps {
  data: InversionistaSummary;
}

export function Dashboard({ data }: DashboardProps) {
  const p = data.portfolio || {};
  const moneda = data.moneda || 'COP';

  const fmt = (n: number) =>
    new Intl.NumberFormat('es-CO', { style: 'currency', currency: moneda }).format(n);

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Dashboard financiero</h1>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <div className="metric-card">
          <div className="metric-label">Rutas activas</div>
          <div className="metric-value success">{p.rutas_activas ?? 0}</div>
        </div>

        <div className="metric-card">
          <div className="metric-label">Cobradores activos</div>
          <div className="metric-value">{p.cobradores_activos ?? 0}</div>
        </div>

        <div className="metric-card">
          <div className="metric-label">Créditos activos</div>
          <div className="metric-value">{p.total_creditos_activos ?? 0}</div>
        </div>

        <div className="metric-card">
          <div className="metric-label">Cartera neta</div>
          <div className="metric-value money">{fmt(p.cartera_neta ?? 0)}</div>
        </div>

        <div className="metric-card">
          <div className="metric-label">Recaudo hoy</div>
          <div className="metric-value money">{fmt(p.recaudo_hoy ?? 0)}</div>
        </div>

        <div className="metric-card">
          <div className="metric-label">Jornadas cerradas hoy</div>
          <div className={`metric-value ${p.jornada_cerrada_hoy ? 'success' : 'warning'}`}>
            {p.jornada_cerrada_hoy ? 'Sí' : 'No'}
          </div>
        </div>
      </div>
    </div>
  );
}
