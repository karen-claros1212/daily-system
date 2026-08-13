'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { loginWithCode } from '@/lib/auth/authClient';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/field';
import { IconShield, IconKey } from '@/components/ui/icons';

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
    <div className="min-h-screen flex items-center justify-center bg-surface px-4">
      <div className="card-elevated w-full" style={{ maxWidth: '400px' }}>
        <div className="text-center mb-6">
          <div className="w-12 h-12 bg-tertiary text-primary rounded-md flex items-center justify-center mx-auto mb-4">
            <IconShield size={22} aria-hidden="true" />
          </div>
          <h2 id="loginTitle" className="text-xl font-bold">
            Panel Administrativo
          </h2>
          <p className="text-sm text-textSecondary mt-2">
            Ingrese el código de activación emitido por el administrador.
          </p>
        </div>

        <div className="space-y-4">
          <div>
            <Label htmlFor="activationCode">Código de activación</Label>
            <div className="relative">
              <IconKey
                size={15}
                aria-hidden="true"
                className="absolute left-3 top-1/2 -translate-y-1/2 text-textSecondary"
              />
              <Input
                id="activationCode"
                type="text"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                className="pl-9"
                placeholder="Código de un solo uso"
                aria-label="Código de activación"
                autoComplete="one-time-code"
              />
            </div>
          </div>

          <Button
            id="loginBtn"
            onClick={handleLogin}
            loading={loading}
            className="w-full"
          >
            {loading ? 'Autenticando...' : 'Ingresar'}
          </Button>

          {error && (
            <div id="loginError" className="text-sm text-error text-center">
              {error}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}