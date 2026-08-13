'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { loginWithCode } from '@/lib/auth/authClient';

/**
 * Login Web con el contrato canonico del backend (sin PIN, sin HMAC):
 *  1. El ADMINISTRADOR emite codigo de activacion (POST /api/activaciones/codigos).
 *  2. El navegador genera/recupera su par EC P-256 (privada no-extractable,
 *     IndexedDB) y activa el dispositivo contra /api/activaciones/desafio.
 *  3. Firma el payload daily-v1 y /api/activaciones/canjear devuelve el
 *     bootstrap al BFF (este lo usa en memoria para el primer desafio).
 *  4. Firma el payload daily-auth-v1 y /api/auth/session setea la cookie
 *     httpOnly daily_admin_token.
 * La privada nunca abandona el navegador; el backend nunca ve PIN.
 */
export function LoginPage() {
  const router = useRouter();
  const [code, setCode] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleLogin() {
    setError('');
    const trimmed = code.trim();
    if (!trimmed) {
      setError('Ingrese el código de activación');
      return;
    }

    try {
      setLoading(true);
      const ok = await loginWithCode(trimmed);
      if (!ok) {
        setError('No se pudo autenticar el dispositivo');
        return;
      }
      // cookie httpOnly ya emitida por el BFF; navega al dashboard
      router.push('/dashboard');
      router.refresh();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Error al autenticar');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-surface">
      <div className="bg-white rounded-lg p-8 shadow-sm border border-outline" style={{ maxWidth: '400px', width: '100%' }}>
        <div className="text-center mb-6">
          <div className="w-12 h-12 bg-tertiary text-primary rounded-md flex items-center justify-center font-bold text-xl mx-auto mb-4">
            D
          </div>
          <h2 id="loginTitle" className="text-xl font-bold">Panel Administrativo</h2>
          <p className="text-sm text-text-secondary mt-2">
            Ingrese el código de activación emitido por el administrador.
          </p>
        </div>

        <div className="space-y-4">
          <div>
            <label htmlFor="activationCode" className="block text-sm text-text-secondary mb-1">Código de activación</label>
            <input
              id="activationCode"
              type="text"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              className="input"
              placeholder="Código de un solo uso"
              aria-label="Código de activación"
            />
          </div>

          <button
            id="loginBtn"
            onClick={handleLogin}
            disabled={loading}
            className="btn btn-primary w-full"
          >
            {loading ? 'Autenticando...' : 'Ingresar'}
          </button>

          {error && <div id="loginError" className="text-sm text-error text-center">{error}</div>}
        </div>
      </div>
    </div>
  );
}