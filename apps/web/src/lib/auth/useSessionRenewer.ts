'use client';

import { useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import type { SessionUser } from '@/lib/rbac';
import { renewSession } from '@/lib/auth/authClient';

/**
 * Ciclo de vida de renovación de sesión (Etapa 2, Commit 5).
 *
 * Con una sesión válida, programa una renovación proactiva del desafío
 * daily-auth-v1 antes de que el JWT/cookie caduque (el backend emite tokens de
 * 1 h; renovamos a los 50 min, dejando margen). La renovación pasa por el BFF
 * `/api/auth/web/desafio` + `/api/auth/session`, que revalidan el binding
 * completo del dispositivo en la base (estado ACTIVE, version_asignacion,
 * usuario, negocio, public_key_hash).
 *
 * Fallos de renovación (401) significan sesión revocada/bump de dispositivo o
 * token caducado: se cierra la sesión (cookie borrada) y se redirige al login.
 * Una sesión válida con permisos insuficientes NO dispara redirect: eso se
 * resuelve por capabilities en cada página (Forbidden 403 controlado).
 *
 * No es permisivo: no fuerza ninguna capacidad; solo refresca el TTL de la
 * cookie httpOnly que el BFF ya emitió.
 */

// Renovar a los 50 min de un token de 1 h (margen de 10 min).
const RENOVATE_AT_MS = 50 * 60 * 1000;

export function SessionRenewer({ session }: { session: SessionUser | null }) {
  const router = useRouter();
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    if (!session) return;

    const invalidateAndRedirect = async () => {
      try {
        await fetch('/api/auth/logout', { method: 'POST' });
      } finally {
        router.replace('/');
        router.refresh();
      }
    };

    let cancelled = false;
    const schedule = (ms: number) => {
      if (cancelled) return;
      timerRef.current = setTimeout(async () => {
        let ok = false;
        try {
          ok = await renewSession();
        } catch {
          ok = false;
        }
        if (cancelled) return;
        if (ok) {
          // Renovación exitosa: reprograma antes del próximo vencimiento.
          schedule(RENOVATE_AT_MS);
        } else {
          // 401/revocación/caducidad: sesión inválida -> al login.
          await invalidateAndRedirect();
        }
      }, ms);
    };
    schedule(RENOVATE_AT_MS);

    return () => {
      cancelled = true;
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [session, router]);

  return null;
}
