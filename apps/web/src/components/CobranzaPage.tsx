'use client';

import { useState, useEffect } from 'react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { FormField } from '@/components/ui/field';
import {
  fetchCobranza,
  fetchCobranzaResumen,
  type CobranzaItem,
  type CobranzaListPage,
  type CobranzaResumen,
  type CobranzaSort,
} from '@/lib/api/client';

const money = new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 0 });

const BUCKET_LABELS: Record<string, string> = {
  CURRENT: 'Al día',
  '1-7': '1-7 días',
  '8-15': '8-15 días',
  '16-30': '16-30 días',
  '31-60': '31-60 días',
  '61-90': '61-90 días',
  '90+': '90+ días',
};

const PRIORITY_TONES: Record<string, 'success' | 'warning' | 'danger' | 'neutral'> = {
  high: 'danger',
  medium: 'warning',
  low: 'neutral',
};

export function CobranzaPage({ session: _session }: { session: import("@/lib/rbac").SessionUser | null }) {
  void _session;
  const [page, setPage] = useState<CobranzaListPage>({ items: [], total: 0, limit: 25, offset: 0 });
  const [resumen, setResumen] = useState<CobranzaResumen | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchInput, setSearchInput] = useState('');
  const [search, setSearch] = useState('');
  const [bucketFilter, setBucketFilter] = useState('');
  const [priorityFilter, setPriorityFilter] = useState('');
  const [sort, setSort] = useState<CobranzaSort>('days_past_due');
  const [order, setOrder] = useState<'asc' | 'desc'>('desc');
  const [offset, setOffset] = useState(0);
  const [refreshKey, setRefreshKey] = useState(0);

  const LIMIT = 25;

  useEffect(() => {
    let ignore = false;
    async function load() {
      try {
        setLoading(true);
        setError(null);
        const [data, res] = await Promise.all([
          fetchCobranza({
            q: search || undefined,
            bucket: bucketFilter || undefined,
            priority: priorityFilter || undefined,
            limit: LIMIT,
            offset,
            sort,
            order,
          }),
          fetchCobranzaResumen(),
        ]);
        if (!ignore) {
          setPage(data);
          setResumen(res);
        }
      } catch (e) {
        if (!ignore) setError(e instanceof Error ? e.message : 'Error cargando cobranza');
      } finally {
        if (!ignore) setLoading(false);
      }
    }
    load();
    return () => { ignore = true; };
  }, [search, bucketFilter, priorityFilter, offset, sort, order, refreshKey]);

  const totalPages = Math.ceil(page.total / LIMIT);
  const currentPage = Math.floor(offset / LIMIT) + 1;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Centro de Cobranza</h1>
        <Button variant="outline" onClick={() => setRefreshKey((k) => k + 1)}>
          Actualizar
        </Button>
      </div>

      {resumen && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Card className="p-4">
            <p className="text-sm text-muted-foreground">Cartera total</p>
            <p className="text-2xl font-bold">{money.format(resumen.total_cartera)}</p>
          </Card>
          <Card className="p-4">
            <p className="text-sm text-muted-foreground">Cartera vencida</p>
            <p className="text-2xl font-bold text-red-600">{money.format(resumen.total_vencido)}</p>
            <p className="text-xs text-muted-foreground">{resumen.pct_vencido}% de la cartera</p>
          </Card>
          <Card className="p-4">
            <p className="text-sm text-muted-foreground">Clientes en mora</p>
            <p className="text-2xl font-bold">{resumen.clientes_en_mora}</p>
          </Card>
          <Card className="p-4">
            <p className="text-sm text-muted-foreground">Promesas activas</p>
            <p className="text-2xl font-bold">{resumen.promesas_activas}</p>
            {resumen.promesas_incumplidas > 0 && (
              <p className="text-xs text-red-600">{resumen.promesas_incumplidas} incumplidas</p>
            )}
          </Card>
        </div>
      )}

      {resumen && (
        <Card className="p-4">
          <h2 className="text-lg font-semibold mb-3">Aging Distribution</h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2">
            {Object.entries(resumen.aging_distribution).map(([bucket, data]) => (
              <div key={bucket} className="text-center p-2 rounded bg-muted/30">
                <p className="text-xs text-muted-foreground">{BUCKET_LABELS[bucket] ?? bucket}</p>
                <p className="text-lg font-bold">{data.count}</p>
                {data.amount > 0 && (
                  <p className="text-xs text-red-600">{money.format(data.amount)}</p>
                )}
              </div>
            ))}
          </div>
        </Card>
      )}

      <Card className="p-4">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <FormField id="cob-search" label="Buscar cliente">
            <Input
              id="cob-search"
              placeholder="Nombre..."
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') { setSearch(searchInput); setOffset(0); } }}
            />
          </FormField>
          <FormField id="cob-bucket" label="Bucket aging">
            <select
              id="cob-bucket"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={bucketFilter}
              onChange={(e) => { setBucketFilter(e.target.value); setOffset(0); }}
            >
              <option value="">Todos</option>
              {Object.entries(BUCKET_LABELS).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
          </FormField>
          <FormField id="cob-priority" label="Prioridad">
            <select
              id="cob-priority"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={priorityFilter}
              onChange={(e) => { setPriorityFilter(e.target.value); setOffset(0); }}
            >
              <option value="">Todas</option>
              <option value="high">Alta</option>
              <option value="medium">Media</option>
              <option value="low">Baja</option>
            </select>
          </FormField>
          <FormField id="cob-sort" label="Ordenar por">
            <select
              id="cob-sort"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={sort}
              onChange={(e) => setSort(e.target.value as CobranzaSort)}
            >
              <option value="days_past_due">Días de mora</option>
              <option value="overdue_amount">Monto vencido</option>
              <option value="total_outstanding">Saldo total</option>
              <option value="priority_score">Prioridad</option>
              <option value="cliente_nombre">Cliente</option>
            </select>
          </FormField>
        </div>
      </Card>

      {error && <Card className="p-4 text-red-600">{error}</Card>}

      <Card>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="px-4 py-3 text-left font-medium">Cliente</th>
                <th className="px-4 py-3 text-left font-medium">Ruta</th>
                <th className="px-4 py-3 text-right font-medium">Saldo</th>
                <th className="px-4 py-3 text-right font-medium">Vencido</th>
                <th className="px-4 py-3 text-right font-medium">Días</th>
                <th className="px-4 py-3 text-left font-medium">Bucket</th>
                <th className="px-4 py-3 text-left font-medium">Prioridad</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={7} className="px-4 py-8 text-center text-muted-foreground">Cargando...</td></tr>
              ) : page.items.length === 0 ? (
                <tr><td colSpan={7} className="px-4 py-8 text-center text-muted-foreground">Sin créditos en cobranza</td></tr>
              ) : (
                page.items.map((item) => (
                  <tr key={item.credito_id} className="border-b last:border-0 hover:bg-muted/30">
                    <td className="px-4 py-3">{item.cliente_nombre || '—'}</td>
                    <td className="px-4 py-3">{item.ruta_nombre || '—'}</td>
                    <td className="px-4 py-3 text-right font-mono">{money.format(item.saldo)}</td>
                    <td className="px-4 py-3 text-right font-mono text-red-600">{money.format(item.overdue_amount)}</td>
                    <td className="px-4 py-3 text-right">{item.days_past_due}</td>
                    <td className="px-4 py-3">
                      <Badge tone={item.days_past_due > 30 ? 'danger' : item.days_past_due > 0 ? 'warning' : 'neutral'}>
                        {item.aging_bucket}
                      </Badge>
                    </td>
                    <td className="px-4 py-3">
                      <Badge tone={PRIORITY_TONES[item.priority] ?? 'neutral'}>
                        {item.priority} ({item.priority_score})
                      </Badge>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Card>

      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            Página {currentPage} de {totalPages} ({page.total} créditos)
          </p>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - LIMIT))}>
              Anterior
            </Button>
            <Button variant="outline" size="sm" disabled={offset + LIMIT >= page.total} onClick={() => setOffset(offset + LIMIT)}>
              Siguiente
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
