'use client';

import { useState, useEffect } from 'react';
import { fetchJornadas, Jornada } from '@/lib/api/client';

export function Caja() {
  const [jornadas, setJornadas] = useState<Jornada[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    load();
  }, []);

  async function load() {
    try {
      setLoading(true);
      setJornadas(await fetchJornadas());
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error al cargar jornadas');
    } finally {
      setLoading(false);
    }
  }

  const today = new Date().toISOString().slice(0, 10);
  const todayJornadas = jornadas.filter((j) => j.fecha === today);

  const totalEsperado = todayJornadas.reduce((sum, j) => sum + (j.esperado || 0), 0);
  const totalContado = todayJornadas.reduce((sum, j) => sum + (j.contado || 0), 0);
  const totalDiferencia = todayJornadas.reduce((sum, j) => sum + (j.diferencia || 0), 0);

  if (loading) return <div className="text-text-secondary">Cargando...</div>;
  if (error) return <div className="flash flash-error">{error}</div>;

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Caja / Conciliación</h1>

      <div className="metric-card">
        <div className="metric-label">Resumen de hoy</div>
        <div className="grid grid-cols-3 gap-4 mt-2">
          <div>
            <div className="text-xs text-text-secondary">Esperado</div>
            <div className="text-xl font-bold">${totalEsperado.toLocaleString('es-CO')}</div>
          </div>
          <div>
            <div className="text-xs text-text-secondary">Contado</div>
            <div className="text-xl font-bold">${totalContado.toLocaleString('es-CO')}</div>
          </div>
          <div>
            <div className="text-xs text-text-secondary">Diferencia</div>
            <div className={`text-xl font-bold ${totalDiferencia !== 0 ? 'text-warning' : 'text-success'}`}>
              ${totalDiferencia.toLocaleString('es-CO')}
            </div>
          </div>
        </div>
      </div>

      {todayJornadas.length === 0 && (
        <p className="text-sm text-text-secondary">No hay jornadas cerradas para hoy.</p>
      )}

      {jornadas.length > 0 && (
        <div className="bg-white rounded-lg border border-outline overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-surfaceContainer">
              <tr>
                <th className="text-left px-4 py-3">Fecha</th>
                <th className="text-left px-4 py-3">Estado</th>
                <th className="text-left px-4 py-3">Esperado</th>
                <th className="text-left px-4 py-3">Contado</th>
                <th className="text-left px-4 py-3">Diferencia</th>
              </tr>
            </thead>
            <tbody>
              {[...jornadas].reverse().slice(0, 30).map((j) => (
                <tr key={j.id} className="border-t border-outline">
                  <td className="px-4 py-3">{j.fecha}</td>
                  <td className="px-4 py-3">
                    <span className={`badge ${['CLOSED_SYNCED', 'CLOSED_LOCAL_PENDING_SYNC'].includes(j.estado) ? 'badge-success' : 'badge-warning'}`}>
                      {j.estado}
                    </span>
                  </td>
                  <td className="px-4 py-3">${(j.esperado || 0).toLocaleString('es-CO')}</td>
                  <td className="px-4 py-3">${(j.contado || 0).toLocaleString('es-CO')}</td>
                  <td className={`px-4 py-3 ${(j.diferencia || 0) !== 0 ? 'text-warning' : 'text-success'}`}>
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
