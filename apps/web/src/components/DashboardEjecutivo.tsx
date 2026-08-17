'use client';

import { useEffect, useState } from 'react';
import { Card } from '@/components/ui/card';
import { MetricCard } from '@/components/ui/misc';
import { fetchDashboardEjecutivo, type DashboardEjecutivo } from '@/lib/api/client';

const BUCKET_LABELS: Record<string, string> = {
  CURRENT: 'Al día',
  '1-7': '1-7 días',
  '8-15': '8-15 días',
  '16-30': '16-30 días',
  '31-60': '31-60 días',
  '61-90': '61-90 días',
  '90+': '90+ días',
};

const SEVERIDAD_CLS: Record<string, string> = {
  critical: 'bg-red-100 text-red-800 border-red-300',
  warning: 'bg-amber-100 text-amber-800 border-amber-300',
  info: 'bg-blue-100 text-blue-800 border-blue-300',
};

export function DashboardEjecutivo() {
  const [data, setData] = useState<DashboardEjecutivo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;
    fetchDashboardEjecutivo()
      .then((d) => { if (!ignore) { setData(d); } })
      .catch((e) => { if (!ignore) setError(e instanceof Error ? e.message : 'Error cargando dashboard'); })
      .finally(() => { if (!ignore) setLoading(false); });
    return () => { ignore = true; };
  }, []);

  if (loading) return <div className="p-8 text-center text-muted-foreground">Cargando dashboard ejecutivo...</div>;
  if (error || !data) return <Card className="p-4 text-red-600">{error ?? 'Sin datos'}</Card>;

  const money = new Intl.NumberFormat('es-CO', { style: 'currency', currency: data.negocio.moneda || 'COP', maximumFractionDigits: 0 });
  const maxNeto = Math.max(...data.tendencia_7d.serie.map((s) => Math.max(s.neto, 1)), 1);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Dashboard ejecutivo</h1>
          <p className="text-sm text-muted-foreground">{data.negocio.nombre} · {data.fecha}</p>
        </div>
      </div>

      {data.alertas.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold mb-2">Requiere atención</h2>
          <div className="flex flex-wrap gap-2">
            {data.alertas.map((a) => (
              <span key={a.tipo} className={`inline-block rounded border px-3 py-1 text-sm ${SEVERIDAD_CLS[a.severidad] ?? SEVERIDAD_CLS.info}`}>
                {a.mensaje}
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard label="Cartera viva" value={money.format(data.hoy.cartera_vigente)} tone="success" money />
        <MetricCard
          label={`Cartera vencida (${data.hoy.pct_vencido}%)`}
          value={money.format(data.hoy.cartera_vencida)}
          tone={data.hoy.cartera_vencida > 0 ? 'warning' : 'default'}
          money
        />
        <MetricCard label="Recaudo hoy" value={money.format(data.hoy.recaudo_hoy)} tone="success" money />
        <MetricCard
          label={`Neto hoy (gastos ${money.format(data.hoy.gastos_hoy)})`}
          value={money.format(data.hoy.neto_hoy)}
          tone={data.hoy.neto_hoy >= 0 ? 'success' : 'danger'}
          money
        />
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard label="Rutas activas" value={data.operativo.rutas_activas} />
        <MetricCard label="Cobradores activos" value={data.operativo.cobradores_activos} />
        <MetricCard label="Créditos activos" value={data.operativo.creditos_activos} />
        <MetricCard
          label="Jornada cerrada hoy"
          value={data.operativo.jornada_cerrada_hoy ? 'Sí' : 'No'}
          tone={data.operativo.jornada_cerrada_hoy ? 'success' : 'warning'}
        />
      </div>

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
              <p className="font-semibold text-red-600">{money.format(data.tendencia_7d.total_reversal)}</p>
            </div>
            <div>
              <p className="text-muted-foreground">Neto</p>
              <p className="font-semibold text-green-600">{money.format(data.tendencia_7d.total_neto)}</p>
            </div>
          </div>
        </div>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
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
                    <tr key={r.ruta_id} className="border-b last:border-0">
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
    </div>
  );
}
