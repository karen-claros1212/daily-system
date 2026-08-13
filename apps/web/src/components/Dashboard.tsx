'use client';

import type { InversionistaSummary } from '@/lib/api/client';
import { MetricCard } from '@/components/ui/misc';

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
        <MetricCard label="Rutas activas" value={p.rutas_activas ?? 0} tone="success" />
        <MetricCard label="Cobradores activos" value={p.cobradores_activos ?? 0} />
        <MetricCard label="Créditos activos" value={p.total_creditos_activos ?? 0} />
        <MetricCard label="Cartera neta" value={fmt(p.cartera_neta ?? 0)} money />
        <MetricCard label="Recaudo hoy" value={fmt(p.recaudo_hoy ?? 0)} money />
        <MetricCard
          label="Jornadas cerradas hoy"
          value={p.jornada_cerrada_hoy ? 'Sí' : 'No'}
          tone={p.jornada_cerrada_hoy ? 'success' : 'warning'}
        />
      </div>
    </div>
  );
}