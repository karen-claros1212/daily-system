'use client';

import { useState, useEffect } from 'react';
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
  type UsuarioList,
  type Usuario,
} from '@/lib/api/client';

export function UsuariosPage({ session }: { session: import("@/lib/rbac").SessionUser | null }) {
  const [usuarios, setUsuarios] = useState<UsuarioList[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState({ nombre: '', rol: 'COBRADOR', documento: '' });
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editData, setEditData] = useState({ nombre: '', documento: '' });

  const isAdmin = hasCapability(session, 'usuarios:gestionar');
  const _session = session;

  useEffect(() => {
    loadUsuarios();
  }, []);

  async function loadUsuarios() {
    try {
      const data = await fetchUsuarios();
      setUsuarios(data);
    } catch (e) {
      setError('Error al cargar usuarios');
    } finally {
      setLoading(false);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await crearUsuario({ nombre: formData.nombre, rol: formData.rol, documento: formData.documento || undefined });
      setFormData({ nombre: '', rol: 'COBRADOR', documento: '' });
      setShowForm(false);
      await loadUsuarios();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Error al crear usuario');
    }
  }

  async function handleEdit(id: string, e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await editarUsuario(id, { nombre: editData.nombre, documento: editData.documento || null });
      setEditingId(null);
      await loadUsuarios();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Error al editar usuario');
    }
  }

  async function handleToggleEstado(id: string, activo: number) {
    setError(null);
    try {
      await cambiarEstadoUsuario(id, activo);
      await loadUsuarios();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Error al cambiar estado');
    }
  }

  if (!isAdmin) return null;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-textPrimary">Gestión de Usuarios</h1>
        <Button onClick={() => setShowForm(!showForm)} variant="primary">
          {showForm ? 'Cancelar' : 'Nuevo Usuario'}
        </Button>
      </div>

      {error && (
        <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-500 text-sm">
          {error}
        </div>
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
              />
            </FormField>
            <FormField id="rol" label="Rol" messageTone="hint">
              <select
                id="rol"
                value={formData.rol}
                onChange={(e) => setFormData({ ...formData, rol: e.target.value })}
                className="w-full px-3 py-2 border border-outline rounded-lg bg-surface text-textPrimary"
              >
                <option value="COBRADOR">Cobrador</option>
                <option value="INVERSIONISTA">Inversionista</option>
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

      {loading ? (
        <div className="text-center py-8 text-textSecondary">Cargando...</div>
      ) : (
        <Card elevated>
          <div className="font-bold text-lg mb-4">Usuarios ({usuarios.length})</div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-outline">
                  <th className="text-left py-3 px-4 text-textSecondary font-medium">Nombre</th>
                  <th className="text-left py-3 px-4 text-textSecondary font-medium">Rol</th>
                  <th className="text-left py-3 px-4 text-textSecondary font-medium">Documento</th>
                  <th className="text-left py-3 px-4 text-textSecondary font-medium">Estado</th>
                  <th className="text-left py-3 px-4 text-textSecondary font-medium">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {usuarios.map((u) => (
                  <tr key={u.id} className="border-b border-outline/50">
                    <td className="py-3 px-4">
                      {editingId === u.id ? (
                        <form onSubmit={(e) => handleEdit(u.id, e)} className="flex gap-2">
                          <Input
                            value={editData.nombre}
                            onChange={(e) => setEditData({ ...editData, nombre: e.target.value })}
                            className="flex-1"
                          />
                          <Button type="submit" size="sm" variant="primary">Guardar</Button>
                          <Button type="button" size="sm" variant="outline" onClick={() => setEditingId(null)}>Cancelar</Button>
                        </form>
                      ) : (
                        <span className="cursor-pointer text-textPrimary hover:text-primary" onClick={() => {
                          setEditingId(u.id);
                          setEditData({ nombre: u.nombre, documento: u.documento || '' });
                        }}>
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
                      <div className="flex gap-2">
                        {u.activo === 1 ? (
                          <Button size="sm" variant="danger" onClick={() => handleToggleEstado(u.id, 0)}>
                            Desactivar
                          </Button>
                        ) : (
                          <Button size="sm" variant="primary" onClick={() => handleToggleEstado(u.id, 1)}>
                            Activar
                          </Button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
                {usuarios.length === 0 && (
                  <tr>
                    <td colSpan={5} className="py-8 text-center text-textSecondary">
                      No hay usuarios registrados
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
