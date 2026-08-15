'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  fetchDispositivos,
  revocarDispositivo,
  reactivarDispositivo,
  reemplazarDispositivo,
  ApiError,
  type Dispositivo,
  type CodigoActivacion,
} from '@/lib/api/client';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button, Flash, LoadingState, EmptyState } from '@/components/ui/button';
import { IconKey, IconLock, IconShield } from '@/components/ui/icons';

/** Formatea una fecha ISO del contrato (país es-CO, sin hora técnica). */
function formatFecha(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return new Intl.DateTimeFormat('es-CO', { dateStyle: 'long' }).format(d);
}

/** Confirmación destructiva discriminada: un solo camino activo a la vez. */
type ConfirmAccion = 'REVOKE' | 'REPLACE';

const ESTADO_LABEL: Record<string, { label: string; tone: 'success' | 'danger' | 'warning' | 'neutral' }> = {
  ACTIVE: { label: 'Autorizado', tone: 'success' },
  REVOKED: { label: 'Revocado', tone: 'danger' },
  REPLACED: { label: 'Reemplazado', tone: 'warning' },
};

/**
 * Superficie administrativa de Dispositivos Autorizados (Etapa 3 — "que se vende").
 *
 * EL BACKEND ES LA AUTORIDAD: esta página solo representa y opera lo que
 * entrega GET /api/dispositivos (`estado`, `activo`, `modelo`, `plataforma`,
 * fechas) y consume las operaciones productivas que ya existen (revocar,
 * reactivar, reemplazar). No expone secretos: jamás muestra huella,
 * public_key_hash, claves ni IDs técnicos completos. El contrato no entrega
 * un nombre humano del cobrador, así que la tarjeta tampoco muestra su UUID
 * (si un contrato futuro entrega `usuario_nombre`, se puede presentar).
 * Los códigos de activación los genera el backend y se muestran tal cual los
 * devuelve.
 *
 * La confirmación destructiva es DISCRIMINADA: al pulsar Revocar se ofrece
 * solo "Confirmar revocación" y al pulsar Reemplazar solo "Confirmar
 * reemplazo" — nunca ambas a la vez.
 *
 * Un dispositivo ACTIVE NO ofrece "generar código": canjear un código nuevo
 * para un cobrador que ya tiene su celular activo choca con el backend (409,
 * una invariante de UN dispositivo ACTIVE por cobrador). El camino canónico
 * para renovar su dispositivo es Reemplazar (marca el viejo REPLACED y emite
 * un código nuevo).
 *
 * Estados: loading/skeleton · lista · vacío · 401 · 403 (SIN redirect
 * silencioso) · error transitorio recuperable con reintento.
 */
export function Dispositivos() {
  const [dispositivos, setDispositivos] = useState<Dispositivo[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<{ status: number; message: string } | null>(null);
  const [flash, setFlash] = useState<{ tone: 'error' | 'success'; text: string } | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [confirm, setConfirm] = useState<{ id: string; action: ConfirmAccion } | null>(null);
  const [codigo, setCodigo] = useState<{ deviceId: string; codigo: CodigoActivacion } | null>(null);

  const load = useCallback(async () => {
    try {
      setDispositivos(await fetchDispositivos());
      setError(null);
    } catch (e) {
      const status = e instanceof ApiError ? e.status : 0;
      const message = e instanceof Error ? e.message : 'Error al cargar los dispositivos';
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

  const runAction = async (
    id: string,
    action: () => Promise<Dispositivo>,
    okText: string,
    conflictText?: string,
  ) => {
    setBusyId(id);
    setFlash(null);
    try {
      const updated = await action();
      setDispositivos((prev) =>
        prev ? prev.map((d) => (d.id === id ? { ...d, ...updated } : d)) : prev,
      );
      setConfirm(null);
      setFlash({ tone: 'success', text: okText });
    } catch (e) {
      const status = e instanceof ApiError ? e.status : 0;
      const detail = e instanceof Error ? e.message : 'Error al ejecutar la operación';
      if (status === 401) {
        setFlash({ tone: 'error', text: 'Tu sesión expiró. Vuelve a iniciar sesión.' });
      } else if (status === 403) {
        setFlash({ tone: 'error', text: 'No tienes permisos para ejecutar esta operación.' });
      } else if (status === 409 && conflictText) {
        // 409 = invariante del backend (p.ej. reactivar con otro ACTIVE del
        // mismo cobrador): mensaje de producto, no el detalle técnico crudo.
        setFlash({ tone: 'error', text: conflictText });
      } else {
        setFlash({ tone: 'error', text: `No se pudo completar la operación. ${detail}` });
      }
    } finally {
      setBusyId(null);
    }
  };

  const handleRevocar = (d: Dispositivo) =>
    runAction(d.id, () => revocarDispositivo(d.id), 'Dispositivo revocado correctamente.');

  const handleReactivar = (d: Dispositivo) =>
    runAction(
      d.id,
      () => reactivarDispositivo(d.id),
      'Dispositivo reactivado correctamente.',
      'No se puede reactivar este dispositivo porque el cobrador ya tiene otro dispositivo activo.',
    );

  const handleReemplazar = async (d: Dispositivo) => {
    setBusyId(d.id);
    setFlash(null);
    try {
      const res = await reemplazarDispositivo(d.id);
      setDispositivos((prev) =>
        prev ? prev.map((x) => (x.id === d.id ? { ...x, ...res.dispositivo } : x)) : prev,
      );
      setConfirm(null);
      setCodigo({ deviceId: d.id, codigo: res.nuevo_codigo });
    } catch (e) {
      const status = e instanceof ApiError ? e.status : 0;
      setFlash({
        tone: 'error',
        text: status === 403
          ? 'No tienes permisos para ejecutar esta operación.'
          : 'No se pudo reemplazar el dispositivo. Verifica que tenga cobrador asignado.',
      });
    } finally {
      setBusyId(null);
    }
  };

  if (loading) return <LoadingState label="Cargando dispositivos..." />;

  // 403: sesión válida sin permiso (el backend también rechaza las acciones).
  if (error?.status === 403) {
    return (
      <div className="max-w-md mx-auto py-16 text-center space-y-4">
        <div className="flex justify-center">
          <IconLock size={40} aria-hidden="true" className="text-textSecondary" />
        </div>
        <h1 className="text-2xl font-bold">Acceso denegado</h1>
        <p className="text-textSecondary">
          Tu sesión está autenticada pero el rol no tiene permisos para gestionar dispositivos.
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
        Tu sesión expiró. Vuelve a iniciar sesión para gestionar dispositivos.
      </Flash>
    );
  }

  // Error transitorio (5xx / red): recuperable con reintento, sin estado falso.
  if (error) {
    return (
      <div className="space-y-4">
        <Flash tone="error">No se pudieron cargar los dispositivos en este momento.</Flash>
        <Button size="sm" onClick={() => { setLoading(true); void load(); }}>
          Reintentar
        </Button>
      </div>
    );
  }

  if (!dispositivos) return null;

  return (
    <div className="space-y-4 max-w-3xl">
      <h1 className="text-2xl font-bold">Dispositivos autorizados</h1>

      {flash && (
        <Flash tone={flash.tone}>{flash.text}</Flash>
      )}

      {codigo && (
        <Card padding="lg" elevated className="space-y-3">
          <div className="flex items-center gap-2">
            <IconKey size={18} aria-hidden="true" className="text-primary" />
            <h2 className="font-semibold">Nuevo código de activación</h2>
          </div>
          <p className="text-sm text-textSecondary">
            Pásale este código al cobrador para activar su dispositivo. Es de un solo uso y expira.
          </p>
          <div className="bg-bg border border-outline rounded-md p-3 font-mono text-sm break-all">
            {codigo.codigo.prefijo}-{codigo.codigo.token}
          </div>
          <div className="flex items-center gap-2 text-sm text-textSecondary">
            <span>Expira:</span>
            <span>{codigo.codigo.expira_el ? formatFecha(codigo.codigo.expira_el) : '—'}</span>
          </div>
          <Button size="sm" variant="outline" onClick={() => setCodigo(null)}>
            Cerrar
          </Button>
        </Card>
      )}

      {dispositivos.length === 0 ? (
        <EmptyState
          icon={<IconShield size={28} aria-hidden="true" className="text-textSecondary" />}
          title="No hay dispositivos registrados"
          description="Cuando un cobrador active su celular con un código de activación, aparecerá aquí."
        />
      ) : (
        <ul className="space-y-3">
          {dispositivos.map((d) => {
            const estado = ESTADO_LABEL[d.estado] ?? {
              label: d.estado || 'Desconocido',
              tone: 'neutral' as const,
            };
            const autorizado = formatFecha(d.autorizado_el);
            const revocado = formatFecha(d.revocado_el);
            const ultimaValidacion = formatFecha(d.ultima_validacion_servidor);
            const esActivo = d.estado === 'ACTIVE';
            const esRevocado = d.estado === 'REVOKED';
            const toggleConfirm = (action: ConfirmAccion) =>
              setConfirm(
                confirm && confirm.id === d.id && confirm.action === action
                  ? null
                  : { id: d.id, action },
              );
            return (
              <li key={d.id}>
                <Card padding="md" className="space-y-2">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <Badge tone={estado.tone} dot>
                        {estado.label}
                      </Badge>
                      <span className="font-semibold">{d.modelo || 'Dispositivo móvil'}</span>
                      {d.plataforma && (
                        <span className="text-sm text-textSecondary">{d.plataforma}</span>
                      )}
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      {esActivo && (
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={busyId === d.id}
                          onClick={() => toggleConfirm('REPLACE')}
                        >
                          Reemplazar
                        </Button>
                      )}
                      {esActivo && (
                        <Button
                          size="sm"
                          variant="danger"
                          disabled={busyId === d.id}
                          onClick={() => toggleConfirm('REVOKE')}
                        >
                          Revocar
                        </Button>
                      )}
                      {esRevocado && (
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={busyId === d.id}
                          loading={busyId === d.id}
                          onClick={() => handleReactivar(d)}
                        >
                          Reactivar
                        </Button>
                      )}
                    </div>
                  </div>

                  <dl className="grid sm:grid-cols-2 gap-x-4 gap-y-1 text-sm">
                    <div className="flex items-center gap-2">
                      <dt className="text-textSecondary">Autorizado</dt>
                      <dd>{autorizado ?? '—'}</dd>
                    </div>
                    {revocado && (
                      <div className="flex items-center gap-2">
                        <dt className="text-textSecondary">Revocado</dt>
                        <dd>{revocado}</dd>
                      </div>
                    )}
                    <div className="flex items-center gap-2">
                      <dt className="text-textSecondary">Última validación</dt>
                      <dd>{ultimaValidacion ?? '—'}</dd>
                    </div>
                  </dl>

                  {confirm && confirm.id === d.id && esActivo && (
                    <div className="flex flex-wrap items-center gap-2 pt-1 border-t border-outline">
                      {confirm.action === 'REPLACE' && (
                        <Button
                          size="sm"
                          variant="danger"
                          loading={busyId === d.id}
                          onClick={() => handleReemplazar(d)}
                        >
                          Confirmar reemplazo (genera código nuevo)
                        </Button>
                      )}
                      {confirm.action === 'REVOKE' && (
                        <Button
                          size="sm"
                          variant="danger"
                          loading={busyId === d.id}
                          onClick={() => handleRevocar(d)}
                        >
                          Confirmar revocación
                        </Button>
                      )}
                      <Button size="sm" variant="ghost" onClick={() => setConfirm(null)}>
                        Cancelar
                      </Button>
                    </div>
                  )}
                </Card>
              </li>
            );
          })}
        </ul>
      )}

      <p className="text-sm text-textSecondary">
        La autoridad de cada dispositivo la conserva el sistema en cada operación; esta página
        refleja y opera sobre los datos que entrega el backend.
      </p>
    </div>
  );
}
