'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { Card } from '@/components/ui/card';
import { Button, LoadingState } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { FormField } from '@/components/ui/field';
import { hasCapability } from '@/lib/rbac';
import {
  fetchRutas,
  fetchResumenRutas,
  fetchUsuarios,
  crearRuta,
  type RutaListItem,
  type RutaResumen,
  type RutaSort,
  type RutaCreateInput,
} from '@/lib/api/client';

const SORT_OPTIONS: { value: RutaSort; label: string }[] = [
  { value: 'creado_el', label: 'Fecha de creación' },
  { value: 'nombre', label: 'Nombre' },
  { value: 'version', label: 'Versión' },
];

function estadoBadge(activa: number) {
  return (
    <Badge tone={activa === 1 ? 'success' : 'warning'}>{activa === 1 ? 'Activa' : 'Inactiva'}</Badge>
  );
}

export function Routes({ session }: { session: import('@/lib/rbac').SessionUser | null }) {
  const canManage = hasCapability(session, 'rutas:crear');
  const esCobrador = session?.rol === 'COBRADOR';

  const [page, setPage] = useState<{ items: RutaListItem[]; total: number }>({ items: [], total: 0 });
  const [resumen, setResumen] = useState<RutaResumen | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchInput, setSearchInput] = useState('');
  const [search, setSearch] = useState('');
  const [activaFilter, setActivaFilter] = useState('');
  const [sort, setSort] = useState<RutaSort>('creado_el');
  const [order, setOrder] = useState<'asc' | 'desc'>('desc');
  const [offset, setOffset] = useState(0);
  const [refreshKey, setRefreshKey] = useState(0);
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState<RutaCreateInput>({ nombre: '', cobrador_id: null });
  const [cobradores, setCobradores] = useState<{ id: string; nombre: string }[]>([]);

  const LIMIT = 25;

  useEffect(() => {
    let ignore = false;

    async function load() {
      try {
        setLoading(true);
        setError(null);
        const data = await fetchRutas({
          q: search || undefined,
          activa: activaFilter === '' ? undefined : Number(activaFilter),
          limit: LIMIT,
          offset,
          sort,
          order,
        });
        if (!ignore) {
          setPage({ items: data.items, total: data.total });
        }
      } catch {
        if (!ignore) {
          setError('Error al cargar rutas');
        }
      } finally {
        if (!ignore) {
          setLoading(false);
        }
      }
    }

    void load();

    return () => {
      ignore = true;
    };
  }, [search, activaFilter, offset, sort, order, refreshKey]);

  useEffect(() => {
    let ignore = false;

    async function loadResumen() {
      try {
        const data = await fetchResumenRutas();
        if (!ignore) setResumen(data);
      } catch {
        // Best-effort: la tabla sigue siendo la fuente de verdad.
      }
    }

    void loadResumen();

    return () => {
      ignore = true;
    };
  }, [refreshKey]);

  useEffect(() => {
    let ignore = false;

    async function loadCobradores() {
      try {
        const data = await fetchUsuarios({ rol: 'COBRADOR', activo: '1' });
        if (!ignore) {
          setCobradores(data.map((u) => ({ id: u.id, nombre: u.nombre })));
        }
      } catch {
        // Sin lista de cobradores el select queda vacío; nombre sigue funcionando.
      }
    }

    if (canManage) void loadCobradores();

    return () => {
      ignore = true;
    };
  }, [canManage]);

  function refresh() {
    setRefreshKey((k) => k + 1);
  }

  function handleSearchSubmit(e: React.FormEvent) {
    e.preventDefault();
    setOffset(0);
    setSearch(searchInput.trim());
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const payload: RutaCreateInput = {
      nombre: formData.nombre.trim(),
      cobrador_id: formData.cobrador_id || null,
    };
    try {
      await crearRuta(payload);
      setFormData({ nombre: '', cobrador_id: null });
      setShowForm(false);
      setOffset(0);
      refresh();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Error al crear ruta');
    }
  }

  const totalPages = Math.max(1, Math.ceil(page.total / LIMIT));
  const currentPage = Math.floor(offset / LIMIT) + 1;

  return (
    <div className="space-y-6" role="main" aria-label="Gestión de Rutas">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-textPrimary">Rutas</h1>
        {canManage && (
          <Button
            variant="primary"
            onClick={() => {
              setShowForm(!showForm);
              setError(null);
            }}
            aria-expanded={showForm}
          >
            {showForm ? 'Cancelar' : 'Nueva ruta'}
          </Button>
        )}
      </div>

      {resumen && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <MetricTile label="Total rutas" value={String(resumen.total_rutas)} />
          <MetricTile label="Activas" value={String(resumen.activas)} tone="success" />
          <MetricTile label="Inactivas" value={String(resumen.inactivas)} tone="warning" />
        </div>
      )}

      {error && (
        <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-500 text-sm" role="alert">
          {error}
        </div>
      )}

      {showForm && (
        <Card elevated>
          <div className="font-bold text-lg mb-4">Nueva ruta</div>
          <form onSubmit={handleCreate} className="space-y-4">
            <FormField id="ruta-nombre" label="Nombre de la ruta" messageTone="hint">
              <Input
                id="ruta-nombre"
                value={formData.nombre}
                onChange={(e) => setFormData({ ...formData, nombre: e.target.value })}
                placeholder="p. ej. Ruta Centro"
                required
                maxLength={100}
                autoFocus
              />
            </FormField>
            <FormField id="ruta-cobrador" label="Cobrador asignado (opcional)" messageTone="hint">
              <select
                id="ruta-cobrador"
                value={formData.cobrador_id ?? ''}
                onChange={(e) =>
                  setFormData({ ...formData, cobrador_id: e.target.value || null })
                }
                className="w-full px-3 py-2 border border-outline rounded-lg bg-surface text-textPrimary"
                aria-label="Seleccionar cobrador"
              >
                <option value="">Sin cobrador</option>
                {cobradores.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.nombre}
                  </option>
                ))}
              </select>
            </FormField>
            <div className="flex gap-2">
              <Button type="submit" variant="primary">
                Crear ruta
              </Button>
              <Button type="button" variant="outline" onClick={() => setShowForm(false)}>
                Cancelar
              </Button>
            </div>
          </form>
        </Card>
      )}

      {!esCobrador && (
        <div className="flex flex-wrap items-center gap-2">
          <form onSubmit={handleSearchSubmit} className="flex items-center gap-2">
            <Input
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Buscar por nombre…"
              className="w-64"
              aria-label="Buscar rutas"
            />
            <Button type="submit" variant="outline" size="sm">
              Buscar
            </Button>
          </form>
          <select
            value={activaFilter}
            onChange={(e) => {
              setActivaFilter(e.target.value);
              setOffset(0);
            }}
            className="px-3 py-2 border border-outline rounded-lg bg-surface text-textPrimary text-sm"
            aria-label="Filtrar por estado"
          >
            <option value="">Todos los estados</option>
            <option value="1">Activas</option>
            <option value="0">Inactivas</option>
          </select>
          <select
            value={sort}
            onChange={(e) => {
              setSort(e.target.value as RutaSort);
              setOffset(0);
            }}
            className="px-3 py-2 border border-outline rounded-lg bg-surface text-textPrimary text-sm"
            aria-label="Ordenar por"
          >
            {SORT_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                Ordenar: {o.label}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={() => setOrder(order === 'desc' ? 'asc' : 'desc')}
            className="px-3 py-2 border border-outline rounded-lg bg-surface text-textPrimary text-sm"
            aria-label="Cambiar dirección de orden"
          >
            {order === 'desc' ? '↓ Descendente' : '↑ Ascendente'}
          </button>
        </div>
      )}

      {loading ? (
        <LoadingState />
      ) : (
        <Card className="p-0 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="table">
              <thead>
                <tr>
                  <th>Ruta</th>
                  <th>Cobrador</th>
                  <th>Estado</th>
                  <th>Versión</th>
                  <th className="text-right">Acción</th>
                </tr>
              </thead>
              <tbody>
                {page.items.map((route) => (
                  <tr key={route.ruta_id}>
                    <td className="font-medium text-textPrimary">{route.nombre}</td>
                    <td>{route.cobrador_nombre ?? '—'}</td>
                    <td>{estadoBadge(route.activa)}</td>
                    <td>{route.version}</td>
                    <td className="text-right">
                      <Link href={`/routes/${route.ruta_id}`}>
                        <Button variant="outline" size="sm">
                          Ver detalle
                        </Button>
                      </Link>
                    </td>
                  </tr>
                ))}
                {page.items.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-4 py-8 text-center text-textSecondary">
                      No hay rutas registradas.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {totalPages > 1 && (
            <div className="flex items-center justify-between px-4 py-3 border-t border-outline">
              <span className="text-sm text-textSecondary">
                Página {currentPage} de {totalPages} · {page.total} rutas
              </span>
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
        </Card>
      )}
    </div>
  );
}

function MetricTile({
  label,
  value,
  tone = 'neutral',
}: {
  label: string;
  value: string;
  tone?: 'neutral' | 'success' | 'warning';
}) {
  const toneClass =
    tone === 'success' ? 'text-success' : tone === 'warning' ? 'text-warning' : 'text-textPrimary';
  return (
    <div className="bg-surface border border-outline rounded-xl p-4">
      <div className="text-sm text-textSecondary">{label}</div>
      <div className={`text-2xl font-bold ${toneClass}`}>{value}</div>
    </div>
  );
}
