'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { fetchCliente360, type Cliente360 } from '@/lib/api/client';

const IDENTITY_LABELS: Record<string, { label: string; tone: 'success' | 'warning' | 'danger' | 'neutral' }> = {
  VERIFIED: { label: 'Verificado', tone: 'success' },
  PROVISIONAL: { label: 'Provisional', tone: 'warning' },
  POSSIBLE_DUPLICATE: { label: 'Posible duplicado', tone: 'danger' },
};

const CREDITO_LABELS: Record<string, 'success' | 'warning' | 'info' | 'danger' | 'neutral'> = {
  ACTIVO: 'success',
  PAGADO: 'neutral',
  REFINANCIADO: 'info',
  CANCELADO: 'neutral',
};

const money = new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 0 });

export function nombreCompleto360(c: Cliente360) {
  return [c.nombres, c.primer_apellido, c.segundo_apellido].filter(Boolean).join(' ').trim() || '—';
}

export function Cliente360Page({ clienteId }: { clienteId: string }) {
  const [cliente, setCliente] = useState<Cliente360 | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;

    async function load() {
      try {
        setLoading(true);
        setError(null);
        const data = await fetchCliente360(clienteId);
        if (!ignore) {
          setCliente(data);
        }
      } catch (e: unknown) {
        if (!ignore) {
          const msg = e instanceof Error && e.message.includes('404')
            ? 'Cliente no encontrado'
            : 'Error al cargar el detalle del cliente';
          setError(msg);
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
  }, [clienteId]);

  if (loading) {
    return (
      <div className="space-y-6" role="main" aria-label="Detalle del cliente">
        <Card elevated>
          <div className="text-center py-8 text-textSecondary" role="status" aria-label="Cargando cliente">
            <div className="animate-pulse">Cargando cliente...</div>
          </div>
        </Card>
      </div>
    );
  }

  if (error || !cliente) {
    return (
      <div className="space-y-6" role="main" aria-label="Detalle del cliente">
        <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-500 text-sm" role="alert">
          {error ?? 'No se pudo cargar el cliente'}
        </div>
        <Link href="/clientes" className="btn btn-outline">Volver a Clientes</Link>
      </div>
    );
  }

  const identity = IDENTITY_LABELS[cliente.identity_status] ?? { label: cliente.identity_status, tone: 'neutral' as const };

  return (
    <div className="space-y-6" role="main" aria-label="Detalle del cliente">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3 flex-wrap">
          <Link href="/clientes" className="btn btn-outline btn-sm" aria-label="Volver a Clientes">← Volver</Link>
          <h1 className="text-2xl font-bold text-textPrimary">{nombreCompleto360(cliente)}</h1>
          <Badge tone={identity.tone}>{identity.label}</Badge>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card elevated>
          <div className="font-bold text-lg mb-3">Información general</div>
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between gap-4">
              <dt className="text-textSecondary">Documento</dt>
              <dd className="text-textPrimary text-right">
                {cliente.documento_normalizado ? `${cliente.tipo_documento ?? ''} ${cliente.documento_normalizado}`.trim() : '—'}
              </dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-textSecondary">Teléfono</dt>
              <dd className="text-textPrimary text-right">{cliente.telefono_1 || '—'}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-textSecondary">Teléfono 2</dt>
              <dd className="text-textPrimary text-right">{cliente.telefono_2 || '—'}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-textSecondary">Dirección</dt>
              <dd className="text-textPrimary text-right">{cliente.direccion || '—'}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-textSecondary">Barrio</dt>
              <dd className="text-textPrimary text-right">{cliente.barrio || '—'}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-textSecondary">Ciudad</dt>
              <dd className="text-textPrimary text-right">{cliente.ciudad || '—'}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-textSecondary">Ocupación</dt>
              <dd className="text-textPrimary text-right">{cliente.ocupacion || '—'}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-textSecondary">Creado</dt>
              <dd className="text-textPrimary text-right">
                {new Date(cliente.creado_el).toLocaleDateString('es-CO')}
              </dd>
            </div>
          </dl>
        </Card>

        <Card elevated>
          <div className="font-bold text-lg mb-3">Créditos</div>
          <div className="text-4xl font-bold text-textPrimary mb-2">{money.format(cliente.saldo_total)}</div>
          <div className="text-sm text-textSecondary">Saldo total (créditos activos)</div>
          <div className="text-sm text-textPrimary mt-3">{cliente.creditos.length} crédito(s) registrado(s)</div>
        </Card>

        <Card elevated>
          <div className="font-bold text-lg mb-3">Pagos recientes</div>
          {cliente.pagos_recientes.length === 0 ? (
            <div className="text-sm text-textSecondary">Sin pagos registrados</div>
          ) : (
            <ul className="space-y-2 text-sm" aria-label="Pagos recientes">
              {cliente.pagos_recientes.map((p) => (
                <li key={p.id} className="flex justify-between gap-4 border-b border-outline/50 pb-2">
                  <div className="text-textPrimary">
                    <div>{money.format(p.monto)}</div>
                    <div className="text-xs text-textSecondary">
                      {new Date(p.recibido_el_servidor).toLocaleDateString('es-CO')}
                      {p.nota ? ` · ${p.nota}` : ''}
                    </div>
                  </div>
                  <Badge tone="success" className="self-start">{p.tipo}</Badge>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <Card elevated>
        <div className="font-bold text-lg mb-4">Créditos del cliente</div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm" role="table" aria-label="Créditos del cliente">
            <thead>
              <tr className="border-b border-outline">
                <th className="text-left py-3 px-4 text-textSecondary font-medium" scope="col">Estado</th>
                <th className="text-left py-3 px-4 text-textSecondary font-medium" scope="col">Cuota</th>
                <th className="text-left py-3 px-4 text-textSecondary font-medium" scope="col">Monto</th>
                <th className="text-left py-3 px-4 text-textSecondary font-medium" scope="col">Total</th>
                <th className="text-left py-3 px-4 text-textSecondary font-medium" scope="col">Saldo</th>
                <th className="text-left py-3 px-4 text-textSecondary font-medium" scope="col">Cuotas pagadas</th>
                <th className="text-left py-3 px-4 text-textSecondary font-medium" scope="col">Mora (días)</th>
                <th className="text-left py-3 px-4 text-textSecondary font-medium" scope="col">Ruta</th>
                <th className="text-left py-3 px-4 text-textSecondary font-medium" scope="col">Cobrador</th>
              </tr>
            </thead>
            <tbody>
              {cliente.creditos.map((cr) => (
                <tr key={cr.id} className="border-b border-outline/50">
                  <td className="py-3 px-4">
                    <Badge tone={CREDITO_LABELS[cr.estado] ?? 'neutral'}>{cr.estado}</Badge>
                  </td>
                  <td className="py-3 px-4 text-textSecondary">{cr.cuota} / {cr.n_cuotas}</td>
                  <td className="py-3 px-4 text-textPrimary">{money.format(cr.monto)}</td>
                  <td className="py-3 px-4 text-textPrimary">{money.format(cr.total)}</td>
                  <td className="py-3 px-4 font-semibold text-textPrimary">{money.format(cr.saldo)}</td>
                  <td className="py-3 px-4 text-textSecondary">{cr.cuotas_pagadas}</td>
                  <td className="py-3 px-4 text-textPrimary">{cr.mora_legacy > 0 ? cr.mora_legacy : '—'}</td>
                  <td className="py-3 px-4 text-textSecondary">{cr.ruta_nombre || '—'}</td>
                  <td className="py-3 px-4 text-textSecondary">{cr.cobrador_nombre || '—'}</td>
                </tr>
              ))}
              {cliente.creditos.length === 0 && (
                <tr>
                  <td colSpan={9} className="py-8 text-center text-textSecondary" aria-label="Sin créditos">
                    El cliente no tiene créditos registrados
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
