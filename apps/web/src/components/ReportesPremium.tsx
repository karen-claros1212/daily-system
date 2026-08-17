'use client';

import { useState, useEffect } from 'react';
import { Card } from '@/components/ui/card';
import {
  fetchReporteResumen,
  fetchReporteRecaudo,
  fetchReporteAging,
  fetchReporteRutas,
  fetchReporteMovimientos,
  type ReporteResumen,
  type ReporteRecaudo,
  type ReporteAging,
  type ReporteRutas,
  type ReporteMovimientos,
} from '@/lib/api/client';

const money = new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 0 });
const BUCKET_LABELS: Record<string, string> = {
  CURRENT: 'Al día',
  '1-7': '1-7 días',
  '8-15': '8-15 días',
  '16-30': '16-30 días',
  '31-60': '31-60 días',
  '61-90': '61-90 días',
  '90+': '90+ días',
};

export function ReportesPremium() {
  const [periodo, setPeriodo] = useState('hoy');
  const [resumen, setResumen] = useState<ReporteResumen | null>(null);
  const [recaudo, setRecaudo] = useState<ReporteRecaudo | null>(null);
  const [aging, setAging] = useState<ReporteAging | null>(null);
  const [rutas, setRutas] = useState<ReporteRutas | null>(null);
  const [movimientos, setMovimientos] = useState<ReporteMovimientos | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;
    async function load() {
      try {
        setLoading(true);
        setError(null);
        const [r, rec, ag, rt, mv] = await Promise.all([
          fetchReporteResumen(periodo),
          fetchReporteRecaudo(periodo === 'hoy' ? '7d' : periodo),
          fetchReporteAging(),
          fetchReporteRutas(periodo),
          fetchReporteMovimientos(periodo),
        ]);
        if (!ignore) {
          setResumen(r);
          setRecaudo(rec);
          setAging(ag);
          setRutas(rt);
          setMovimientos(mv);
        }
      } catch (e) {
        if (!ignore) setError(e instanceof Error ? e.message : 'Error cargando reportes');
      } finally {
        if (!ignore) setLoading(false);
      }
    }
    load();
    return () => { ignore = true; };
  }, [periodo]);

  if (loading) return <div className="p-8 text-center text-muted-foreground">Cargando reportes...</div>;
  if (error) return <Card className="p-4 text-red-600">{error}</Card>;

  const maxRecaudo = recaudo ? Math.max(...recaudo.serie.map((s) => Math.max(s.recaudo, 1)), 1) : 1;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Reportes</h1>
        <select
          id="rep-periodo"
          value={periodo}
          onChange={(e) => setPeriodo(e.target.value)}
          className="border rounded px-3 py-2 text-sm bg-background"
        >
          <option value="hoy">Hoy</option>
          <option value="7d">Últimos 7 días</option>
          <option value="30d">Últimos 30 días</option>
        </select>
      </div>

      {resumen && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Card className="p-4">
            <p className="text-sm text-muted-foreground">Cartera vigente</p>
            <p className="text-2xl font-bold">{money.format(resumen.cartera_vigente)}</p>
          </Card>
          <Card className="p-4">
            <p className="text-sm text-muted-foreground">Cartera vencida</p>
            <p className="text-2xl font-bold text-red-600">{money.format(resumen.cartera_vencida)}</p>
            <p className="text-xs text-muted-foreground">{resumen.pct_vencido}% de la cartera</p>
          </Card>
          <Card className="p-4">
            <p className="text-sm text-muted-foreground">Recaudo del periodo</p>
            <p className="text-2xl font-bold text-green-600">{money.format(resumen.recaudo_periodo)}</p>
          </Card>
          <Card className="p-4">
            <p className="text-sm text-muted-foreground">Neto del periodo</p>
            <p className={`text-2xl font-bold ${resumen.neto_periodo >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {money.format(resumen.neto_periodo)}
            </p>
            <p className="text-xs text-muted-foreground">Gastos: {money.format(resumen.gastos_periodo)}</p>
          </Card>
        </div>
      )}

      {recaudo && recaudo.serie.length > 0 && (
        <Card>
          <div className="p-4 border-b">
            <h2 className="text-lg font-semibold">Tendencia de recaudo</h2>
          </div>
          <div className="p-4">
            <div className="flex items-end gap-1 h-32">
              {recaudo.serie.map((s) => (
                <div key={s.fecha} className="flex-1 flex flex-col items-center gap-1">
                  <div
                    className="w-full bg-blue-500 rounded-t"
                    style={{ height: `${(s.neto / maxRecaudo) * 100}%`, minHeight: s.neto > 0 ? '4px' : '0' }}
                    title={`${s.fecha}: ${money.format(s.neto)}`}
                  />
                  <span className="text-[10px] text-muted-foreground">{s.fecha.slice(5)}</span>
                </div>
              ))}
            </div>
            <div className="mt-3 grid grid-cols-3 gap-2 text-center text-sm">
              <div>
                <p className="text-muted-foreground">Recaudo</p>
                <p className="font-semibold">{money.format(recaudo.total_recaudo)}</p>
              </div>
              <div>
                <p className="text-muted-foreground">Reversal</p>
                <p className="font-semibold text-red-600">{money.format(recaudo.total_reversal)}</p>
              </div>
              <div>
                <p className="text-muted-foreground">Neto</p>
                <p className="font-semibold text-green-600">{money.format(recaudo.total_neto)}</p>
              </div>
            </div>
          </div>
        </Card>
      )}

      {aging && (
        <Card>
          <div className="p-4 border-b">
            <h2 className="text-lg font-semibold">Aging de cartera</h2>
          </div>
          <div className="p-4 grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2">
            {Object.entries(aging.buckets).map(([bucket, data]) => (
              <div key={bucket} className="text-center p-2 rounded bg-muted/30">
                <p className="text-xs text-muted-foreground">{BUCKET_LABELS[bucket] ?? bucket}</p>
                <p className="text-lg font-bold">{data.count}</p>
                {data.amount > 0 && (
                  <p className="text-xs text-red-600">{money.format(data.amount)}</p>
                )}
              </div>
            ))}
          </div>
        </Card>
      )}

      {rutas && rutas.rutas.length > 0 && (
        <Card>
          <div className="p-4 border-b">
            <h2 className="text-lg font-semibold">Rendimiento por rutas</h2>
          </div>
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
                {rutas.rutas.map((r) => (
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
        </Card>
      )}

      {movimientos && movimientos.por_tipo.length > 0 && (
        <Card>
          <div className="p-4 border-b">
            <h2 className="text-lg font-semibold">Gastos y movimientos</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/50">
                  <th className="px-4 py-2 text-left font-medium">Tipo</th>
                  <th className="px-4 py-2 text-right font-medium">Total</th>
                  <th className="px-4 py-2 text-right font-medium">Operaciones</th>
                </tr>
              </thead>
              <tbody>
                {movimientos.por_tipo.map((t) => (
                  <tr key={t.tipo} className="border-b last:border-0">
                    <td className="px-4 py-2">{t.tipo}</td>
                    <td className="px-4 py-2 text-right font-mono">{money.format(t.total)}</td>
                    <td className="px-4 py-2 text-right">{t.count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
