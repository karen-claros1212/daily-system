'use client';

import Link from 'next/link';
import type { InversionistaSummary } from '@/lib/api/client';
import { Card } from '@/components/ui/card';
import { MetricCard } from '@/components/ui/misc';
import { Badge } from '@/components/ui/badge';

/**
 * DashboardInversionista (W9) — snapshot financiero read-only del inversionista.
 *
 * Contraste con W8: el Dashboard Ejecutivo es de ADMINISTRADOR (operación +
 * decisiones). El inversionista ve su cartera, el flujo del día, la tendencia,
 * el riesgo y la exposición por ruta — sin PII de cliente/cobrador y sin
 * controles de mutación. Los datos llegan ya calculados por el backend
 * (autoridad canónica W6/W7); aquí NO se recalcula nada.
 *
 * Dashboard = snapshot/decisión. Reportes = análisis histórico y filtros.
 */

const BUCKET_LABELS: Record<string, string> = {
  CURRENT: 'Al día',
  '1-7': '1-7 días',
  '8-15': '8-15 días',
  '16-30': '16-30 días',
  '31-60': '31-60 días',
  '61-90': '61-90 días',
  '90+': '90+ días',
};

interface AccesosItem {
  href: string;
  label: string;
  desc: string;
}

const ACCESOS: AccesosItem[] = [
  { href: '/reportes', label: 'Reportes', desc: 'Análisis histórico y filtros' },
  { href: '/creditos', label: 'Créditos', desc: 'Cartera y detalle (read-only)' },
  { href: '/cobranza', label: 'Cobranza', desc: 'Aging y mora (read-only)' },
  { href: '/movimientos', label: 'Centro Financiero', desc: 'Movimientos de caja' },
];

interface Props {
  data: InversionistaSummary;
}

export function DashboardInversionista({ data }: Props) {
  const p = data.portfolio;
  const moneda = data.negocio?.moneda || data.moneda || 'COP';
  const money = new Intl.NumberFormat('es-CO', {
    style: 'currency',
    currency: moneda,
    maximumFractionDigits: 0,
  });

  const maxNeto = Math.max(...data.tendencia_7d.serie.map((s) => Math.max(s.neto, 1)), 1);

  return (
    <div className="space-y-6">
      {/* A. Encabezado: negocio + fecha de negocio + plan */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Dashboard financiero</h1>
          <p className="text-sm text-muted-foreground">
            {data.negocio?.nombre || data.negocio_nombre} · {data.negocio?.fecha}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">Plan</span>
          <Badge tone="neutral">{data.negocio?.plan || data.plan}</Badge>
          <Link
            href="/suscripcion"
            className="text-sm text-blue-600 hover:underline"
            aria-label="Ver estado de suscripción"
          >
            Suscripción
          </Link>
        </div>
      </div>

      {/* B. KPIs: cartera viva, vencida + %, recaudo hoy, neto hoy */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard label="Cartera viva" value={money.format(p.cartera_viva)} tone="success" money />
        <MetricCard
          label={`Cartera vencida (${p.pct_vencido}%)`}
          value={money.format(p.cartera_vencida)}
          tone={p.cartera_vencida > 0 ? 'warning' : 'default'}
          money
        />
        <MetricCard label="Recaudo hoy" value={money.format(p.recaudo_hoy)} tone="success" money />
        <MetricCard
          label={`Neto hoy (gastos ${money.format(p.gastos_hoy)})`}
          value={money.format(p.neto_hoy)}
          tone={p.neto_hoy >= 0 ? 'success' : 'danger'}
          money
        />
      </div>

      {/* F. Promesas + riesgo (conteos, sin PII) */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard label="Créditos activos" value={p.total_creditos_activos} />
        <MetricCard label="Clientes en mora" value={data.riesgo.clientes_en_mora} tone={data.riesgo.clientes_en_mora > 0 ? 'warning' : 'default'} />
        <MetricCard label="Promesas activas" value={data.riesgo.promesas_activas} />
        <MetricCard
          label="Promesas incumplidas"
          value={data.riesgo.promesas_incumplidas}
          tone={data.riesgo.promesas_incumplidas > 0 ? 'danger' : 'default'}
        />
      </div>

      {/* C. Tendencia 7 días */}
      <Card>
        <div className="p-4 border-b">
          <h2 className="text-lg font-semibold">Tendencia de recaudo (7 días)</h2>
        </div>
        <div className="p-4">
          <div className="flex items-end gap-1 h-32">
            {data.tendencia_7d.serie.map((s) => (
              <div key={s.fecha} className="flex-1 flex flex-col items-center gap-1">
                <div
                  className="w-full bg-blue-500 rounded-t"
                  style={{ height: `${(Math.max(s.neto, 0) / maxNeto) * 100}%`, minHeight: s.neto > 0 ? '4px' : '0' }}
                  title={`${s.fecha}: ${money.format(s.neto)}`}
                />
                <span className="text-[10px] text-muted-foreground">{s.fecha.slice(5)}</span>
              </div>
            ))}
          </div>
          <div className="mt-3 grid grid-cols-3 gap-2 text-center text-sm">
            <div>
              <p className="text-muted-foreground">Recaudo</p>
              <p className="font-semibold">{money.format(data.tendencia_7d.total_recaudo)}</p>
            </div>
            <div>
              <p className="text-muted-foreground">Reversal</p>
              <p className="font-semibold text-red-700">{money.format(data.tendencia_7d.total_reversal)}</p>
            </div>
            <div>
              <p className="text-muted-foreground">Neto</p>
              <p className="font-semibold text-green-700">{money.format(data.tendencia_7d.total_neto)}</p>
            </div>
          </div>
        </div>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        {/* D. Aging / riesgo */}
        <Card>
          <div className="p-4 border-b">
            <h2 className="text-lg font-semibold">Concentración de riesgo (aging)</h2>
          </div>
          <div className="p-4 grid grid-cols-2 sm:grid-cols-4 gap-2">
            {Object.entries(data.riesgo.aging_distribution).map(([bucket, d]) => (
              <div key={bucket} className="text-center p-2 rounded bg-muted/30">
                <p className="text-xs text-muted-foreground">{BUCKET_LABELS[bucket] ?? bucket}</p>
                <p className="text-lg font-bold">{d.count}</p>
                {d.amount > 0 && <p className="text-xs text-red-600">{money.format(d.amount)}</p>}
              </div>
            ))}
          </div>
        </Card>

        {/* E. Exposición por ruta (PII minimizada: sin cobrador) */}
        <Card>
          <div className="p-4 border-b">
            <h2 className="text-lg font-semibold">Exposición por ruta</h2>
          </div>
          {data.rutas.length === 0 ? (
            <p className="p-4 text-sm text-muted-foreground">Sin rutas activas</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b bg-muted/50">
                    <th className="px-4 py-2 text-left font-medium">Ruta</th>
                    <th className="px-4 py-2 text-right font-medium">Cartera</th>
                    <th className="px-4 py-2 text-right font-medium">Vencido</th>
                    <th className="px-4 py-2 text-right font-medium">Créditos</th>
                  </tr>
                </thead>
                <tbody>
                  {data.rutas.map((r) => (
                    <tr key={r.ruta_nombre} className="border-b last:border-0">
                      <td className="px-4 py-2">{r.ruta_nombre}</td>
                      <td className="px-4 py-2 text-right font-mono">{money.format(r.cartera)}</td>
                      <td className="px-4 py-2 text-right font-mono text-red-600">{money.format(r.vencido)}</td>
                      <td className="px-4 py-2 text-right">{r.creditos}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>

      {/* G. Accesos claros a las superficies read-only */}
      <Card>
        <div className="p-4 border-b">
          <h2 className="text-lg font-semibold">Explorar</h2>
        </div>
        <div className="grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-4">
          {ACCESOS.map((a) => (
            <Link
              key={a.href}
              href={a.href}
              className="rounded-lg border border-outline bg-surface p-3 transition-colors hover:bg-muted/40"
            >
              <p className="font-medium">{a.label}</p>
              <p className="text-xs text-muted-foreground">{a.desc}</p>
            </Link>
          ))}
        </div>
      </Card>
    </div>
  );
}
