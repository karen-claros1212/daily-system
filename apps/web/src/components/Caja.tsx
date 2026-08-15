'use client';

import { useState, useEffect, useCallback } from 'react';
import { fetchJornadas, Jornada } from '@/lib/api/client';
import { Badge } from '@/components/ui/badge';
import { LoadingState, Flash } from '@/components/ui/button';

export function Caja() {
  const [jornadas, setJornadas] = useState<Jornada[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    try {
      setJornadas(await fetchJornadas());
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error al cargar jornadas');
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

  const today = new Date().toISOString().slice(0, 10);
  const todayJornadas = jornadas.filter((j) => j.fecha === today);

  const totalEsperado = todayJornadas.reduce((sum, j) => sum + (j.esperado || 0), 0);
  const totalContado = todayJornadas.reduce((sum, j) => sum + (j.contado || 0), 0);
  const totalDiferencia = todayJornadas.reduce((sum, j) => sum + (j.diferencia || 0), 0);
  const cerrada = (j: Jornada) =>
    ['CLOSED_SYNCED', 'CLOSED_LOCAL_PENDING_SYNC'].includes(j.estado);

  if (loading) return <LoadingState />;
  if (error) return <Flash tone="error">{error}</Flash>;

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Caja / Conciliación</h1>

      <div className="metric-card">
        <div className="metric-label">Resumen de hoy</div>
        <div className="grid grid-cols-3 gap-4 mt-2">
          <div>
            <div className="text-xs text-textSecondary">Esperado</div>
            <div className="text-xl font-bold">${totalEsperado.toLocaleString('es-CO')}</div>
          </div>
          <div>
            <div className="text-xs text-textSecondary">Contado</div>
            <div className="text-xl font-bold">${totalContado.toLocaleString('es-CO')}</div>
          </div>
          <div>
            <div className="text-xs text-textSecondary">Diferencia</div>
            <div className={`text-xl font-bold ${totalDiferencia !== 0 ? 'text-warning' : 'text-success'}`}>
              ${totalDiferencia.toLocaleString('es-CO')}
            </div>
          </div>
        </div>
      </div>

      {todayJornadas.length === 0 && (
        <p className="text-sm text-textSecondary">No hay jornadas cerradas para hoy.</p>
      )}

      {jornadas.length > 0 && (
        <div className="bg-surface rounded-lg border border-outline overflow-hidden">
          <table className="table">
            <thead>
              <tr>
                <th>Fecha</th>
                <th>Estado</th>
                <th>Esperado</th>
                <th>Contado</th>
                <th>Diferencia</th>
              </tr>
            </thead>
            <tbody>
              {[...jornadas].reverse().slice(0, 30).map((j) => (
                <tr key={j.id}>
                  <td>{j.fecha}</td>
                  <td>
                    <Badge tone={cerrada(j) ? 'success' : 'warning'}>{j.estado}</Badge>
                  </td>
                  <td>${(j.esperado || 0).toLocaleString('es-CO')}</td>
                  <td>${(j.contado || 0).toLocaleString('es-CO')}</td>
                  <td className={(j.diferencia || 0) !== 0 ? 'text-warning' : 'text-success'}>
                    ${(j.diferencia || 0).toLocaleString('es-CO')}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}