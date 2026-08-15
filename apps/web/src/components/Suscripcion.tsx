'use client';

import { useState, useEffect, useCallback } from 'react';
import { fetchSuscripcion, ApiError, type Suscripcion } from '@/lib/api/client';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button, Flash, LoadingState } from '@/components/ui/button';
import { IconLock } from '@/components/ui/icons';

/** Formatea una fecha ISO del contrato (país es-CO, sin hora técnica). */
function formatFecha(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return new Intl.DateTimeFormat('es-CO', { dateStyle: 'long' }).format(d);
}

/**
 * Superficie de Suscripción / Licencia (Etapa 3 — "que se venda").
 *
 * EL BACKEND ES LA AUTORIDAD: esta página NO computa un booleano local de
 * licencia ni autoriza operaciones. Muestra exactamente lo que entrega
 * GET /api/inversionista/suscripcion (`estado_suscripcion`, `plan`,
 * `paid_through_at`, `activa`). Si una licencia vencida bloquea capacidades,
 * el backend decide; aquí solo se refleja el estado.
 *
 * Estados: loading/skeleton · activa · bloqueada (vencida u otro estado no
 * activo) · 401 (sesión inexistente) · 403 (sesión válida sin permiso, SIN
 * redirect silencioso) · error transitorio recuperable con reintento.
 */
export function Suscripcion() {
  const [data, setData] = useState<Suscripcion | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<{ status: number; message: string } | null>(null);

  const load = useCallback(async () => {
    try {
      setData(await fetchSuscripcion());
      setError(null);
    } catch (e) {
      const status = e instanceof ApiError ? e.status : 0;
      const message = e instanceof Error ? e.message : 'Error al cargar la suscripción';
      setError({ status, message });
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

  // 403: sesión válida pero sin permiso (rol sin capability o rechazo del
  // backend). NO es un redirect silencioso al login: vista controlada.
  if (error?.status === 403) {
    return (
      <div className="max-w-md mx-auto py-16 text-center space-y-4">
        <div className="flex justify-center">
          <IconLock size={40} aria-hidden="true" className="text-textSecondary" />
        </div>
        <h1 className="text-2xl font-bold">Acceso denegado</h1>
        <p className="text-textSecondary">
          Tu sesión está autenticada pero el rol no tiene permisos para ver la suscripción.
        </p>
        <div className="flex justify-center gap-3 pt-2">
          <Button size="sm" onClick={() => { setLoading(true); void load(); }}>
            Reintentar
          </Button>
        </div>
      </div>
    );
  }

  // 401: sesión inexistente/rechazada (el SessionRenewer cierra la sesión).
  if (error?.status === 401) {
    return (
      <Flash tone="warning">
        Tu sesión expiró. Vuelve a iniciar sesión para ver tu suscripción.
      </Flash>
    );
  }

  // Error transitorio (5xx / red): recuperable con reintento, sin estado falso.
  if (error) {
    return (
      <div className="space-y-4">
        <Flash tone="error">No se pudo cargar la suscripción en este momento.</Flash>
        <Button size="sm" onClick={() => { setLoading(true); void load(); }}>
          Reintentar
        </Button>
      </div>
    );
  }

  if (!data) return null;

  const vigencia = formatFecha(data.paid_through_at);
  const plan = data.plan || 'basic';
  const activa = data.activa;
  const estado = data.estado_suscripcion;

  return (
    <div className="space-y-4 max-w-2xl">
      <h1 className="text-2xl font-bold">Suscripción</h1>

      <Card padding="lg" elevated>
        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="text-textSecondary">Estado</span>
              {activa ? (
                <Badge tone="success" dot>
                  Activa
                </Badge>
              ) : (
                <Badge tone={estado === 'vencida' ? 'danger' : 'warning'} dot>
                  {estado === 'vencida' ? 'Vencida' : 'No activa'}
                </Badge>
              )}
            </div>
            <div className="flex items-center gap-2">
              <span className="text-textSecondary">Plan</span>
              <span className="font-semibold uppercase">{plan}</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-textSecondary">Vigencia</span>
              <span className={activa ? '' : 'text-textSecondary'}>
                {vigencia ? `Hasta el ${vigencia}` : 'Sin fecha de vencimiento registrada'}
              </span>
            </div>
          </div>
        </div>

        {!activa && (
          <p className="mt-4 text-sm text-textSecondary">
            {estado === 'vencida'
              ? 'Tu suscripción venció. Algunas funciones del sistema pueden estar bloqueadas.'
              : 'Tu suscripción no está activa. Algunas funciones del sistema pueden estar bloqueadas.'}
          </p>
        )}
      </Card>

      <p className="text-sm text-textSecondary">
        El estado de tu licencia es definido por el sistema en cada operación; esta página lo refleja.
      </p>
    </div>
  );
}
