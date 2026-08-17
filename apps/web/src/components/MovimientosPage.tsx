'use client';

import { useState, useEffect } from 'react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { FormField } from '@/components/ui/field';
import {
  fetchMovimientos,
  fetchMovimientosResumen,
  fetchRutas,
  type MovimientoListPage,
  type MovimientoResumen,
  type MovimientoSort,
} from '@/lib/api/client';

const money = new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 0 });

const NATURALEZA_LABELS: Record<string, { label: string; tone: 'success' | 'warning' | 'danger' | 'neutral' }> = {
  GASTO: { label: 'Gasto', tone: 'danger' },
  INGRESO: { label: 'Ingreso', tone: 'success' },
  CUENTA_POR_COBRAR: { label: 'C/Pagar', tone: 'warning' },
  AJUSTE: { label: 'Ajuste', tone: 'neutral' },
  TRANSFERENCIA: { label: 'Transferencia', tone: 'neutral' },
  OTRA: { label: 'Otra', tone: 'neutral' },
};

const SORT_OPTIONS: { value: MovimientoSort; label: string }[] = [
  { value: 'creado_el', label: 'Fecha' },
  { value: 'monto', label: 'Monto' },
  { value: 'tipo', label: 'Tipo' },
];

function naturalezaBadge(naturaleza: string) {
  const meta = NATURALEZA_LABELS[naturaleza] ?? { label: naturaleza, tone: 'neutral' as const };
  return <Badge tone={meta.tone}>{meta.label}</Badge>;
}

export function MovimientosPage({ session: _session }: { session: import("@/lib/rbac").SessionUser | null }) {
  void _session;
  const [page, setPage] = useState<MovimientoListPage>({ items: [], total: 0, limit: 25, offset: 0 });
  const [resumen, setResumen] = useState<MovimientoResumen | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchInput, setSearchInput] = useState('');
  const [search, setSearch] = useState('');
  const [naturalezaFilter, setNaturalezaFilter] = useState('');
  const [rutaFilter, setRutaFilter] = useState('');
  const [rutas, setRutas] = useState<{ id: string; nombre: string }[]>([]);
  const [sort, setSort] = useState<MovimientoSort>('creado_el');
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
          fetchMovimientos({
            q: search || undefined,
            naturaleza: naturalezaFilter || undefined,
            ruta_id: rutaFilter || undefined,
            limit: LIMIT,
            offset,
            sort,
            order,
          }),
          fetchMovimientosResumen(),
        ]);
        if (!ignore) {
          setPage(data);
          setResumen(res);
        }
      } catch (e) {
        if (!ignore) setError(e instanceof Error ? e.message : 'Error cargando movimientos');
      } finally {
        if (!ignore) setLoading(false);
      }
    }
    load();
    return () => { ignore = true; };
  }, [search, naturalezaFilter, rutaFilter, offset, sort, order, refreshKey]);

  useEffect(() => {
    fetchRutas({ limit: 100 }).then((r) => setRutas(r.items.map((r) => ({ id: r.ruta_id, nombre: r.nombre })))).catch(() => {});
  }, []);

  const totalPages = Math.ceil(page.total / LIMIT);
  const currentPage = Math.floor(offset / LIMIT) + 1;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Centro Financiero</h1>
        <Button variant="outline" onClick={() => setRefreshKey((k) => k + 1)}>
          Actualizar
        </Button>
      </div>

      {resumen && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Card className="p-4">
            <p className="text-sm text-muted-foreground">Total movimientos</p>
            <p className="text-2xl font-bold">{resumen.total_movimientos}</p>
          </Card>
          <Card className="p-4">
            <p className="text-sm text-muted-foreground">Total monto</p>
            <p className="text-2xl font-bold">{money.format(resumen.total_monto)}</p>
          </Card>
          {resumen.gastos_por_tipo.slice(0, 2).map((g) => (
            <Card key={g.tipo} className="p-4">
              <p className="text-sm text-muted-foreground">Gasto: {g.tipo}</p>
              <p className="text-2xl font-bold text-red-600">{money.format(g.total)}</p>
            </Card>
          ))}
        </div>
      )}

      <Card className="p-4">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          <FormField id="mov-search" label="Buscar">
            <Input
              id="mov-search"
              placeholder="Nota..."
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') { setSearch(searchInput); setOffset(0); } }}
            />
          </FormField>
          <FormField id="mov-naturaleza" label="Naturaleza">
            <select
              id="mov-naturaleza"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={naturalezaFilter}
              onChange={(e) => { setNaturalezaFilter(e.target.value); setOffset(0); }}
            >
              <option value="">Todas</option>
              {Object.entries(NATURALEZA_LABELS).map(([k, v]) => (
                <option key={k} value={k}>{v.label}</option>
              ))}
            </select>
          </FormField>
          <FormField id="mov-ruta" label="Ruta">
            <select
              id="mov-ruta"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={rutaFilter}
              onChange={(e) => { setRutaFilter(e.target.value); setOffset(0); }}
            >
              <option value="">Todas</option>
              {rutas.map((r) => (
                <option key={r.id} value={r.id}>{r.nombre}</option>
              ))}
            </select>
          </FormField>
          <FormField id="mov-sort" label="Ordenar por">
            <select
              id="mov-sort"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={sort}
              onChange={(e) => setSort(e.target.value as MovimientoSort)}
            >
              {SORT_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </FormField>
          <FormField id="mov-order" label="Dirección">
            <select
              id="mov-order"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={order}
              onChange={(e) => setOrder(e.target.value as 'asc' | 'desc')}
            >
              <option value="desc">Descendente</option>
              <option value="asc">Ascendente</option>
            </select>
          </FormField>
        </div>
      </Card>

      {error && (
        <Card className="p-4 text-red-600">
          {error}
        </Card>
      )}

      <Card>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="px-4 py-3 text-left font-medium">Fecha</th>
                <th className="px-4 py-3 text-left font-medium">Tipo</th>
                <th className="px-4 py-3 text-left font-medium">Naturaleza</th>
                <th className="px-4 py-3 text-right font-medium">Monto</th>
                <th className="px-4 py-3 text-left font-medium">Nota</th>
                <th className="px-4 py-3 text-left font-medium">Ruta</th>
                <th className="px-4 py-3 text-left font-medium">Registró</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={7} className="px-4 py-8 text-center text-muted-foreground">Cargando...</td></tr>
              ) : page.items.length === 0 ? (
                <tr><td colSpan={7} className="px-4 py-8 text-center text-muted-foreground">Sin movimientos</td></tr>
              ) : (
                page.items.map((m) => (
                  <tr key={m.id} className="border-b last:border-0 hover:bg-muted/30">
                    <td className="px-4 py-3 whitespace-nowrap">
                      {m.creado_el ? new Date(m.creado_el).toLocaleDateString('es-CO') : '—'}
                    </td>
                    <td className="px-4 py-3">{m.tipo}</td>
                    <td className="px-4 py-3">{naturalezaBadge(m.naturaleza)}</td>
                    <td className="px-4 py-3 text-right font-mono">{money.format(m.monto)}</td>
                    <td className="px-4 py-3 max-w-[200px] truncate">{m.nota || '—'}</td>
                    <td className="px-4 py-3">{m.ruta_nombre || '—'}</td>
                    <td className="px-4 py-3">{m.creado_por_nombre || '—'}</td>
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
            Página {currentPage} de {totalPages} ({page.total} movimientos)
          </p>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={offset === 0}
              onClick={() => setOffset(Math.max(0, offset - LIMIT))}
            >
              Anterior
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={offset + LIMIT >= page.total}
              onClick={() => setOffset(offset + LIMIT)}
            >
              Siguiente
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
