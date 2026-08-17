'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { FormField } from '@/components/ui/field';
import { fetchCobranzaDetalle, crearPromesa, type CobranzaDetalle } from '@/lib/api/client';

const money = new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 0 });

export function CobranzaDetallePage({ creditoId }: { creditoId: string }) {
  const [data, setData] = useState<CobranzaDetalle | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showPromesaForm, setShowPromesaForm] = useState(false);
  const [promesaFecha, setPromesaFecha] = useState('');
  const [promesaMonto, setPromesaMonto] = useState('');
  const [promesaNota, setPromesaNota] = useState('');
  const [promesaBusy, setPromesaBusy] = useState(false);
  const [promesaError, setPromesaError] = useState<string | null>(null);
  const [promesaOk, setPromesaOk] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    let ignore = false;
    async function load() {
      try {
        setLoading(true);
        setError(null);
        const d = await fetchCobranzaDetalle(creditoId);
        if (!ignore) setData(d);
      } catch (e) {
        if (!ignore) setError(e instanceof Error ? e.message : 'Error cargando detalle');
      } finally {
        if (!ignore) setLoading(false);
      }
    }
    load();
    return () => { ignore = true; };
  }, [creditoId, refreshKey]);

  const handleCrearPromesa = async () => {
    setPromesaBusy(true);
    setPromesaError(null);
    setPromesaOk(false);
    try {
      await crearPromesa(creditoId, {
        amount: parseInt(promesaMonto, 10),
        promised_date: promesaFecha,
        nota: promesaNota || undefined,
      });
      setPromesaOk(true);
      setShowPromesaForm(false);
      setPromesaFecha('');
      setPromesaMonto('');
      setPromesaNota('');
      setRefreshKey((k) => k + 1);
    } catch (e) {
      setPromesaError(e instanceof Error ? e.message : 'Error creando promesa');
    } finally {
      setPromesaBusy(false);
    }
  };

  if (loading) return <div className="p-8 text-center text-muted-foreground">Cargando...</div>;
  if (error) return <Card className="p-4 text-red-600">{error}</Card>;
  if (!data) return null;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <Link href="/cobranza" className="text-sm text-muted-foreground hover:text-foreground">← Volver a Cobranza</Link>
          <h1 className="text-2xl font-bold mt-1">{data.cliente_nombre || 'Crédito'}</h1>
          <p className="text-sm text-muted-foreground">{data.ruta_nombre} · {data.cobrador_nombre || '—'}</p>
        </div>
        <Badge tone={data.days_past_due > 30 ? 'danger' : data.days_past_due > 0 ? 'warning' : 'neutral'}>
          {data.aging_bucket} · {data.days_past_due} días
        </Badge>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card className="p-4">
          <p className="text-sm text-muted-foreground">Saldo total</p>
          <p className="text-2xl font-bold">{money.format(data.saldo)}</p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted-foreground">Monto vencido</p>
          <p className="text-2xl font-bold text-red-600">{money.format(data.overdue_amount)}</p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted-foreground">Cuotas vencidas</p>
          <p className="text-2xl font-bold">{data.overdue_installments}</p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted-foreground">Cuotas pagadas</p>
          <p className="text-2xl font-bold">{data.cuotas_pagadas}/{data.n_cuotas}</p>
        </Card>
      </div>

      {data.oldest_unpaid_due_date && (
        <Card className="p-4">
          <p className="text-sm text-muted-foreground">Primera obligación vencida</p>
          <p className="text-lg font-semibold">{new Date(data.oldest_unpaid_due_date).toLocaleDateString('es-CO')}</p>
        </Card>
      )}

      {data.obligaciones_vencidas.length > 0 && (
        <Card>
          <div className="p-4 border-b">
            <h2 className="text-lg font-semibold">Obligaciones vencidas ({data.obligaciones_vencidas.length})</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/50">
                  <th className="px-4 py-2 text-left font-medium">#</th>
                  <th className="px-4 py-2 text-left font-medium">Vencimiento</th>
                  <th className="px-4 py-2 text-right font-medium">Monto</th>
                  <th className="px-4 py-2 text-left font-medium">Estado</th>
                </tr>
              </thead>
              <tbody>
                {data.obligaciones_vencidas.map((c) => (
                  <tr key={c.numero} className="border-b last:border-0">
                    <td className="px-4 py-2">{c.numero}</td>
                    <td className="px-4 py-2">{new Date(c.fecha_vencimiento).toLocaleDateString('es-CO')}</td>
                    <td className="px-4 py-2 text-right font-mono">{money.format(c.monto)}</td>
                    <td className="px-4 py-2"><Badge tone="warning">{c.estado}</Badge></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {data.pagos_recientes.length > 0 && (
        <Card>
          <div className="p-4 border-b">
            <h2 className="text-lg font-semibold">Pagos recientes</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/50">
                  <th className="px-4 py-2 text-left font-medium">Fecha</th>
                  <th className="px-4 py-2 text-left font-medium">Tipo</th>
                  <th className="px-4 py-2 text-right font-medium">Monto</th>
                </tr>
              </thead>
              <tbody>
                {data.pagos_recientes.map((p) => (
                  <tr key={p.id} className="border-b last:border-0">
                    <td className="px-4 py-2">{p.recibido_el ? new Date(p.recibido_el).toLocaleDateString('es-CO') : '—'}</td>
                    <td className="px-4 py-2"><Badge tone={p.tipo === 'PAYMENT' ? 'success' : 'danger'}>{p.tipo}</Badge></td>
                    <td className="px-4 py-2 text-right font-mono">{money.format(p.monto)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      <Card>
        <div className="p-4 border-b flex items-center justify-between">
          <h2 className="text-lg font-semibold">Promesas de pago</h2>
          <Button size="sm" onClick={() => { setShowPromesaForm(!showPromesaForm); setPromesaError(null); setPromesaOk(false); }}>
            {showPromesaForm ? 'Cancelar' : '+ Registrar promesa'}
          </Button>
        </div>

        {showPromesaForm && (
          <div className="p-4 space-y-4 border-b">
            <div className="grid gap-4 sm:grid-cols-2">
              <FormField id="promesa-fecha" label="Fecha comprometida">
                <Input id="promesa-fecha" type="date" value={promesaFecha} onChange={(e) => setPromesaFecha(e.target.value)} />
              </FormField>
              <FormField id="promesa-monto" label="Monto (COP)">
                <Input id="promesa-monto" type="number" min="1" value={promesaMonto} onChange={(e) => setPromesaMonto(e.target.value)} />
              </FormField>
            </div>
            <FormField id="promesa-nota" label="Nota (opcional)">
              <Input id="promesa-nota" placeholder="Ej: paga viernes en efectivo" value={promesaNota} onChange={(e) => setPromesaNota(e.target.value)} />
            </FormField>
            {promesaError && <p className="text-sm text-red-600">{promesaError}</p>}
            {promesaOk && <p className="text-sm text-green-600">Promesa registrada correctamente</p>}
            <Button onClick={handleCrearPromesa} disabled={promesaBusy || !promesaFecha || !promesaMonto}>
              {promesaBusy ? 'Guardando...' : 'Confirmar promesa'}
            </Button>
          </div>
        )}

        <div className="p-4">
          {data.promesas.length === 0 ? (
            <p className="text-sm text-muted-foreground">Sin promesas registradas</p>
          ) : (
            <div className="space-y-2">
              {data.promesas.map((p) => (
                <div key={p.id} className="flex items-center justify-between p-3 rounded bg-muted/30">
                  <div>
                    <p className="text-sm font-medium">{money.format(p.amount)} · {new Date(p.promised_date).toLocaleDateString('es-CO')}</p>
                    {p.nota && <p className="text-xs text-muted-foreground">{p.nota}</p>}
                  </div>
                  <Badge tone={p.estado === 'ACTIVE' ? 'warning' : p.estado === 'FULFILLED' ? 'success' : p.estado === 'BROKEN' ? 'danger' : 'neutral'}>
                    {p.estado}
                  </Badge>
                </div>
              ))}
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}
