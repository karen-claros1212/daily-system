'use client';

import { useState, useEffect } from 'react';
import { fetchRutas, fetchRuta, fetchJornadas, Ruta, Jornada } from '@/lib/api/client';

export function Routes() {
  const [routes, setRoutes] = useState<Ruta[]>([]);
  const [selectedRoute, setSelectedRoute] = useState<string | null>(null);
  const [routeDetail, setRouteDetail] = useState<Ruta | null>(null);
  const [jornada, setJornada] = useState<Jornada | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    load();
  }, []);

  async function load() {
    try {
      setLoading(true);
      setRoutes(await fetchRutas());
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error al cargar rutas');
    } finally {
      setLoading(false);
    }
  }

  async function showDetail(routeId: string) {
    try {
      const route = await fetchRuta(routeId);
      const jornadas = await fetchJornadas();
      const today = new Date().toISOString().slice(0, 10);
      const todayJornada = jornadas.find((j) => j.fecha === today);

      setRouteDetail(route);
      setJornada(todayJornada || null);
      setSelectedRoute(routeId);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error al cargar detalle');
    }
  }

  function goBack() {
    setSelectedRoute(null);
    setRouteDetail(null);
    setJornada(null);
  }

  if (loading) return <div className="text-text-secondary">Cargando...</div>;
  if (error) return <div className="flash flash-error">{error}</div>;

  if (selectedRoute && routeDetail) {
    return (
      <div className="space-y-4">
        <button onClick={goBack} className="btn btn-outline text-sm">
          ← Volver
        </button>

        <div className="bg-white rounded-lg p-4 border border-outline">
          <h2 className="text-lg font-semibold mb-4">{routeDetail.nombre || routeDetail.id}</h2>

          <table className="w-full text-sm">
            <tbody>
              <tr>
                <td className="text-text-secondary py-2 w-1/3">ID</td>
                <td>{routeDetail.id}</td>
              </tr>
              <tr>
                <td className="text-text-secondary py-2">Cobrador</td>
                <td>{routeDetail.cobrador_id || '—'}</td>
              </tr>
              <tr>
                <td className="text-text-secondary py-2">Estado</td>
                <td>
                  <span className={`badge ${routeDetail.activa ? 'badge-success' : 'badge-warning'}`}>
                    {routeDetail.activa ? 'Activa' : 'Inactiva'}
                  </span>
                </td>
              </tr>
              <tr>
                <td className="text-text-secondary py-2">Versión</td>
                <td>{routeDetail.version || 1}</td>
              </tr>
            </tbody>
          </table>

          {jornada && (
            <>
              <hr className="my-4 border-outline" />
              <h3 className="font-semibold mb-2">Jornada de hoy</h3>
              <table className="w-full text-sm">
                <tbody>
                  <tr>
                    <td className="text-text-secondary py-2">Estado</td>
                    <td>
                      <span className={`badge ${['CLOSED_SYNCED', 'CLOSED_LOCAL_PENDING_SYNC'].includes(jornada.estado) ? 'badge-success' : 'badge-warning'}`}>
                        {jornada.estado}
                      </span>
                    </td>
                  </tr>
                  {jornada.esperado !== undefined && (
                    <tr>
                      <td className="text-text-secondary py-2">Esperado</td>
                      <td>${jornada.esperado.toLocaleString('es-CO')}</td>
                    </tr>
                  )}
                  {jornada.contado !== undefined && (
                    <tr>
                      <td className="text-text-secondary py-2">Contado</td>
                      <td>${jornada.contado.toLocaleString('es-CO')}</td>
                    </tr>
                  )}
                  {jornada.diferencia !== undefined && (
                    <tr>
                      <td className="text-text-secondary py-2">Diferencia</td>
                      <td style={{ color: jornada.diferencia !== 0 ? 'var(--ds-warning)' : 'var(--ds-success)' }}>
                        ${jornada.diferencia.toLocaleString('es-CO')}
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </>
          )}

          {!jornada && (
            <p className="text-sm text-text-secondary mt-4">No hay jornada abierta para hoy.</p>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Rutas</h1>

      <div className="bg-white rounded-lg border border-outline overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-surfaceContainer">
            <tr>
              <th className="text-left px-4 py-3">Ruta</th>
              <th className="text-left px-4 py-3">Cobrador</th>
              <th className="text-left px-4 py-3">Estado</th>
              <th className="text-left px-4 py-3">Acción</th>
            </tr>
          </thead>
          <tbody>
            {routes.map((route) => (
              <tr key={route.id} className="border-t border-outline">
                <td className="px-4 py-3">{route.nombre || route.id}</td>
                <td className="px-4 py-3">{route.cobrador_id || '—'}</td>
                <td className="px-4 py-3">
                  <span className={`badge ${route.activa ? 'badge-success' : 'badge-warning'}`}>
                    {route.activa ? 'Activa' : 'Inactiva'}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <button
                    onClick={() => showDetail(route.id)}
                    className="btn btn-outline text-xs"
                  >
                    Ver detalle
                  </button>
                </td>
              </tr>
            ))}
            {routes.length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-8 text-center text-text-secondary">
                  No hay rutas registradas.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
