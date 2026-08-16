'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { Card } from '@/components/ui/card';
import { Button, LoadingState, Flash } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { FormField } from '@/components/ui/field';
import { hasCapability } from '@/lib/rbac';
import { fetchRuta, reasignarRuta, type Ruta } from '@/lib/api/client';

export function RouteDetailPage({
  routeId,
  session,
}: {
  routeId: string;
  session: import('@/lib/rbac').SessionUser | null;
}) {
  const canReasignar = hasCapability(session, 'rutas:reasignar');
  const esCobrador = session?.rol === 'COBRADOR';

  const [route, setRoute] = useState<Ruta | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [confirmOpen, setConfirmOpen] = useState(false);
  const [nuevoNombre, setNuevoNombre] = useState('');
  const [confirming, setConfirming] = useState(false);
  const [resultado, setResultado] = useState<{ anterior: string; nueva: string } | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    let ignore = false;

    async function load() {
      try {
        setError(null);
        setSuccess(null);
        const data = await fetchRuta(routeId);
        if (!ignore) setRoute(data);
      } catch {
        if (!ignore) setError('No se pudo cargar la ruta');
      } finally {
        if (!ignore) setLoading(false);
      }
    }

    void load();

    return () => {
      ignore = true;
    };
  }, [routeId]);

  useEffect(() => {
    if (confirmOpen && inputRef.current) {
      inputRef.current.focus();
    }
  }, [confirmOpen]);

  function abrirConfirmacion() {
    console.log('abrirConfirmacion CALLED');
    setNuevoNombre('');
    setError(null);
    setSuccess(null);
    setResultado(null);
    setConfirmOpen(true);
  }

  async function confirmarReasignar(e: React.FormEvent) {
    e.preventDefault();
    console.log('confirmarReasignar CALLED');
    if (!route) return;
    const nombre = nuevoNombre.trim();
    if (!nombre) {
      setError('Ingresa el nuevo nombre de la ruta');
      return;
    }
    setError(null);
    setConfirming(true);
    try {
      const res = await reasignarRuta(route.id, { nombre });
      setResultado({ anterior: res.ruta_anterior_nombre, nueva: res.ruta_nueva_nombre });
      setConfirmOpen(false);
      setRoute({
        ...route,
        id: res.ruta_nueva_id,
        nombre: res.ruta_nueva_nombre,
        activa: 1,
        version: (route.version ?? 1) + 1,
      });
      setSuccess(
        `Ruta reasignada: "${res.ruta_anterior_nombre}" quedó inactiva y se activó "${res.ruta_nueva_nombre}" para el mismo cobrador.`,
      );
    } catch (err: unknown) {
      console.log('CATCH err:', err);
      console.log('CATCH err instanceof Error:', err instanceof Error);
      console.log('CATCH err.message:', err instanceof Error ? err.message : 'N/A');
      setError(err instanceof Error ? err.message : 'Error al reasignar la ruta');
    } finally {
      setConfirming(false);
    }
  }

  if (loading) return <LoadingState />;

  if (!route) {
    return (
      <div className="space-y-4">
        <Link href="/routes">
          <Button variant="outline" size="sm">← Volver a rutas</Button>
        </Link>
        <Flash tone="error">{error || 'Ruta no encontrada'}</Flash>
      </div>
    );
  }

  return (
    <div className="space-y-6" role="main" aria-label="Detalle de ruta">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link href="/routes">
            <Button variant="outline" size="sm">← Volver</Button>
          </Link>
          <h1 className="text-2xl font-bold text-textPrimary">{route.nombre}</h1>
          {estadoBadge(route.activa)}
        </div>
        {canReasignar && (
          <Button variant="primary" onClick={abrirConfirmacion}>
            Reasignar ruta
          </Button>
        )}
      </div>

      {success && <Flash tone="success">{success}</Flash>}

      {error && (
        <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-500 text-sm" role="alert">
          {error}
        </div>
      )}

      {resultado && (
        <Card elevated className="border-green-500/30 bg-green-500/5">
          <div className="font-bold text-green-600 mb-2">Reasignación completada (S4)</div>
          <div className="space-y-1 text-sm">
            <div><span className="text-textSecondary">Anterior:</span> {resultado.anterior} (inactiva)</div>
            <div><span className="text-textSecondary">Nueva:</span> {resultado.nueva} (activa)</div>
            <div className="text-textSecondary">El cobrador conserva la nueva ruta y su sesión móvil se invalidó (debe reautenticarse).</div>
          </div>
          <Button size="sm" variant="outline" className="mt-3" onClick={() => setResultado(null)}>
            Cerrar
          </Button>
        </Card>
      )}

      <Card className="p-0 overflow-hidden">
        <table className="table">
          <tbody>
            <tr>
              <td className="text-textSecondary py-2 w-1/3">ID</td>
              <td className="font-mono text-xs">{route.id}</td>
            </tr>
            <tr>
              <td className="text-textSecondary py-2">Cobrador</td>
              <td>{route.cobrador_nombre || '—'}</td>
            </tr>
            <tr>
              <td className="text-textSecondary py-2">Estado</td>
              <td>{estadoBadge(route.activa)}</td>
            </tr>
            <tr>
              <td className="text-textSecondary py-2">Versión de asignación</td>
              <td>{route.version ?? 1}</td>
            </tr>
            <tr>
              <td className="text-textSecondary py-2">Creada</td>
              <td>{route.creado_el ? new Date(route.creado_el).toLocaleString('es-CO') : '—'}</td>
            </tr>
          </tbody>
        </table>
      </Card>

      {canReasignar && (
        <Card className="border-outline">
          <div className="font-bold text-lg mb-2">Reasignar ruta (S4)</div>
          <p className="text-sm text-textSecondary mb-4">
            La reasignación crea una ruta nueva para el <strong>mismo cobrador</strong>: la ruta
            actual queda <strong>inactiva</strong> y la nueva pasa a ser su única ruta activa. La
            sesión móvil del cobrador se invalida (debe reautenticarse). Esta operación es
            irreversible.
          </p>
          <form onSubmit={confirmarReasignar} className="space-y-4">
            <FormField id="nuevo-nombre" label="Nuevo nombre de la ruta" messageTone="hint">
              <Input
                ref={inputRef}
                id="nuevo-nombre"
                value={nuevoNombre}
                onChange={(e) => setNuevoNombre(e.target.value)}
                placeholder="p. ej. Ruta Norte V2"
                required
                maxLength={100}
              />
            </FormField>
            <div className="flex gap-2">
              <Button type="submit" variant="primary" disabled={confirming}>
                {confirming ? 'Reasignando…' : 'Confirmar reasignación'}
              </Button>
              <Button type="button" variant="outline" onClick={() => setNuevoNombre('')}>
                Limpiar
              </Button>
            </div>
            {esCobrador && (
              <p className="text-xs text-textSecondary">
                Solo el administrador puede reasignar rutas.
              </p>
            )}
          </form>
        </Card>
      )}
    </div>
  );
}

function estadoBadge(activa: number) {
  return (
    <Badge tone={activa === 1 ? 'success' : 'warning'}>{activa === 1 ? 'Activa' : 'Inactiva'}</Badge>
  );
}
