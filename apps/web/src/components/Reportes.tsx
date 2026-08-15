'use client';

import { useState, useEffect, useCallback } from 'react';
import { fetchResumen, InversionistaSummary } from '@/lib/api/client';
import { MetricCard } from '@/components/ui/misc';
import { LoadingState, Flash } from '@/components/ui/button';

export function Reportes() {
  const [data, setData] = useState<InversionistaSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    try {
      setData(await fetchResumen());
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error al cargar reportes');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // Fetch async: todos los setState ocurren tras un await. La regla
    // react-hooks/set-state-in-effect no modela flujo async (falso positivo).
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  if (loading) return <LoadingState />;
  if (error) return <Flash tone="error">{error}</Flash>;
  if (!data) return null;

  const p = data.portfolio || {};
  const moneda = data.moneda || 'COP';
  const fmt = (n: number) =>
    new Intl.NumberFormat('es-CO', { style: 'currency', currency: moneda }).format(n);

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Reportes</h1>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard label="Total créditos activos" value={p.total_creditos_activos ?? 0} />
        <MetricCard label="Cartera neta" value={fmt(p.cartera_neta ?? 0)} />
        <MetricCard label="Recaudo hoy" value={fmt(p.recaudo_hoy ?? 0)} />
        <div className="metric-card">
          <div className="metric-label">Plan</div>
          <div className="metric-value" style={{ fontSize: '18px' }}>
            {(data.plan || 'basic').toUpperCase()}
          </div>
        </div>
      </div>
    </div>
  );
}