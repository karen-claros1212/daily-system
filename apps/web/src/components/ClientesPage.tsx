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
  fetchClientes,
  crearCliente,
  editarCliente,
  fetchCliente360,
  type ClienteList,
  type ClienteCreateInput,
  type ClienteUpdateInput,
} from '@/lib/api/client';

const IDENTITY_LABELS: Record<string, { label: string; tone: 'success' | 'warning' | 'danger' | 'neutral' }> = {
  VERIFIED: { label: 'Verificado', tone: 'success' },
  PROVISIONAL: { label: 'Provisional', tone: 'warning' },
  POSSIBLE_DUPLICATE: { label: 'Posible duplicado', tone: 'danger' },
};

const TIPO_DOCUMENTOS = ['CC', 'CE', 'TI', 'NIT', 'PASAPORTE'];

function identityBadge(status: string) {
  const meta = IDENTITY_LABELS[status] ?? { label: status, tone: 'neutral' as const };
  return <Badge tone={meta.tone}>{meta.label}</Badge>;
}

function nombreCompleto(c: { primer_apellido?: string | null; segundo_apellido?: string | null; nombres?: string | null }) {
  return [c.nombres, c.primer_apellido, c.segundo_apellido].filter(Boolean).join(' ').trim() || '—';
}

const EMPTY_CREATE: ClienteCreateInput = {
  primer_apellido: '',
  nombres: '',
  segundo_apellido: '',
  tipo_documento: '',
  documento_normalizado: '',
  telefono_1: '',
  telefono_2: '',
  direccion: '',
  barrio: '',
  ciudad: '',
  ocupacion: '',
};

export function ClientesPage({ session }: { session: import("@/lib/rbac").SessionUser | null }) {
  const canManage = hasCapability(session, 'clientes:gestionar');

  const [page, setPage] = useState<{ items: ClienteList[]; total: number }>({ items: [], total: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchInput, setSearchInput] = useState('');
  const [search, setSearch] = useState('');
  const [identityFilter, setIdentityFilter] = useState('');
  const [tipoDocFilter, setTipoDocFilter] = useState('');
  const [offset, setOffset] = useState(0);
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState<ClienteCreateInput>(EMPTY_CREATE);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editData, setEditData] = useState<ClienteUpdateInput | null>(null);
  const [editingLoading, setEditingLoading] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  const LIMIT = 25;

  useEffect(() => {
    let ignore = false;

    async function load() {
      try {
        setLoading(true);
        setError(null);
        const data = await fetchClientes({
          q: search || undefined,
          identity_status: identityFilter || undefined,
          tipo_documento: tipoDocFilter || undefined,
          limit: LIMIT,
          offset,
        });
        if (!ignore) {
          setPage({ items: data.items, total: data.total });
        }
      } catch {
        if (!ignore) {
          setError('Error al cargar clientes');
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
  }, [search, identityFilter, tipoDocFilter, offset, refreshKey]);

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
    const trim = (v: string | null | undefined): string | null => v?.trim() || null;
    const payload: ClienteCreateInput = {
      primer_apellido: formData.primer_apellido.trim(),
      nombres: formData.nombres.trim(),
      segundo_apellido: trim(formData.segundo_apellido),
      tipo_documento: trim(formData.tipo_documento),
      documento_normalizado: trim(formData.documento_normalizado),
      telefono_1: trim(formData.telefono_1),
      telefono_2: trim(formData.telefono_2),
      direccion: trim(formData.direccion),
      barrio: trim(formData.barrio),
      ciudad: trim(formData.ciudad),
      ocupacion: trim(formData.ocupacion),
    };
    try {
      await crearCliente(payload);
      setFormData(EMPTY_CREATE);
      setShowForm(false);
      setOffset(0);
      refresh();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Error al crear cliente');
    }
  }

  async function handleEdit(e: React.FormEvent) {
    if (!editingId || !editData) return;
    e.preventDefault();
    setError(null);
    const trim = (v: string | null | undefined): string | null => v?.trim() || null;
    const payload: ClienteUpdateInput = {
      primer_apellido: trim(editData.primer_apellido),
      segundo_apellido: trim(editData.segundo_apellido),
      nombres: trim(editData.nombres),
      telefono_1: trim(editData.telefono_1),
      telefono_2: trim(editData.telefono_2),
      direccion: trim(editData.direccion),
      barrio: trim(editData.barrio),
      ciudad: trim(editData.ciudad),
      ocupacion: trim(editData.ocupacion),
    };
    try {
      await editarCliente(editingId, payload);
      setEditingId(null);
      setEditData(null);
      refresh();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Error al editar cliente');
    }
  }

  async function startEdit(c: ClienteList) {
    setError(null);
    setEditingId(c.id);
    setEditData(null);
    setEditingLoading(true);
    try {
      const detalle = await fetchCliente360(c.id);
      setEditData({
        primer_apellido: detalle.primer_apellido ?? '',
        segundo_apellido: detalle.segundo_apellido ?? '',
        nombres: detalle.nombres ?? '',
        telefono_1: detalle.telefono_1 ?? '',
        telefono_2: detalle.telefono_2 ?? '',
        direccion: detalle.direccion ?? '',
        barrio: detalle.barrio ?? '',
        ciudad: detalle.ciudad ?? '',
        ocupacion: detalle.ocupacion ?? '',
      });
    } catch {
      setError('Error al cargar los datos para editar');
      setEditingId(null);
    } finally {
      setEditingLoading(false);
    }
  }

  function setEditField(field: keyof ClienteUpdateInput, value: string) {
    setEditData((prev) => (prev ? { ...prev, [field]: value } : prev));
  }

  const total = page.total;
  const from = total === 0 ? 0 : offset + 1;
  const to = Math.min(offset + page.items.length, total);

  return (
    <div className="space-y-6" role="main" aria-label="Clientes">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-textPrimary">Clientes</h1>
        {canManage && (
          <Button onClick={() => { setShowForm(!showForm); }} variant="primary" aria-expanded={showForm}>
            {showForm ? 'Cancelar' : 'Nuevo Cliente'}
          </Button>
        )}
      </div>

      {error && (
        <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-500 text-sm" role="alert">
          {error}
        </div>
      )}

      {showForm && canManage && (
        <Card elevated>
          <div className="font-bold text-lg mb-4">Nuevo Cliente</div>
          <form onSubmit={handleCreate} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <FormField id="nuevo-primer_apellido" label="Primer apellido" messageTone="hint">
                <Input
                  id="nuevo-primer_apellido"
                  value={formData.primer_apellido}
                  onChange={(e) => setFormData({ ...formData, primer_apellido: e.target.value })}
                  placeholder="Apellido"
                  required
                  maxLength={100}
                />
              </FormField>
              <FormField id="nuevo-segundo_apellido" label="Segundo apellido" messageTone="hint">
                <Input
                  id="nuevo-segundo_apellido"
                  value={formData.segundo_apellido ?? ''}
                  onChange={(e) => setFormData({ ...formData, segundo_apellido: e.target.value })}
                  placeholder="Segundo apellido (opcional)"
                  maxLength={100}
                />
              </FormField>
              <FormField id="nuevo-nombres" label="Nombres" messageTone="hint">
                <Input
                  id="nuevo-nombres"
                  value={formData.nombres}
                  onChange={(e) => setFormData({ ...formData, nombres: e.target.value })}
                  placeholder="Nombres"
                  required
                  maxLength={200}
                />
              </FormField>
              <FormField id="nuevo-tipo_documento" label="Tipo de documento" messageTone="hint">
                <select
                  id="nuevo-tipo_documento"
                  value={formData.tipo_documento ?? ''}
                  onChange={(e) => setFormData({ ...formData, tipo_documento: e.target.value })}
                  className="w-full px-3 py-2 border border-outline rounded-lg bg-surface text-textPrimary"
                  aria-label="Tipo de documento"
                >
                  <option value="">Seleccionar…</option>
                  {TIPO_DOCUMENTOS.map((t) => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </select>
              </FormField>
              <FormField id="nuevo-documento_normalizado" label="Documento" messageTone="hint">
                <Input
                  id="nuevo-documento_normalizado"
                  value={formData.documento_normalizado ?? ''}
                  onChange={(e) => setFormData({ ...formData, documento_normalizado: e.target.value })}
                  placeholder="Número de documento"
                  maxLength={50}
                />
              </FormField>
              <FormField id="nuevo-telefono_1" label="Teléfono" messageTone="hint">
                <Input
                  id="nuevo-telefono_1"
                  value={formData.telefono_1 ?? ''}
                  onChange={(e) => setFormData({ ...formData, telefono_1: e.target.value })}
                  placeholder="Teléfono principal"
                  maxLength={20}
                />
              </FormField>
              <FormField id="nuevo-telefono_2" label="Teléfono 2" messageTone="hint">
                <Input
                  id="nuevo-telefono_2"
                  value={formData.telefono_2 ?? ''}
                  onChange={(e) => setFormData({ ...formData, telefono_2: e.target.value })}
                  placeholder="Teléfono alternativo (opcional)"
                  maxLength={20}
                />
              </FormField>
              <FormField id="nuevo-ciudad" label="Ciudad" messageTone="hint">
                <Input
                  id="nuevo-ciudad"
                  value={formData.ciudad ?? ''}
                  onChange={(e) => setFormData({ ...formData, ciudad: e.target.value })}
                  placeholder="Ciudad"
                  maxLength={100}
                />
              </FormField>
              <FormField id="nuevo-barrio" label="Barrio" messageTone="hint">
                <Input
                  id="nuevo-barrio"
                  value={formData.barrio ?? ''}
                  onChange={(e) => setFormData({ ...formData, barrio: e.target.value })}
                  placeholder="Barrio"
                  maxLength={100}
                />
              </FormField>
              <FormField id="nuevo-direccion" label="Dirección" messageTone="hint">
                <Input
                  id="nuevo-direccion"
                  value={formData.direccion ?? ''}
                  onChange={(e) => setFormData({ ...formData, direccion: e.target.value })}
                  placeholder="Dirección"
                  maxLength={300}
                />
              </FormField>
              <FormField id="nuevo-ocupacion" label="Ocupación" messageTone="hint">
                <Input
                  id="nuevo-ocupacion"
                  value={formData.ocupacion ?? ''}
                  onChange={(e) => setFormData({ ...formData, ocupacion: e.target.value })}
                  placeholder="Ocupación (opcional)"
                  maxLength={100}
                />
              </FormField>
            </div>
            <Button type="submit" variant="primary">Crear Cliente</Button>
          </form>
        </Card>
      )}

      <Card elevated>
        <div className="font-bold text-lg mb-4">Filtros</div>
        <form onSubmit={handleSearchSubmit} className="flex flex-wrap gap-4">
          <div className="flex-1 min-w-[220px]">
            <label htmlFor="searchClientes" className="block text-sm text-textSecondary mb-1">Buscar</label>
            <Input
              id="searchClientes"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Nombre, documento o teléfono…"
            />
          </div>
          <div className="flex-1 min-w-[180px]">
            <label htmlFor="filterIdentity" className="block text-sm text-textSecondary mb-1">Estado de identidad</label>
            <select
              id="filterIdentity"
              value={identityFilter}
              onChange={(e) => { setIdentityFilter(e.target.value); setOffset(0); }}
              className="w-full px-3 py-2 border border-outline rounded-lg bg-surface text-textPrimary"
              aria-label="Filtrar por estado de identidad"
            >
              <option value="">Todos</option>
              <option value="VERIFIED">Verificados</option>
              <option value="PROVISIONAL">Provisionales</option>
              <option value="POSSIBLE_DUPLICATE">Posibles duplicados</option>
            </select>
          </div>
          <div className="flex-1 min-w-[140px]">
            <label htmlFor="filterTipoDoc" className="block text-sm text-textSecondary mb-1">Tipo de documento</label>
            <select
              id="filterTipoDoc"
              value={tipoDocFilter}
              onChange={(e) => { setTipoDocFilter(e.target.value); setOffset(0); }}
              className="w-full px-3 py-2 border border-outline rounded-lg bg-surface text-textPrimary"
              aria-label="Filtrar por tipo de documento"
            >
              <option value="">Todos</option>
              {TIPO_DOCUMENTOS.map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </div>
          <div className="flex items-end gap-2">
            <Button type="submit" variant="primary">Buscar</Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => { setSearchInput(''); setSearch(''); setIdentityFilter(''); setTipoDocFilter(''); setOffset(0); }}
            >
              Limpiar
            </Button>
          </div>
        </form>
      </Card>

      {loading ? (
        <Card elevated>
          <div className="text-center py-8 text-textSecondary" role="status" aria-label="Cargando clientes">
            <div className="animate-pulse">Cargando clientes...</div>
          </div>
        </Card>
      ) : (
        <Card elevated>
          <div className="font-bold text-lg mb-4">Clientes ({total})</div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm" role="table" aria-label="Lista de clientes">
              <thead>
                <tr className="border-b border-outline">
                  <th className="text-left py-3 px-4 text-textSecondary font-medium" scope="col">Nombre</th>
                  <th className="text-left py-3 px-4 text-textSecondary font-medium" scope="col">Documento</th>
                  <th className="text-left py-3 px-4 text-textSecondary font-medium" scope="col">Identidad</th>
                  <th className="text-left py-3 px-4 text-textSecondary font-medium" scope="col">Créditos</th>
                  <th className="text-left py-3 px-4 text-textSecondary font-medium" scope="col">Teléfono</th>
                  <th className="text-left py-3 px-4 text-textSecondary font-medium" scope="col">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {page.items.map((c) => (
                  <tr key={c.id} className="border-b border-outline/50">
                    <td className="py-3 px-4">
                      <Link
                        href={`/clientes/${c.id}`}
                        className="text-textPrimary hover:text-primary focus:outline-none focus:ring-2 focus:ring-primary/50 rounded"
                        aria-label={`Ver detalle de ${nombreCompleto(c)}`}
                      >
                        {nombreCompleto(c)}
                      </Link>
                    </td>
                    <td className="py-3 px-4 text-textSecondary">
                      {c.documento_normalizado ? `${c.tipo_documento ?? ''} ${c.documento_normalizado}`.trim() : '—'}
                    </td>
                    <td className="py-3 px-4">{identityBadge(c.identity_status)}</td>
                    <td className="py-3 px-4 text-textSecondary">{c.creditos_activos}</td>
                    <td className="py-3 px-4 text-textSecondary">{c.telefono_1 || '—'}</td>
                    <td className="py-3 px-4">
                      <div className="flex gap-2 flex-wrap">
                        <Link
                          href={`/clientes/${c.id}`}
                          className="btn btn-outline btn-sm"
                          aria-label={`Ver detalle de ${nombreCompleto(c)}`}
                        >
                          Ver
                        </Link>
                        {canManage && (
                          <Button size="sm" variant="outline" onClick={() => startEdit(c)} aria-label={`Editar ${nombreCompleto(c)}`}>
                            Editar
                          </Button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
                {page.items.length === 0 && !loading && (
                  <tr>
                    <td colSpan={6} className="py-8 text-center text-textSecondary" aria-label="No hay clientes">
                      {search || identityFilter || tipoDocFilter
                        ? 'No hay clientes con los filtros aplicados'
                        : 'No hay clientes registrados'}
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

      {/* Edit modal */}
      {editingId && canManage && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" role="dialog" aria-modal="true" aria-label="Editar cliente">
          <Card elevated className="max-w-lg mx-4 w-full max-h-[90vh] overflow-y-auto">
            <div className="font-bold text-lg mb-2">Editar Cliente</div>
            {editingLoading ? (
              <div className="text-center py-8 text-textSecondary" role="status" aria-label="Cargando datos del cliente">
                <div className="animate-pulse">Cargando datos del cliente...</div>
              </div>
            ) : editData ? (
              <>
                <p className="text-sm text-textSecondary mb-4">
                  Solo se pueden editar nombres y datos de contacto. La identidad (documento) se resuelve por el flujo de verificación.
                </p>
                <form onSubmit={handleEdit} className="space-y-4">
                  <FormField id="edit-primer_apellido" label="Primer apellido" messageTone="hint">
                    <Input
                      id="edit-primer_apellido"
                      value={editData.primer_apellido ?? ''}
                      onChange={(e) => setEditField('primer_apellido', e.target.value)}
                      maxLength={100}
                    />
                  </FormField>
                  <FormField id="edit-segundo_apellido" label="Segundo apellido" messageTone="hint">
                    <Input
                      id="edit-segundo_apellido"
                      value={editData.segundo_apellido ?? ''}
                      onChange={(e) => setEditField('segundo_apellido', e.target.value)}
                      maxLength={100}
                    />
                  </FormField>
                  <FormField id="edit-nombres" label="Nombres" messageTone="hint">
                    <Input
                      id="edit-nombres"
                      value={editData.nombres ?? ''}
                      onChange={(e) => setEditField('nombres', e.target.value)}
                      maxLength={200}
                    />
                  </FormField>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <FormField id="edit-telefono_1" label="Teléfono" messageTone="hint">
                      <Input
                        id="edit-telefono_1"
                        value={editData.telefono_1 ?? ''}
                        onChange={(e) => setEditField('telefono_1', e.target.value)}
                        maxLength={20}
                      />
                    </FormField>
                    <FormField id="edit-telefono_2" label="Teléfono 2" messageTone="hint">
                      <Input
                        id="edit-telefono_2"
                        value={editData.telefono_2 ?? ''}
                        onChange={(e) => setEditField('telefono_2', e.target.value)}
                        maxLength={20}
                      />
                    </FormField>
                    <FormField id="edit-ciudad" label="Ciudad" messageTone="hint">
                      <Input
                        id="edit-ciudad"
                        value={editData.ciudad ?? ''}
                        onChange={(e) => setEditField('ciudad', e.target.value)}
                        maxLength={100}
                      />
                    </FormField>
                    <FormField id="edit-barrio" label="Barrio" messageTone="hint">
                      <Input
                        id="edit-barrio"
                        value={editData.barrio ?? ''}
                        onChange={(e) => setEditField('barrio', e.target.value)}
                        maxLength={100}
                      />
                    </FormField>
                    <FormField id="edit-direccion" label="Dirección" messageTone="hint">
                      <Input
                        id="edit-direccion"
                        value={editData.direccion ?? ''}
                        onChange={(e) => setEditField('direccion', e.target.value)}
                        maxLength={300}
                      />
                    </FormField>
                    <FormField id="edit-ocupacion" label="Ocupación" messageTone="hint">
                      <Input
                        id="edit-ocupacion"
                        value={editData.ocupacion ?? ''}
                        onChange={(e) => setEditField('ocupacion', e.target.value)}
                        maxLength={100}
                      />
                    </FormField>
                  </div>
                  <div className="flex gap-2 justify-end">
                    <Button type="button" variant="outline" onClick={() => { setEditingId(null); setEditData(null); }}>Cancelar</Button>
                    <Button type="submit" variant="primary">Guardar</Button>
                  </div>
                </form>
              </>
            ) : null}
          </Card>
        </div>
      )}
    </div>
  );
}
