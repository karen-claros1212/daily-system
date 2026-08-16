'use client';

import { useState, useEffect, useRef } from 'react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { FormField } from '@/components/ui/field';
import { hasCapability } from '@/lib/rbac';

import {
  fetchUsuarios,
  crearUsuario,
  editarUsuario,
  cambiarEstadoUsuario,
  generarCodigoActivacion,
  type UsuarioList,
} from '@/lib/api/client';

type ActivationResult = { prefijo: string; token: string; expira_el: string };

const ROLES = ['COBRADOR', 'INVERSIONISTA'] as const;
const ROL_LABELS: Record<string, string> = {
  COBRADOR: 'Cobrador',
  INVERSIONISTA: 'Inversionista',
  ADMINISTRADOR: 'Administrador',
};

export function UsuariosPage({ session }: { session: import("@/lib/rbac").SessionUser | null }) {
  const [usuarios, setUsuarios] = useState<UsuarioList[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState({ nombre: '', rol: 'COBRADOR' as string, documento: '' });
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editData, setEditData] = useState({ nombre: '', documento: '' });
  const [filters, setFilters] = useState({ rol: '', activo: '' });
  const [activatingId, setActivatingId] = useState<string | null>(null);
  const [activationResult, setActivationResult] = useState<ActivationResult | null>(null);
  const [confirmDeactivateId, setConfirmDeactivateId] = useState<string | null>(null);
  const [confirmName, setConfirmName] = useState('');
  const [refreshKey, setRefreshKey] = useState(0);

  const isAdmin = hasCapability(session, 'usuarios:gestionar');
  const confirmInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    let ignore = false;

    async function loadUsuarios() {
      try {
        setLoading(true);
        setError(null);
        const data = await fetchUsuarios({
          rol: filters.rol || undefined,
          activo: filters.activo || undefined,
        });
        if (!ignore) {
          setUsuarios(data);
        }
      } catch {
        if (!ignore) {
          setError('Error al cargar usuarios');
        }
      } finally {
        if (!ignore) {
          setLoading(false);
        }
      }
    }

    void loadUsuarios();

    return () => {
      ignore = true;
    };
  }, [filters.rol, filters.activo, refreshKey]);

  function refresh() {
    setRefreshKey(k => k + 1);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await crearUsuario({ nombre: formData.nombre.trim(), rol: formData.rol, documento: formData.documento.trim() || null });
      setFormData({ nombre: '', rol: 'COBRADOR', documento: '' });
      setShowForm(false);
      refresh();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Error al crear usuario');
    }
  }

  async function handleEdit(id: string, e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await editarUsuario(id, { nombre: editData.nombre.trim(), documento: editData.documento.trim() || null });
      setEditingId(null);
      refresh();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Error al editar usuario');
    }
  }

  async function handleToggleEstado(id: string, activo: number) {
    setError(null);
    try {
      await cambiarEstadoUsuario(id, activo);
      refresh();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Error al cambiar estado');
    }
  }

  async function handleGenerateActivation(usuarioId: string, _nombre?: string) {
    setActivatingId(usuarioId);
    setActivationResult(null);
    setError(null);
    try {
      const result = await generarCodigoActivacion({ usuario_id: usuarioId, expira_minutos: 60 });
      setActivationResult(result);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Error al generar código de activación');
    } finally {
      setActivatingId(null);
    }
  }

  function handleConfirmDeactivate(usuarioId: string, nombre: string) {
    setConfirmDeactivateId(usuarioId);
    setConfirmName('');
  }

  async function handleConfirmDeactivateSubmit(e: React.FormEvent) {
    if (!confirmDeactivateId) return;
    e.preventDefault();
    if (confirmName.trim().toUpperCase() !== usuarios.find(u => u.id === confirmDeactivateId)?.nombre?.trim().toUpperCase()) {
      setError('El nombre no coincide');
      return;
    }
    setError(null);
    try {
      await handleToggleEstado(confirmDeactivateId, 0);
      setConfirmDeactivateId(null);
      setConfirmName('');
    } catch {
      // handled by handleToggleEstado
    }
  }

  function handleCancelConfirm() {
    setConfirmDeactivateId(null);
    setConfirmName('');
  }

  // Keyboard navigation: focus confirm input when modal opens
  useEffect(() => {
    if (confirmDeactivateId && confirmInputRef.current) {
      confirmInputRef.current.focus();
    }
  }, [confirmDeactivateId]);

  if (!isAdmin) return null;

  return (
    <div className="space-y-6" role="main" aria-label="Gestión de Usuarios">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-textPrimary">Gestión de Usuarios</h1>
        <Button onClick={() => { setShowForm(!showForm); setActivationResult(null); }} variant="primary" aria-expanded={showForm}>
          {showForm ? 'Cancelar' : 'Nuevo Usuario'}
        </Button>
      </div>

      {error && (
        <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-500 text-sm" role="alert">
          {error}
        </div>
      )}

      {activationResult && (
        <Card elevated className="border-green-500/30 bg-green-500/5">
          <div className="font-bold text-green-600 mb-2">Código de activación generado</div>
          <div className="space-y-1 text-sm">
            <div><span className="text-textSecondary">Prefijo:</span> <code className="font-mono bg-green-500/10 px-2 py-0.5 rounded">{activationResult.prefijo}</code></div>
            <div><span className="text-textSecondary">Token:</span> <code className="font-mono bg-green-500/10 px-2 py-0.5 rounded break-all">{activationResult.token}</code></div>
            <div><span className="text-textSecondary">Expira:</span> {new Date(activationResult.expira_el).toLocaleString('es-CO')}</div>
          </div>
          <Button size="sm" variant="outline" className="mt-3" onClick={() => setActivationResult(null)}>Cerrar</Button>
        </Card>
      )}

      {showForm && (
        <Card elevated>
          <div className="font-bold text-lg mb-4">Nuevo Usuario</div>
          <form onSubmit={handleSubmit} className="space-y-4">
            <FormField id="nombre" label="Nombre" messageTone="hint">
              <Input
                id="nombre"
                value={formData.nombre}
                onChange={(e) => setFormData({ ...formData, nombre: e.target.value })}
                placeholder="Nombre completo"
                required
                autoFocus
              />
            </FormField>
            <FormField id="rol" label="Rol" messageTone="hint">
              <select
                id="rol"
                value={formData.rol}
                onChange={(e) => setFormData({ ...formData, rol: e.target.value })}
                className="w-full px-3 py-2 border border-outline rounded-lg bg-surface text-textPrimary"
                aria-label="Seleccionar rol"
              >
                {ROLES.map(r => (
                  <option key={r} value={r}>{ROL_LABELS[r]}</option>
                ))}
              </select>
            </FormField>
            <FormField id="documento" label="Documento" messageTone="hint">
              <Input
                id="documento"
                value={formData.documento}
                onChange={(e) => setFormData({ ...formData, documento: e.target.value })}
                placeholder="Número de documento (opcional)"
              />
            </FormField>
            <Button type="submit" variant="primary">Crear Usuario</Button>
          </form>
        </Card>
      )}

      <Card elevated>
        <div className="font-bold text-lg mb-4">Filtros</div>
        <div className="flex flex-wrap gap-4">
          <div className="flex-1 min-w-[180px]">
            <label htmlFor="filterRol" className="block text-sm text-textSecondary mb-1">Rol</label>
            <select
              id="filterRol"
              value={filters.rol}
              onChange={(e) => setFilters({ ...filters, rol: e.target.value })}
              className="w-full px-3 py-2 border border-outline rounded-lg bg-surface text-textPrimary"
              aria-label="Filtrar por rol"
            >
              <option value="">Todos</option>
              {ROLES.map(r => (
                <option key={r} value={r}>{ROL_LABELS[r]}</option>
              ))}
              <option value="ADMINISTRADOR">Administrador</option>
            </select>
          </div>
          <div className="flex-1 min-w-[180px]">
            <label htmlFor="filterActivo" className="block text-sm text-textSecondary mb-1">Estado</label>
            <select
              id="filterActivo"
              value={filters.activo}
              onChange={(e) => setFilters({ ...filters, activo: e.target.value })}
              className="w-full px-3 py-2 border border-outline rounded-lg bg-surface text-textPrimary"
              aria-label="Filtrar por estado"
            >
              <option value="">Todos</option>
              <option value="1">Activos</option>
              <option value="0">Inactivos</option>
            </select>
          </div>
          <div className="flex items-end">
            <Button onClick={refresh} variant="primary">Filtrar</Button>
          </div>
        </div>
      </Card>

      {loading ? (
        <Card elevated>
          <div className="text-center py-8 text-textSecondary" role="status" aria-label="Cargando usuarios">
            <div className="animate-pulse">Cargando usuarios...</div>
          </div>
        </Card>
      ) : (
        <Card elevated>
          <div className="font-bold text-lg mb-4">Usuarios ({usuarios.length})</div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm" role="table" aria-label="Lista de usuarios">
              <thead>
                <tr className="border-b border-outline">
                  <th className="text-left py-3 px-4 text-textSecondary font-medium" scope="col">Nombre</th>
                  <th className="text-left py-3 px-4 text-textSecondary font-medium" scope="col">Rol</th>
                  <th className="text-left py-3 px-4 text-textSecondary font-medium" scope="col">Documento</th>
                  <th className="text-left py-3 px-4 text-textSecondary font-medium" scope="col">Estado</th>
                  <th className="text-left py-3 px-4 text-textSecondary font-medium" scope="col">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {usuarios.map((u) => (
                  <tr key={u.id} className="border-b border-outline/50 focus-within:bg-primary/5">
                    <td className="py-3 px-4">
                      {editingId === u.id ? (
                        <form onSubmit={(e) => handleEdit(u.id, e)} className="flex gap-2">
                          <Input
                            value={editData.nombre}
                            onChange={(e) => setEditData({ ...editData, nombre: e.target.value })}
                            className="flex-1"
                            autoFocus
                            aria-label="Editar nombre"
                          />
                          <Button type="submit" size="sm" variant="primary">Guardar</Button>
                          <Button type="button" size="sm" variant="outline" onClick={() => setEditingId(null)}>Cancelar</Button>
                        </form>
                      ) : (
                        <span
                          className="cursor-pointer text-textPrimary hover:text-primary focus:text-primary focus:outline-none focus:ring-2 focus:ring-primary/50 rounded"
                          onClick={() => {
                            setEditingId(u.id);
                            setEditData({ nombre: u.nombre, documento: u.documento || '' });
                          }}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter' || e.key === ' ') {
                              e.preventDefault();
                              setEditingId(u.id);
                              setEditData({ nombre: u.nombre, documento: u.documento || '' });
                            }
                          }}
                          tabIndex={0}
                          role="button"
                          aria-label={`Editar ${u.nombre}`}
                        >
                          {u.nombre}
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-4">
                      <Badge tone={u.rol === 'COBRADOR' ? 'neutral' : 'info'}>{u.rol}</Badge>
                    </td>
                    <td className="py-3 px-4 text-textSecondary">{u.documento || '—'}</td>
                    <td className="py-3 px-4">
                      <Badge tone={u.activo === 1 ? 'success' : 'warning'}>
                        {u.activo === 1 ? 'Activo' : 'Inactivo'}
                      </Badge>
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex gap-2 flex-wrap">
                        {u.activo === 1 ? (
                          <>
                            <Button size="sm" variant="outline" onClick={() => {
                              setEditingId(u.id);
                              setEditData({ nombre: u.nombre, documento: u.documento || '' });
                            }} aria-label={`Editar ${u.nombre}`}>Editar</Button>
                            <Button size="sm" variant="danger" onClick={() => handleConfirmDeactivate(u.id, u.nombre)} aria-label={`Desactivar ${u.nombre}`}>
                              Desactivar
                            </Button>
                            <Button size="sm" variant="primary" onClick={() => handleGenerateActivation(u.id)} loading={activatingId === u.id} aria-label={`Generar activación para ${u.nombre}`}>
                              Activación
                            </Button>
                          </>
                        ) : (
                          <>
                            <Button size="sm" variant="primary" onClick={() => handleToggleEstado(u.id, 1)} aria-label={`Activar ${u.nombre}`}>Activar</Button>
                            <Button size="sm" variant="danger" onClick={() => handleGenerateActivation(u.id)} loading={activatingId === u.id} aria-label={`Generar activación para ${u.nombre}`}>
                              Activación
                            </Button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
                {usuarios.length === 0 && !loading && (
                  <tr>
                    <td colSpan={5} className="py-8 text-center text-textSecondary" aria-label="No hay usuarios">
                      {filters.rol || filters.activo
                        ? 'No hay usuarios con los filtros aplicados'
                        : 'No hay usuarios registrados'}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* Confirm deactivation modal */}
      {confirmDeactivateId && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" role="dialog" aria-modal="true" aria-label="Confirmar desactivación">
          <Card elevated className="max-w-sm mx-4">
            <div className="font-bold text-lg mb-2">Confirmar desactivación</div>
            <p className="text-sm text-textSecondary mb-4">
              Escribe el nombre del usuario para confirmar: <strong>{usuarios.find(u => u.id === confirmDeactivateId)?.nombre}</strong>
            </p>
            <form onSubmit={handleConfirmDeactivateSubmit} className="space-y-4">
              <FormField id="confirmName" label="Escribe el nombre" messageTone="hint">
                <Input
                  ref={confirmInputRef}
                  id="confirmName"
                  value={confirmName}
                  onChange={(e) => setConfirmName(e.target.value)}
                  placeholder={usuarios.find(u => u.id === confirmDeactivateId)?.nombre || ''}
                  autoFocus
                />
              </FormField>
              <div className="flex gap-2 justify-end">
                <Button type="button" variant="outline" onClick={handleCancelConfirm}>Cancelar</Button>
                <Button type="submit" variant="danger">Desactivar</Button>
              </div>
            </form>
          </Card>
        </div>
      )}
    </div>
  );
}
