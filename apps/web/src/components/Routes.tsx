'use client';

import { useState, useEffect } from 'react';
import { fetchRutas, fetchRuta, fetchJornadas, Ruta, Jornada } from '@/lib/api/client';
import { Badge } from '@/components/ui/badge';
import { Button, LoadingState, Flash } from '@/components/ui/button';

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

  if (loading) return <LoadingState />;
  if (error) return <Flash tone="error">{error}</Flash>;

  const cerrada = (j: Jornada) =>
    ['CLOSED_SYNCED', 'CLOSED_LOCAL_PENDING_SYNC'].includes(j.estado);

  if (selectedRoute && routeDetail) {
    return (
      <div className="space-y-4">
        <Button variant="outline" size="sm" onClick={goBack}>
          ← Volver
        </Button>

        <div className="card">
          <h2 className="text-lg font-semibold mb-4">{routeDetail.nombre || routeDetail.id}</h2>

          <table className="table">
            <tbody>
              <tr>
                <td className="text-textSecondary py-2 w-1/3">ID</td>
                <td>{routeDetail.id}</td>
              </tr>
              <tr>
                <td className="text-textSecondary py-2">Cobrador</td>
                <td>{routeDetail.cobrador_id || '—'}</td>
              </tr>
              <tr>
                <td className="text-textSecondary py-2">Estado</td>
                <td>
                  <Badge tone={routeDetail.activa ? 'success' : 'warning'}>
                    {routeDetail.activa ? 'Activa' : 'Inactiva'}
                  </Badge>
                </td>
              </tr>
              <tr>
                <td className="text-textSecondary py-2">Versión</td>
                <td>{routeDetail.version || 1}</td>
              </tr>
            </tbody>
          </table>

          {jornada && (
            <>
              <hr className="divider" />
              <h3 className="font-semibold mb-2">Jornada de hoy</h3>
              <table className="table">
                <tbody>
                  <tr>
                    <td className="text-textSecondary py-2">Estado</td>
                    <td>
                      <Badge tone={cerrada(jornada) ? 'success' : 'warning'}>{jornada.estado}</Badge>
                    </td>
                  </tr>
                  {jornada.esperado !== undefined && (
                    <tr>
                      <td className="text-textSecondary py-2">Esperado</td>
                      <td>${jornada.esperado.toLocaleString('es-CO')}</td>
                    </tr>
                  )}
                  {jornada.contado !== undefined && (
                    <tr>
                      <td className="text-textSecondary py-2">Contado</td>
                      <td>${jornada.contado.toLocaleString('es-CO')}</td>
                    </tr>
                  )}
                  {jornada.diferencia !== undefined && (
                    <tr>
                      <td className="text-textSecondary py-2">Diferencia</td>
                      <td
                        className={
                          jornada.diferencia !== 0 ? 'text-warning font-medium' : 'text-success font-medium'
                        }
                      >
                        ${jornada.diferencia.toLocaleString('es-CO')}
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </>
          )}

          {!jornada && (
            <p className="text-sm text-textSecondary mt-4">No hay jornada abierta para hoy.</p>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Rutas</h1>

      <div className="card p-0 overflow-hidden">
        <table className="table">
          <thead>
            <tr>
              <th>Ruta</th>
              <th>Cobrador</th>
              <th>Estado</th>
              <th>Acción</th>
            </tr>
          </thead>
          <tbody>
            {routes.map((route) => (
              <tr key={route.id}>
                <td>{route.nombre || route.id}</td>
                <td>{route.cobrador_id || '—'}</td>
                <td>
                  <Badge tone={route.activa ? 'success' : 'warning'}>
                    {route.activa ? 'Activa' : 'Inactiva'}
                  </Badge>
                </td>
                <td>
                  <Button variant="outline" size="sm" onClick={() => showDetail(route.id)}>
                    Ver detalle
                  </Button>
                </td>
              </tr>
            ))}
            {routes.length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-8 text-center text-textSecondary">
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