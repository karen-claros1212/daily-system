'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { FormField } from '@/components/ui/field';
import { hasCapability } from '@/lib/rbac';
import {
  fetchCreditos,
  fetchResumenCreditos,
  fetchRutas,
  fetchClientes,
  crearCredito,
  type CreditoListItem,
  type CreditoResumen,
  type CreditoSort,
  type CreditoCreateInput,
} from '@/lib/api/client';

const money = new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 0 });

const ESTADO_LABELS: Record<string, { label: string; tone: 'success' | 'warning' | 'danger' | 'neutral' }> = {
  ACTIVO: { label: 'Activo', tone: 'success' },
  PAGADO: { label: 'Pagado', tone: 'neutral' },
  REFINANCIADO: { label: 'Refinanciado', tone: 'warning' },
  CANCELADO: { label: 'Cancelado', tone: 'danger' },
};

const SORT_OPTIONS: { value: CreditoSort; label: string }[] = [
  { value: 'fecha_inicio', label: 'Fecha de inicio' },
  { value: 'saldo', label: 'Saldo' },
  { value: 'monto', label: 'Monto' },
  { value: 'total', label: 'Total' },
  { value: 'cuota', label: 'Cuota' },
  { value: 'periodicidad', label: 'Periodicidad' },
  { value: 'estado', label: 'Estado' },
];

const EMPTY_CREATE: CreditoCreateInput = {
  cliente_id: '' as unknown as CreditoCreateInput['cliente_id'],
  ruta_id: '' as unknown as CreditoCreateInput['ruta_id'],
  cuota: 0,
  n_cuotas: 0,
  monto: 0,
  fecha_inicio: new Date().toISOString().slice(0, 10),
  periodicidad: 'DIARIO',
};

function estadoBadge(estado: string) {
  const meta = ESTADO_LABELS[estado] ?? { label: estado, tone: 'neutral' as const };
  return <Badge tone={meta.tone}>{meta.label}</Badge>;
}

export function CreditosPage({ session }: { session: import("@/lib/rbac").SessionUser | null }) {
  const canManage = hasCapability(session, 'creditos:gestionar');
  const canCliente360 = hasCapability(session, 'clientes:ver');
  const esCobrador = session?.rol === 'COBRADOR';

  const [page, setPage] = useState<{ items: CreditoListItem[]; total: number }>({ items: [], total: 0 });
  const [resumen, setResumen] = useState<CreditoResumen | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchInput, setSearchInput] = useState('');
  const [search, setSearch] = useState('');
  const [estadoFilter, setEstadoFilter] = useState('');
  const [rutaFilter, setRutaFilter] = useState('');
  const [rutas, setRutas] = useState<{ id: string; nombre: string }[]>([]);
  const [sort, setSort] = useState<CreditoSort>('fecha_inicio');
  const [order, setOrder] = useState<'asc' | 'desc'>('desc');
  const [offset, setOffset] = useState(0);
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState<CreditoCreateInput>(EMPTY_CREATE);
  const [clienteSearch, setClienteSearch] = useState('');
  const [clienteResults, setClienteResults] = useState<{ id: string; nombre: string }[]>([]);
  const [clienteBusy, setClienteBusy] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  const LIMIT = 25;

  useEffect(() => {
    let ignore = false;

    async function load() {
      try {
        setLoading(true);
        setError(null);
        const data = await fetchCreditos({
          q: search || undefined,
          estado: estadoFilter || undefined,
          ruta_id: rutaFilter || undefined,
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
          setError('Error al cargar créditos');
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
  }, [search, estadoFilter, rutaFilter, offset, sort, order, refreshKey]);

  useEffect(() => {
    let ignore = false;

    async function loadResumen() {
      try {
        const data = await fetchResumenCreditos();
        if (!ignore) setResumen(data);
      } catch {
        // El resumen es best-effort; la tabla sigue siendo la fuente de verdad.
      }
    }

    void loadResumen();

    return () => {
      ignore = true;
    };
  }, [refreshKey]);

  useEffect(() => {
    let ignore = false;

    async function loadRutas() {
      try {
        const data = await fetchRutas();
        if (!ignore) {
          setRutas(data.map((r) => ({ id: r.id, nombre: r.nombre })));
        }
      } catch {
        // Sin rutas no hay filtro por ruta; la lista sigue disponible.
      }
    }

    if (!esCobrador) void loadRutas();

    return () => {
      ignore = true;
    };
  }, [esCobrador]);

  function refresh() {
    setRefreshKey((k) => k + 1);
  }

  function handleSearchSubmit(e: React.FormEvent) {
    e.preventDefault();
    setOffset(0);
    setSearch(searchInput.trim());
  }

  async function handleBuscarCliente(e: React.FormEvent) {
    e.preventDefault();
    setClienteBusy(true);
    try {
      const data = await fetchClientes({ q: clienteSearch.trim() || undefined, limit: 10 });
      setClienteResults(data.items.map((c) => ({ id: c.id, nombre: [c.primer_apellido, c.nombres].filter(Boolean).join(' ').trim() })));
    } catch {
      setClienteResults([]);
    } finally {
      setClienteBusy(false);
    }
  }

  function seleccionarCliente(id: string, nombre: string) {
    setFormData({ ...formData, cliente_id: id as unknown as CreditoCreateInput['cliente_id'] });
    setClienteSearch(nombre);
    setClienteResults([]);
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const payload: CreditoCreateInput = {
      cliente_id: formData.cliente_id,
      ruta_id: formData.ruta_id,
      cuota: formData.cuota,
      n_cuotas: formData.n_cuotas,
      monto: formData.monto,
      fecha_inicio: formData.fecha_inicio,
      periodicidad: formData.periodicidad,
    };
    try {
      await crearCredito(payload);
      setFormData({ ...EMPTY_CREATE, fecha_inicio: new Date().toISOString().slice(0, 10) });
      setClienteSearch('');
      setShowForm(false);
      setOffset(0);
      refresh();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Error al crear crédito');
    }
  }

  function setCreateField(field: keyof CreditoCreateInput, value: string | number) {
    setFormData((prev) => ({ ...prev, [field]: value }));
  }

  const total = page.total;
  const from = total === 0 ? 0 : offset + 1;
  const to = Math.min(offset + page.items.length, total);
  const totalPreview = formData.cuota * formData.n_cuotas;

  return (
    <div className="space-y-6" role="main" aria-label="Créditos">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-textPrimary">Créditos</h1>
        {canManage && (
          <Button onClick={() => { setShowForm(!showForm); }} variant="primary" aria-expanded={showForm}>
            {showForm ? 'Cancelar' : 'Nuevo Crédito'}
          </Button>
        )}
      </div>

      {error && (
        <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-500 text-sm" role="alert">
          {error}
        </div>
      )}

      {/* Resumen superior: agregados calculados SOLO en el backend
          (hoja_viva_service.resumen_creditos); el panel no deriva financiero. */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4" aria-label="Resumen de cartera">
        <Card elevated>
          <div className="text-sm text-textSecondary">Total créditos</div>
          <div className="text-2xl font-bold text-textPrimary">{resumen?.total_creditos ?? '—'}</div>
        </Card>
        <Card elevated>
          <div className="text-sm text-textSecondary">Activos</div>
          <div className="text-2xl font-bold text-textPrimary">{resumen?.activos ?? '—'}</div>
        </Card>
        <Card elevated>
          <div className="text-sm text-textSecondary">Saldo de cartera</div>
          <div className="text-2xl font-bold text-textPrimary">
            {resumen ? money.format(resumen.saldo_total_cartera) : '—'}
          </div>
        </Card>
        <Card elevated>
          <div className="text-sm text-textSecondary">En mora</div>
          <div className="text-2xl font-bold text-textPrimary">{resumen?.en_mora ?? '—'}</div>
        </Card>
      </div>

      {showForm && canManage && (
        <Card elevated>
          <div className="font-bold text-lg mb-4">Nuevo Crédito</div>
          <form onSubmit={handleCreate} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <FormField id="nuevo-credito-cliente" label="Cliente" messageTone="hint">
                <div className="flex gap-2">
                  <Input
                    id="nuevo-credito-cliente"
                    value={clienteSearch}
                    onChange={(e) => setClienteSearch(e.target.value)}
                    placeholder="Buscar cliente por nombre…"
                    aria-label="Buscar cliente"
                  />
                  <Button type="button" variant="outline" onClick={handleBuscarCliente} disabled={clienteBusy}>
                    {clienteBusy ? '…' : 'Buscar'}
                  </Button>
                </div>
                {clienteResults.length > 0 && (
                  <ul className="mt-2 border border-outline rounded-lg divide-y divide-outline/50" aria-label="Resultados de clientes">
                    {clienteResults.map((c) => (
                      <li key={c.id}>
                        <button
                          type="button"
                          onClick={() => seleccionarCliente(c.id, c.nombre)}
                          className="w-full text-left px-3 py-2 text-sm text-textPrimary hover:bg-primary/10"
                          aria-label={`Seleccionar ${c.nombre}`}
                        >
                          {c.nombre}
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </FormField>
              <FormField id="nuevo-credito-ruta" label="Ruta" messageTone="hint">
                <select
                  id="nuevo-credito-ruta"
                  value={typeof formData.ruta_id === 'string' ? formData.ruta_id : ''}
                  onChange={(e) => setCreateField('ruta_id', e.target.value)}
                  className="w-full px-3 py-2 border border-outline rounded-lg bg-surface text-textPrimary"
                  aria-label="Ruta del crédito"
                  required
                >
                  <option value="">Seleccionar…</option>
                  {rutas.map((r) => (
                    <option key={r.id} value={r.id}>{r.nombre}</option>
                  ))}
                </select>
              </FormField>
              <FormField id="nuevo-credito-cuota" label="Cuota (COP)" messageTone="hint">
                <Input
                  id="nuevo-credito-cuota"
                  type="number"
                  min={1}
                  value={formData.cuota || ''}
                  onChange={(e) => setCreateField('cuota', Number(e.target.value))}
                  placeholder="Valor de la cuota"
                  required
                />
              </FormField>
              <FormField id="nuevo-credito-cuotas" label="N.º de cuotas" messageTone="hint">
                <Input
                  id="nuevo-credito-cuotas"
                  type="number"
                  min={1}
                  value={formData.n_cuotas || ''}
                  onChange={(e) => setCreateField('n_cuotas', Number(e.target.value))}
                  placeholder="Cantidad de cuotas"
                  required
                />
              </FormField>
              <FormField id="nuevo-credito-monto" label="Monto (COP)" messageTone="hint">
                <Input
                  id="nuevo-credito-monto"
                  type="number"
                  min={1}
                  value={formData.monto || ''}
                  onChange={(e) => setCreateField('monto', Number(e.target.value))}
                  placeholder="Monto desembolsado"
                  required
                />
              </FormField>
              <FormField id="nuevo-credito-fecha" label="Fecha de inicio" messageTone="hint">
                <Input
                  id="nuevo-credito-fecha"
                  type="date"
                  value={formData.fecha_inicio}
                  onChange={(e) => setCreateField('fecha_inicio', e.target.value)}
                  required
                />
              </FormField>
              <FormField id="nuevo-credito-periodicidad" label="Periodicidad" messageTone="hint">
                <select
                  id="nuevo-credito-periodicidad"
                  value={formData.periodicidad}
                  onChange={(e) => setCreateField('periodicidad', e.target.value)}
                  className="w-full px-3 py-2 border border-outline rounded-lg bg-surface text-textPrimary"
                  aria-label="Periodicidad del crédito"
                >
                  <option value="DIARIO">Diaria</option>
                  <option value="SEMANAL">Semanal</option>
                  <option value="QUINCENAL">Quincenal</option>
                  <option value="UNICA">Única</option>
                </select>
              </FormField>
            </div>
            {totalPreview > 0 && (
              <p className="text-sm text-textSecondary">
                Total estimado (cuota × cuotas): <span className="font-semibold text-textPrimary">{money.format(totalPreview)}</span> — el total final lo calcula el backend.
              </p>
            )}
            <Button type="submit" variant="primary">Crear Crédito</Button>
          </form>
        </Card>
      )}

      <Card elevated>
        <div className="font-bold text-lg mb-4">Filtros</div>
        <form onSubmit={handleSearchSubmit} className="flex flex-wrap gap-4">
          <div className="flex-1 min-w-[220px]">
            <label htmlFor="searchCreditos" className="block text-sm text-textSecondary mb-1">Buscar</label>
            <Input
              id="searchCreditos"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Cliente…"
            />
          </div>
          <div className="flex-1 min-w-[140px]">
            <label htmlFor="filterEstado" className="block text-sm text-textSecondary mb-1">Estado</label>
            <select
              id="filterEstado"
              value={estadoFilter}
              onChange={(e) => { setEstadoFilter(e.target.value); setOffset(0); }}
              className="w-full px-3 py-2 border border-outline rounded-lg bg-surface text-textPrimary"
              aria-label="Filtrar por estado"
            >
              <option value="">Todos</option>
              <option value="ACTIVO">Activos</option>
              <option value="PAGADO">Pagados</option>
              <option value="REFINANCIADO">Refinanciados</option>
              <option value="CANCELADO">Cancelados</option>
            </select>
          </div>
          {!esCobrador && (
            <div className="flex-1 min-w-[140px]">
              <label htmlFor="filterRuta" className="block text-sm text-textSecondary mb-1">Ruta</label>
              <select
                id="filterRuta"
                value={rutaFilter}
                onChange={(e) => { setRutaFilter(e.target.value); setOffset(0); }}
                className="w-full px-3 py-2 border border-outline rounded-lg bg-surface text-textPrimary"
                aria-label="Filtrar por ruta"
              >
                <option value="">Todas</option>
                {rutas.map((r) => (
                  <option key={r.id} value={r.id}>{r.nombre}</option>
                ))}
              </select>
            </div>
          )}
          <div className="flex-1 min-w-[140px]">
            <label htmlFor="sortCreditos" className="block text-sm text-textSecondary mb-1">Ordenar por</label>
            <select
              id="sortCreditos"
              value={sort}
              onChange={(e) => { setSort(e.target.value as CreditoSort); setOffset(0); }}
              className="w-full px-3 py-2 border border-outline rounded-lg bg-surface text-textPrimary"
              aria-label="Ordenar créditos por"
            >
              {SORT_OPTIONS.map((s) => (
                <option key={s.value} value={s.value}>{s.label}</option>
              ))}
            </select>
          </div>
          <div className="flex-1 min-w-[140px]">
            <label htmlFor="orderCreditos" className="block text-sm text-textSecondary mb-1">Dirección</label>
            <select
              id="orderCreditos"
              value={order}
              onChange={(e) => { setOrder(e.target.value as 'asc' | 'desc'); setOffset(0); }}
              className="w-full px-3 py-2 border border-outline rounded-lg bg-surface text-textPrimary"
              aria-label="Dirección del orden"
            >
              <option value="desc">Descendente</option>
              <option value="asc">Ascendente</option>
            </select>
          </div>
          <div className="flex items-end gap-2">
            <Button type="submit" variant="primary">Buscar</Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => { setSearchInput(''); setSearch(''); setEstadoFilter(''); setRutaFilter(''); setOffset(0); }}
            >
              Limpiar
            </Button>
          </div>
        </form>
      </Card>

      {loading ? (
        <Card elevated>
          <div className="text-center py-8 text-textSecondary" role="status" aria-label="Cargando créditos">
            <div className="animate-pulse">Cargando créditos...</div>
          </div>
        </Card>
      ) : (
        <Card elevated>
          <div className="font-bold text-lg mb-4">Créditos ({total})</div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm" role="table" aria-label="Lista de créditos">
              <thead>
                <tr className="border-b border-outline">
                  <th className="text-left py-3 px-4 text-textSecondary font-medium" scope="col">Cliente</th>
                  <th className="text-left py-3 px-4 text-textSecondary font-medium" scope="col">Ruta</th>
                  <th className="text-left py-3 px-4 text-textSecondary font-medium" scope="col">Estado</th>
                  <th className="text-left py-3 px-4 text-textSecondary font-medium" scope="col">Cuota</th>
                  <th className="text-left py-3 px-4 text-textSecondary font-medium" scope="col">Saldo</th>
                  <th className="text-left py-3 px-4 text-textSecondary font-medium" scope="col">Mora</th>
                  <th className="text-left py-3 px-4 text-textSecondary font-medium" scope="col">Cuotas</th>
                  <th className="text-left py-3 px-4 text-textSecondary font-medium" scope="col">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {page.items.map((c) => (
                  <tr key={c.id} className="border-b border-outline/50">
                    <td className="py-3 px-4">
                      {canCliente360 && c.cliente_id ? (
                        <Link
                          href={`/clientes/${c.cliente_id}`}
                          className="text-textPrimary hover:text-primary focus:outline-none focus:ring-2 focus:ring-primary/50 rounded"
                          aria-label={`Ver Cliente 360 de ${c.cliente_nombre ?? 'cliente'}`}
                        >
                          {c.cliente_nombre ?? '—'}
                        </Link>
                      ) : (
                        <span className="text-textPrimary">{c.cliente_nombre ?? '—'}</span>
                      )}
                    </td>
                    <td className="py-3 px-4 text-textSecondary">{c.ruta_nombre || '—'}</td>
                    <td className="py-3 px-4">{estadoBadge(c.estado)}</td>
                    <td className="py-3 px-4 text-textSecondary">{money.format(c.cuota)}</td>
                    <td className="py-3 px-4 text-textPrimary font-medium">{money.format(c.saldo)}</td>
                    <td className="py-3 px-4 text-textSecondary">{c.mora > 0 ? `${c.mora} días` : '—'}</td>
                    <td className="py-3 px-4 text-textSecondary">{c.cuotas_pagadas}/{c.n_cuotas}</td>
                    <td className="py-3 px-4">
                      <Link
                        href={`/creditos/${c.id}`}
                        className="btn btn-outline btn-sm"
                        aria-label={`Ver detalle del crédito${c.cliente_nombre ? ' de ' + c.cliente_nombre : ''}`}
                      >
                        Ver
                      </Link>
                    </td>
                  </tr>
                ))}
                {page.items.length === 0 && !loading && (
                  <tr>
                    <td colSpan={8} className="py-8 text-center text-textSecondary" aria-label="No hay créditos">
                      {search || estadoFilter || rutaFilter
                        ? 'No hay créditos con los filtros aplicados'
                        : 'No hay créditos registrados'}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          {total > LIMIT && (
            <div className="flex items-center justify-between mt-4 px-4 pb-4">
              <span className="text-sm text-textSecondary">
                Mostrando {from}–{to} de {total}
              </span>
              <div className="flex gap-2">
                <Button size="sm" variant="outline" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - LIMIT))}>
                  Anterior
                </Button>
                <Button size="sm" variant="outline" disabled={to >= total} onClick={() => setOffset(offset + LIMIT)}>
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
