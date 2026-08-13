'use client';

import { useState, useEffect } from 'react';
import { fetchResumen, InversionistaSummary } from '@/lib/api/client';

export function Reportes() {
  const [data, setData] = useState<InversionistaSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    load();
  }, []);

  async function load() {
    try {
      setLoading(true);
      setData(await fetchResumen());
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error al cargar reportes');
    } finally {
      setLoading(false);
    }
  }

  if (loading) return <div className="text-text-secondary">Cargando...</div>;
  if (error) return <div className="flash flash-error">{error}</div>;
  if (!data) return null;

  const p = data.portfolio || {};
  const moneda = data.moneda || 'COP';
  const fmt = (n: number) =>
    new Intl.NumberFormat('es-CO', { style: 'currency', currency: moneda }).format(n);

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Reportes</h1>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="metric-card">
          <div className="metric-label">Total créditos activos</div>
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
          <div className="metric-label">Plan</div>
          <div className="metric-value" style={{ fontSize: '18px' }}>
            {(data.plan || 'basic').toUpperCase()}
          </div>
        </div>
      </div>
    </div>
  );
}
