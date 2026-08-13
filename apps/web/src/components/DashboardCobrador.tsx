'use client';

import { useEffect, useState } from 'react';
import type { Ruta, Jornada } from '@/lib/api/client';
import { fetchRutas, fetchJornadas } from '@/lib/api/client';

/**
 * Superficie de campo del COBRADOR: jornada y ruta.
 *
 * Usa EXCLUSIVAMENTE endpoints que ya le pertenecen al COBRADOR en el backend
 * (GET /api/rutas y GET /api/jornadas filtran por su ruta activa derivada del
 * ctx, nunca por claims). No toca /api/inversionista/*.
 */
export function DashboardCobrador() {
  const [rutas, setRutas] = useState<Ruta[]>([]);
  const [jornadas, setJornadas] = useState<Jornada[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const [r, j] = await Promise.all([fetchRutas(), fetchJornadas()]);
        if (!alive) return;
        setRutas(r);
        setJornadas(j);
      } catch (e) {
        if (alive) setError((e as Error).message || 'Error al cargar datos');
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  if (loading) return <div className="text-text-secondary">Cargando...</div>;
  if (error) return <div className="text-red-600">Error: {error}</div>;

  const miRuta = rutas[0]; // el backend filtra a la ruta activa única del cobrador
  const jornadaActiva = jornadas.find((j) => j.estado === 'OPEN');

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Mi jornada</h1>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="metric-card">
          <div className="metric-label">Ruta asignada</div>
          <div className="metric-value">{miRuta?.nombre ?? 'Sin ruta activa'}</div>
        </div>

        <div className="metric-card">
          <div className="metric-label">Jornada</div>
          <div className={`metric-value ${jornadaActiva ? 'success' : 'warning'}`}>
            {jornadaActiva ? 'Abierta' : 'Sin jornada abierta'}
          </div>
        </div>
      </div>
    </div>
  );
}
