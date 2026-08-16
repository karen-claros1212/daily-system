'use client';

import { useState, useEffect } from 'react';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { hasCapability } from '@/lib/rbac';
import { fetchAudit, type AuditLog } from '@/lib/api/client';

const ACCION_LABELS: Record<string, string> = {
  USUARIO_CREADO: 'Usuario creado',
  USUARIO_EDITADO: 'Usuario editado',
  USUARIO_DESACTIVADO: 'Usuario desactivado',
  USUARIO_REACTIVADO: 'Usuario reactivado',
  CODIGO_ACTIVACION_GENERADO: 'Código de activación generado',
  CREDITO_CREADO: 'Crédito creado',
  CUOTA_PROGRAMADA: 'Cuota programada',
  PAGO_REGISTRADO: 'Pago registrado',
  JORNADA_CERRADA: 'Jornada cerrada',
  DISPOSITIVO_REGISTRADO: 'Dispositivo registrado',
  DISPOSITIVO_REVOCADO: 'Dispositivo revocado',
  DISPOSITIVO_REACTIVADO: 'Dispositivo reactivado',
  NEGOCIO_CREADO: 'Negocio creado',
};

const ENTIDAD_LABELS: Record<string, string> = {
  USUARIO: 'Usuario',
  CREDITO: 'Crédito',
  CUOTA: 'Cuota',
  PAGO: 'Pago',
  JORNADA: 'Jornada',
  DISPOSITIVO: 'Dispositivo',
  NEGOCIO: 'Negocio',
  RUTA: 'Ruta',
};

export function AuditoriaPage({ session }: { session: import("@/lib/rbac").SessionUser | null }) {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState({
    action: '',
    entity_type: '',
    limit: '50',
  });
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [page, setPage] = useState(1);

  const hasAudit = hasCapability(session, 'audit:ver');

  async function loadAudit() {
    try {
      setLoading(true);
      setError(null);
      const data = await fetchAudit({
        action: filters.action || undefined,
        entity_type: filters.entity_type || undefined,
        limit: filters.limit,
      });
      setLogs(data);
      setPage(1);
      setExpandedId(null);
    } catch {
      setError('Error al cargar logs de auditoría');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAudit();
  }, [filters.action, filters.entity_type, filters.limit]);

  function getAccionLabel(action: string): string {
    return ACCION_LABELS[action] || action;
  }

  function getEntidadLabel(entityType: string): string {
    return ENTIDAD_LABELS[entityType] || entityType;
  }

  function formatTimestamp(iso: string): string {
    const d = new Date(iso);
    return d.toLocaleString('es-CO', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  }

  if (!hasAudit) return null;

  return (
    <div className="space-y-6" role="main" aria-label="Auditoría">
      <h1 className="text-2xl font-bold text-textPrimary">Auditoría</h1>

      {error && (
        <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-500 text-sm" role="alert">
          {error}
        </div>
      )}

      <Card elevated>
        <div className="font-bold text-lg mb-4">Filtros</div>
        <div className="flex flex-wrap gap-4">
          <div className="flex-1 min-w-[180px]">
            <label htmlFor="filterAction" className="block text-sm text-textSecondary mb-1">Acción</label>
            <Input
              id="filterAction"
              value={filters.action}
              onChange={(e) => setFilters({ ...filters, action: e.target.value })}
              placeholder="Filtrar por acción"
              aria-label="Filtrar por acción"
            />
          </div>
          <div className="flex-1 min-w-[180px]">
            <label htmlFor="filterEntity" className="block text-sm text-textSecondary mb-1">Tipo de entidad</label>
            <Input
              id="filterEntity"
              value={filters.entity_type}
              onChange={(e) => setFilters({ ...filters, entity_type: e.target.value })}
              placeholder="Filtrar por entidad"
              aria-label="Filtrar por tipo de entidad"
            />
          </div>
          <div className="flex items-end">
            <Button onClick={loadAudit} variant="primary">Filtrar</Button>
          </div>
        </div>
      </Card>

      <Card elevated>
        <div className="font-bold text-lg mb-4">Logs ({logs.length})</div>
        {loading ? (
          <div className="text-center py-8 text-textSecondary" role="status" aria-label="Cargando logs">
            <div className="animate-pulse">Cargando logs de auditoría...</div>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm" role="table" aria-label="Registros de auditoría">
              <thead>
                <tr className="border-b border-outline">
                  <th className="text-left py-3 px-4 text-textSecondary font-medium" scope="col">Fecha</th>
                  <th className="text-left py-3 px-4 text-textSecondary font-medium" scope="col">Actor</th>
                  <th className="text-left py-3 px-4 text-textSecondary font-medium" scope="col">Acción</th>
                  <th className="text-left py-3 px-4 text-textSecondary font-medium" scope="col">Entidad</th>
                  <th className="text-left py-3 px-4 text-textSecondary font-medium" scope="col">Detalle</th>
                  <th className="text-left py-3 px-4 text-textSecondary font-medium" scope="col">Metadata</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log) => (
                  <tr key={log.id} className="border-b border-outline/50">
                    <td className="py-3 px-4 text-textSecondary whitespace-nowrap">
                      {formatTimestamp(log.creado_el)}
                    </td>
                    <td className="py-3 px-4">
                      {log.actor_nombre ? (
                        <span className="text-textPrimary" title={`ID: ${log.actor_id}`}>
                          {log.actor_nombre}
                        </span>
                      ) : (
                        <span className="text-textSecondary italic" title={`actor_id: ${log.actor_id}`}>
                          Sistema
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-4">
                      <Badge tone="neutral" title={log.action}>{getAccionLabel(log.action)}</Badge>
                    </td>
                    <td className="py-3 px-4 text-textSecondary">
                      {getEntidadLabel(log.entity_type)}
                    </td>
                    <td className="py-3 px-4">
                      <button
                        onClick={() => setExpandedId(expandedId === log.id ? null : log.id)}
                        className="text-primary hover:underline text-xs font-mono cursor-pointer focus:outline-none focus:ring-2 focus:ring-primary/50 rounded"
                        aria-expanded={expandedId === log.id}
                        aria-label={`Ver detalles de ${getAccionLabel(log.action)}`}
                      >
                        {expandedId === log.id ? 'Ocultar ▾' : 'Ver ▸'}
                      </button>
                    </td>
                    <td className="py-3 px-4 text-textSecondary font-mono text-xs max-w-[150px] truncate">
                      {log.metadata ? JSON.stringify(log.metadata).slice(0, 60) + (log.metadata ? '…' : '') : '—'}
                    </td>
                  </tr>
                ))}
                {logs.length === 0 && !loading && (
                  <tr>
                    <td colSpan={6} className="py-8 text-center text-textSecondary" aria-label="No hay logs">
                      {filters.action || filters.entity_type
                        ? 'No hay logs con los filtros aplicados'
                        : 'No hay logs de auditoría'}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Expanded detail panel */}
      {expandedId && (() => {
        const log = logs.find(l => l.id === expandedId);
        if (!log) return null;
        return (
          <Card elevated className="border-primary/30">
            <div className="font-bold text-base mb-3">Detalle del registro</div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
              <div>
                <span className="text-textSecondary">ID registro:</span>{' '}
                <code className="font-mono text-xs">{log.id}</code>
              </div>
              <div>
                <span className="text-textSecondary">negocio_id:</span>{' '}
                <code className="font-mono text-xs">{log.negocio_id}</code>
              </div>
              <div>
                <span className="text-textSecondary">actor_id:</span>{' '}
                <code className="font-mono text-xs">{log.actor_id}</code>
              </div>
              <div>
                <span className="text-textSecondary">actor_nombre:</span>{' '}
                <span>{log.actor_nombre || 'Sistema'}</span>
              </div>
              <div>
                <span className="text-textSecondary">acción:</span>{' '}
                <Badge tone="neutral">{log.action}</Badge>
              </div>
              <div>
                <span className="text-textSecondary">entidad:</span>{' '}
                <span>{log.entity_type}</span>
              </div>
              <div>
                <span className="text-textSecondary">entity_id:</span>{' '}
                <code className="font-mono text-xs">{log.entity_id || '—'}</code>
              </div>
              <div>
                <span className="text-textSecondary">IP:</span>{' '}
                <span className="font-mono text-xs">{log.ip_address || '—'}</span>
              </div>
              <div className="md:col-span-2">
                <span className="text-textSecondary">user_agent:</span>{' '}
                <span className="font-mono text-xs break-all">{log.user_agent || '—'}</span>
              </div>
              <div className="md:col-span-2">
                <span className="text-textSecondary">metadata:</span>
                <pre className="mt-1 p-2 bg-surface/50 rounded text-xs font-mono overflow-x-auto whitespace-pre-wrap">
                  {log.metadata ? JSON.stringify(log.metadata, null, 2) : '—'}
                </pre>
              </div>
              <div>
                <span className="text-textSecondary">creado_el:</span>{' '}
                <span>{formatTimestamp(log.creado_el)}</span>
              </div>
            </div>
            <div className="mt-3">
              <Button size="sm" variant="outline" onClick={() => setExpandedId(null)}>Cerrar detalle</Button>
            </div>
          </Card>
        );
      })()}
    </div>
  );
}
