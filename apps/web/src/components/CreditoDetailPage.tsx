'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { fetchCredito } from '@/lib/api/client';
import type { CreditoDetail } from '@/lib/api/client';
import { hasCapability } from '@/lib/rbac';

const money = new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 0 });

const ESTADO_LABELS: Record<string, { label: string; tone: 'success' | 'warning' | 'danger' | 'neutral' }> = {
  ACTIVO: { label: 'Activo', tone: 'success' },
  PAGADO: { label: 'Pagado', tone: 'neutral' },
  REFINANCIADO: { label: 'Refinanciado', tone: 'warning' },
  CANCELADO: { label: 'Cancelado', tone: 'danger' },
};

const PERIODICIDAD_LABELS: Record<string, string> = {
  DIARIO: 'Diaria',
  SEMANAL: 'Semanal',
  QUINCENAL: 'Quincenal',
  UNICA: 'Única',
};

export function CreditoDetailPage({
  creditoId,
  session,
}: {
  creditoId: string;
  session: import("@/lib/rbac").SessionUser | null;
}) {
  const canCliente360 = hasCapability(session, 'clientes:ver');

  const [data, setData] = useState<CreditoDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;

    async function load() {
      try {
        setLoading(true);
        setError(null);
        const d = await fetchCredito(creditoId);
        if (!ignore) setData(d);
      } catch {
        if (!ignore) setError('Error al cargar el crédito');
      } finally {
        if (!ignore) setLoading(false);
      }
    }

    void load();

    return () => {
      ignore = true;
    };
  }, [creditoId]);

  if (loading) {
    return (
      <div className="space-y-6" role="main" aria-label="Detalle del crédito">
        <Card elevated>
          <div className="text-center py-8 text-textSecondary" role="status" aria-label="Cargando crédito">
            <div className="animate-pulse">Cargando crédito...</div>
          </div>
        </Card>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="space-y-6" role="main" aria-label="Detalle del crédito">
        <Card elevated>
          <div className="text-center py-8 text-red-500" role="alert">{error ?? 'Crédito no encontrado'}</div>
        </Card>
      </div>
    );
  }

  const estado = ESTADO_LABELS[data.estado] ?? { label: data.estado, tone: 'neutral' as const };
  const pct = data.n_cuotas > 0 ? Math.min(100, Math.round((data.cuotas_pagadas / data.n_cuotas) * 100)) : 0;

  return (
    <div className="space-y-6" role="main" aria-label="Detalle del crédito">
      <div className="flex items-center gap-3 flex-wrap">
        <h1 className="text-2xl font-bold text-textPrimary">Crédito</h1>
        <Badge tone={estado.tone}>{estado.label}</Badge>
        <Link href="/creditos" className="text-sm text-textSecondary hover:text-primary" aria-label="Volver a créditos">
          ← Volver
        </Link>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card elevated>
          <div className="font-bold text-lg mb-4">Información</div>
          <dl className="space-y-3 text-sm">
            <div className="flex justify-between gap-4">
              <dt className="text-textSecondary">Cliente</dt>
              <dd className="text-textPrimary font-medium">
                {data.cliente_nombre ?? '—'}
                {canCliente360 && data.cliente_id && (
                  <Link href={`/clientes/${data.cliente_id}`} className="ml-2 text-primary underline hover:no-underline" aria-label={`Ver Cliente 360 de ${data.cliente_nombre ?? 'cliente'}`}>
                    Cliente 360
                  </Link>
                )}
              </dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-textSecondary">Ruta</dt>
              <dd className="text-textPrimary font-medium">{data.ruta_nombre || '—'}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-textSecondary">Cobrador</dt>
              <dd className="text-textPrimary font-medium">{data.cobrador_nombre ?? '—'}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-textSecondary">Periodicidad</dt>
              <dd className="text-textPrimary font-medium">{PERIODICIDAD_LABELS[data.periodicidad] ?? data.periodicidad}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-textSecondary">Fecha de inicio</dt>
              <dd className="text-textPrimary font-medium">{new Date(data.fecha_inicio).toLocaleDateString('es-CO')}</dd>
            </div>
          </dl>
        </Card>

        <Card elevated>
          <div className="font-bold text-lg mb-4">Financiero</div>
          <dl className="space-y-3 text-sm">
            <div className="flex justify-between gap-4">
              <dt className="text-textSecondary">Monto</dt>
              <dd className="text-textPrimary font-medium">{money.format(data.monto)}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-textSecondary">Cuota</dt>
              <dd className="text-textPrimary font-medium">{money.format(data.cuota)}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-textSecondary">Total (cuota × cuotas)</dt>
              <dd className="text-textPrimary font-medium">{money.format(data.total)}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-textSecondary">Saldo</dt>
              <dd className="text-textPrimary font-bold text-base">{money.format(data.saldo)}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-textSecondary">Cuotas pagadas</dt>
              <dd className="text-textPrimary font-medium">{data.cuotas_pagadas}/{data.n_cuotas}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-textSecondary">Mora</dt>
              <dd className="text-textPrimary font-medium">{data.mora > 0 ? `${data.mora} días` : 'Al día'}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-textSecondary">Pico de mora</dt>
              <dd className="text-textPrimary font-medium">{data.pico > 0 ? `${data.pico} días` : '—'}</dd>
            </div>
          </dl>
          <div className="mt-4" aria-label="Progreso de cuotas">
            <div className="flex justify-between text-xs text-textSecondary mb-1">
              <span>Progreso</span>
              <span>{pct}%</span>
            </div>
            <div className="h-2 rounded-full bg-outline/40 overflow-hidden">
              <div className="h-full bg-primary rounded-full transition-all" style={{ width: `${pct}%` }} />
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}
