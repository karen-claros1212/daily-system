'use client';

import { useState, useEffect } from 'react';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { hasCapability } from '@/lib/rbac';

import { fetchAudit, type AuditLog } from '@/lib/api/client';

export function AuditoriaPage({ session }: { session: import("@/lib/rbac").SessionUser | null }) {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState({
    action: '',
    entity_type: '',
    limit: '50',
  });

  const hasAudit = hasCapability(session, 'audit:ver');
  const _session = session;

  useEffect(() => {
    loadAudit();
  }, [filters]);

  async function loadAudit() {
    try {
      setLoading(true);
      const data = await fetchAudit({
        action: filters.action || undefined,
        entity_type: filters.entity_type || undefined,
        limit: filters.limit,
      });
      setLogs(data);
    } catch (e) {
      setError('Error al cargar logs de auditoría');
    } finally {
      setLoading(false);
    }
  }

  if (!hasAudit) return null;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-textPrimary">Auditoría</h1>

      {error && (
        <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-500 text-sm">
          {error}
        </div>
      )}

      <Card elevated>
        <div className="font-bold text-lg mb-4">Filtros</div>
        <div className="flex flex-wrap gap-4">
          <div className="flex-1 min-w-[200px]">
            <label className="block text-sm text-textSecondary mb-1">Acción</label>
            <Input
              value={filters.action}
              onChange={(e) => setFilters({ ...filters, action: e.target.value })}
              placeholder="Filtrar por acción"
            />
          </div>
          <div className="flex-1 min-w-[200px]">
            <label className="block text-sm text-textSecondary mb-1">Tipo de entidad</label>
            <Input
              value={filters.entity_type}
              onChange={(e) => setFilters({ ...filters, entity_type: e.target.value })}
              placeholder="Filtrar por entidad"
            />
          </div>
          <div className="flex items-end">
            <Button onClick={loadAudit} variant="primary">Aplicar</Button>
          </div>
        </div>
      </Card>

      <Card elevated>
        <div className="font-bold text-lg mb-4">Logs ({logs.length})</div>
        {loading ? (
          <div className="text-center py-8 text-textSecondary">Cargando...</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-outline">
                  <th className="text-left py-3 px-4 text-textSecondary font-medium">Fecha</th>
                  <th className="text-left py-3 px-4 text-textSecondary font-medium">Acción</th>
                  <th className="text-left py-3 px-4 text-textSecondary font-medium">Entidad</th>
                  <th className="text-left py-3 px-4 text-textSecondary font-medium">ID Entidad</th>
                  <th className="text-left py-3 px-4 text-textSecondary font-medium">Metadata</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log) => (
                  <tr key={log.id} className="border-b border-outline/50">
                    <td className="py-3 px-4 text-textSecondary">
                      {new Date(log.creado_el).toLocaleString('es-CO')}
                    </td>
                    <td className="py-3 px-4">
                      <Badge tone="neutral">{log.action}</Badge>
                    </td>
                    <td className="py-3 px-4 text-textSecondary">{log.entity_type}</td>
                    <td className="py-3 px-4 text-textSecondary font-mono text-xs">
                      {log.entity_id || '—'}
                    </td>
                    <td className="py-3 px-4 text-textSecondary font-mono text-xs max-w-[200px] truncate">
                      {log.metadata ? JSON.stringify(log.metadata) : '—'}
                    </td>
                  </tr>
                ))}
                {logs.length === 0 && (
                  <tr>
                    <td colSpan={5} className="py-8 text-center text-textSecondary">
                      No hay logs de auditoría
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
