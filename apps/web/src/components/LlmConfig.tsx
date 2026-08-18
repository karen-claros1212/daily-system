'use client';

import { useCallback, useEffect, useState } from 'react';
import {
  ApiError,
  deleteLlmCredential,
  fetchLlmProviders,
  setLlmCredential,
  testLlmProvider,
  updateLlmConfig,
  type LLMProviderList,
  type LLMProviderStatus,
  type LLMProviderTest,
} from '@/lib/api/client';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button, Flash, LoadingState } from '@/components/ui/button';
import { IconLock, IconSparkle } from '@/components/ui/icons';

/** Badge de fuente de credencial (BYOK / Plataforma / No disponible). */
function SourceBadge({ p }: { p: LLMProviderStatus }) {
  if (p.credential_source === 'TENANT_BYOK') {
    return (
      <Badge tone="primary" dot>
        BYOK
      </Badge>
    );
  }
  if (p.credential_source === 'PLATFORM_MANAGED') {
    return (
      <Badge tone="info" dot>
        Plataforma
      </Badge>
    );
  }
  return (
    <Badge tone="neutral">
      No disponible
    </Badge>
  );
}

function CapabilitiesBadges({ p }: { p: LLMProviderStatus }) {
  const caps: [string, boolean][] = [
    ['text', p.capabilities.text],
    ['tools', p.capabilities.tools],
    ['structured', p.capabilities.structured_output],
    ['vision', p.capabilities.vision],
    ['streaming', p.capabilities.streaming],
  ];
  return (
    <div className="flex flex-wrap gap-1.5">
      {caps
        .filter(([, on]) => on)
        .map(([label]) => (
          <span key={label} className="text-xs text-textSecondary">
            {label}
          </span>
        ))}
    </div>
  );
}

/** Panel de configuración de un provider (model + API key + test). */
function ProviderPanel({
  provider,
  onSaved,
}: {
  provider: LLMProviderStatus;
  onSaved: () => void;
}) {
  const [model, setModel] = useState(provider.model ?? '');
  const [apiKey, setApiKey] = useState('');
  const [showKey, setShowKey] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ tone: 'success' | 'error'; text: string } | null>(null);
  const [testResult, setTestResult] = useState<LLMProviderTest | null>(null);

  const saveConfig = async () => {
    setBusy(true);
    setMsg(null);
    try {
      await updateLlmConfig(provider.provider, {
        model: model || undefined,
        enabled: 1,
      });
      setMsg({ tone: 'success', text: 'Configuración guardada' });
      onSaved();
    } catch (e) {
      setMsg({ tone: 'error', text: e instanceof Error ? e.message : 'Error al guardar' });
    } finally {
      setBusy(false);
    }
  };

  const saveKey = async () => {
    if (!apiKey.trim()) return;
    setBusy(true);
    setMsg(null);
    try {
      const r = await setLlmCredential(provider.provider, apiKey);
      // Vaciar el input inmediatamente: la clave no persiste en el client.
      setApiKey('');
      setShowKey(false);
      setMsg({
        tone: 'success',
        text: `Credencial guardada (${r.key_hint ?? 'ok'})`,
      });
      onSaved();
    } catch (e) {
      setMsg({ tone: 'error', text: e instanceof Error ? e.message : 'Error al guardar la clave' });
    } finally {
      setBusy(false);
    }
  };

  const removeKey = async () => {
    setBusy(true);
    setMsg(null);
    try {
      const r = await deleteLlmCredential(provider.provider);
      setMsg({
        tone: 'success',
        text:
          r.credential_source === 'PLATFORM_MANAGED'
            ? 'BYOK eliminado (cae a Plataforma)'
            : 'BYOK eliminado (no disponible)',
      });
      onSaved();
    } catch (e) {
      setMsg({ tone: 'error', text: e instanceof Error ? e.message : 'Error al eliminar' });
    } finally {
      setBusy(false);
    }
  };

  const runTest = async () => {
    setBusy(true);
    setMsg(null);
    try {
      const r = await testLlmProvider(provider.provider);
      setTestResult(r);
      setMsg(
        r.status === 'OK'
          ? { tone: 'success', text: `Conexión OK (${r.latency_ms} ms)` }
          : { tone: 'error', text: `Test: ${r.status}` },
      );
    } catch (e) {
      setMsg({ tone: 'error', text: e instanceof Error ? e.message : 'Error en el test' });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mt-3 pt-3 border-t border-outline space-y-3">
      <div className="flex flex-col sm:flex-row gap-3">
        <label className="flex-1 text-sm">
          <span className="text-textSecondary">Modelo</span>
          <input
            type="text"
            value={model}
            onChange={(e) => setModel(e.target.value)}
            className="mt-1 w-full rounded-md border border-outline bg-surface px-3 py-2 text-sm"
            placeholder={provider.model ?? 'modelo por defecto'}
          />
        </label>
        <div className="flex items-end gap-2">
          <Button size="sm" onClick={saveConfig} disabled={busy}>
            Guardar config
          </Button>
          <Button size="sm" variant="outline" onClick={runTest} disabled={busy}>
            Test conexión
          </Button>
        </div>
      </div>

      {provider.credential_source === 'TENANT_BYOK' ? (
        <div className="flex items-center justify-between gap-2">
          <div className="text-sm">
            <span className="text-textSecondary">Clave BYOK: </span>
            <code className="text-xs">{provider.key_hint}</code>
          </div>
          <Button size="sm" variant="ghost" onClick={removeKey} disabled={busy}>
            Eliminar BYOK
          </Button>
        </div>
      ) : (
        <div className="flex flex-col sm:flex-row sm:items-center gap-2">
          <Button size="sm" variant="outline" onClick={() => setShowKey((v) => !v)} disabled={busy}>
            {showKey ? 'Cancelar' : 'Añadir / cambiar BYOK'}
          </Button>
        </div>
      )}

      {showKey && (
        <div className="flex flex-col sm:flex-row gap-2">
          <label className="flex-1 text-sm">
            <span className="text-textSecondary">API key</span>
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              autoComplete="off"
              className="mt-1 w-full rounded-md border border-outline bg-surface px-3 py-2 text-sm"
              placeholder="sk-…"
            />
          </label>
          <div className="flex items-end">
            <Button size="sm" onClick={saveKey} disabled={busy || !apiKey.trim()}>
              Guardar clave
            </Button>
          </div>
        </div>
      )}

      {msg && (
        <Flash tone={msg.tone === 'success' ? 'success' : 'error'}>{msg.text}</Flash>
      )}
      {testResult && testResult.status !== 'OK' && testResult.detail && (
        <p className="text-xs text-textSecondary">Detalle: {testResult.detail}</p>
      )}
    </div>
  );
}

/**
 * Superficie de Configuración IA (W10 — Provider Gateway Multi-LLM + BYOK).
 *
 * EL BACKEND ES LA AUTORIDAD: el catálogo, las capacidades y la fuente de
 * credencial salen de GET /api/llm/providers. La UI solo refleja y muta vía
 * BFF. La API key vive en un input type=password transitorio: NO localStorage,
 * NO cookie, NO re-render de la clave guardada (solo key_hint).
 */
export function LlmConfig() {
  const [data, setData] = useState<LLMProviderList | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<{ status: number; message: string } | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setData(await fetchLlmProviders());
      setError(null);
    } catch (e) {
      const status = e instanceof ApiError ? e.status : 0;
      setError({ status, message: e instanceof Error ? e.message : 'Error al cargar' });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  if (loading) return <LoadingState />;

  if (error?.status === 403) {
    return (
      <div className="max-w-md mx-auto py-16 text-center space-y-4">
        <div className="flex justify-center">
          <IconLock size={40} aria-hidden="true" className="text-textSecondary" />
        </div>
        <h1 className="text-2xl font-bold">Acceso denegado</h1>
        <p className="text-textSecondary">Tu rol no puede gestionar la configuración IA.</p>
      </div>
    );
  }
  if (error) {
    return (
      <div className="space-y-4">
        <Flash tone="error">No se pudo cargar la configuración IA.</Flash>
        <Button size="sm" onClick={() => { setLoading(true); void load(); }}>
          Reintentar
        </Button>
      </div>
    );
  }
  if (!data) return null;

  return (
    <div className="space-y-4 max-w-3xl">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <IconSparkle size={22} aria-hidden="true" />
          Configuración IA
        </h1>
        <p className="text-sm text-textSecondary mt-1">
          Proveedores LLM del negocio. La clave BYOK se cifra en el servidor; aquí solo
          se muestra una pista segura.
        </p>
      </div>

      <div className="space-y-3">
        {data.providers.map((p) => (
          <Card key={p.provider} padding="md">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
              <div className="flex items-center gap-3">
                <div>
                  <div className="font-semibold">{p.provider}</div>
                  <div className="text-xs text-textSecondary">
                    {p.type === 'openai-compatible' ? 'OpenAI-compatible' : p.protocol ?? 'native'}
                  </div>
                </div>
                <SourceBadge p={p} />
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-textSecondary">
                  {p.model ?? '—'}
                </span>
                <Button
                  size="sm"
                  variant="ghost"
                  aria-expanded={expanded === p.provider}
                  onClick={() => setExpanded(expanded === p.provider ? null : p.provider)}
                >
                  {expanded === p.provider ? 'Cerrar' : 'Configurar'}
                </Button>
              </div>
            </div>
            <div className="mt-2">
              <CapabilitiesBadges p={p} />
            </div>
            {expanded === p.provider && (
              <ProviderPanel provider={p} onSaved={() => void load()} />
            )}
          </Card>
        ))}
      </div>

      <p className="text-xs text-textSecondary">
        Endpoint profiles (OpenAI-compatible genérico): {data.endpoint_profiles.map((e) => e.label).join(', ') || 'ninguno'}
      </p>
    </div>
  );
}
