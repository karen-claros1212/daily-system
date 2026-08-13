'use client';

import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { IconLock } from '@/components/ui/icons';

interface ForbiddenProps {
  /** Rol de la sesión (para mostrar contexto, no se usa para autorizar). */
  rol?: string | null;
}

/**
 * Vista 403 controlada: una sesión válida con permisos insuficientes NO es
 * una sesión inexistente, así que NO se redirige al login. El backend sigue
 * siendo la autoridad; esta vista solo comunica el rechazo.
 */
export function Forbidden({ rol = null }: ForbiddenProps) {
  const router = useRouter();
  return (
    <div className="max-w-md mx-auto py-16 text-center space-y-4">
      <div className="flex justify-center">
        <IconLock size={40} aria-hidden="true" className="text-textSecondary" />
      </div>
      <h1 className="text-2xl font-bold">Acceso denegado</h1>
      <p className="text-textSecondary">
        Tu sesión está autenticada pero el rol
        {rol ? ` “${rol}”` : ''} no tiene permisos para ver esta sección.
      </p>
      <div className="flex justify-center gap-3 pt-2">
        <Button size="sm" onClick={() => router.push('/dashboard')}>
          Ir al panel principal
        </Button>
        <Button
          size="sm"
          variant="outline"
          onClick={async () => {
            await fetch('/api/auth/logout', { method: 'POST' });
            router.push('/');
          }}
        >
          Cerrar sesión
        </Button>
      </div>
    </div>
  );
}