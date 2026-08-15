'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  ApiError,
  registrarNegocio,
  type OnboardingNegocioResponse,
} from '@/lib/api/client';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/field';
import { IconShield, IconKey } from '@/components/ui/icons';

/** Minutos restantes hasta `expiraEl` (RFC3339) segun el reloj del cliente.
 * Devuelve null si no es parseable (el texto cae a la variante generica). */
function minutosRestantes(expiraEl: string | null | undefined): number | null {
  if (!expiraEl) return null;
  const fin = Date.parse(expiraEl);
  if (Number.isNaN(fin)) return null;
  const minutos = Math.ceil((fin - Date.now()) / 60_000);
  return minutos > 0 ? minutos : null;
}

/**
 * Alta de negocios (Etapa 3) — superficie Web PRE-sesion.
 *
 * Llama al contrato atomico POST /api/onboarding/negocios via BFF (publico):
 * el servidor crea Negocio + ADMINISTRADOR inicial + codigo de activacion en
 * una sola transaccion. El formulario NO pide negocio_id/rol/plan: el servidor
 * deriva todo (aislamiento de tenancy). En exito se muestra el codigo bootstrap
 * UNA vez y se guia al admin a completar el login Web existente.
 */
export function RegistroPage() {
  const router = useRouter();
  const [negocioNombre, setNegocioNombre] = useState('');
  const [nit, setNit] = useState('');
  const [adminNombre, setAdminNombre] = useState('');
  const [adminDocumento, setAdminDocumento] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [resultado, setResultado] = useState<OnboardingNegocioResponse | null>(null);

  async function handleRegistro() {
    setError('');
    if (!negocioNombre.trim()) {
      setError('Ingrese el nombre del negocio');
      return;
    }
    if (!adminNombre.trim()) {
      setError('Ingrese el nombre del administrador');
      return;
    }

    try {
      setLoading(true);
      const res = await registrarNegocio({
        nombre: negocioNombre.trim(),
        nit: nit.trim() || null,
        administrador: {
          nombre: adminNombre.trim(),
          documento: adminDocumento.trim() || null,
        },
      });
      setResultado(res);
    } catch (e: unknown) {
      if (e instanceof ApiError && e.status === 409) {
        setError('El NIT ya está registrado. Verifique el número o continúe sin él.');
      } else if (e instanceof ApiError && e.status === 422) {
        setError('Revise los datos del formulario e intente de nuevo.');
      } else {
        setError('No se pudo completar el registro. Intente de nuevo en unos momentos.');
      }
    } finally {
      setLoading(false);
    }
  }

  if (resultado) {
    const codigo = resultado.codigo_activacion;
    const venceEnMinutos = minutosRestantes(codigo.expira_el);
    return (
      <div className="min-h-screen flex items-center justify-center bg-surface px-4">
        <div className="card-elevated w-full" style={{ maxWidth: '440px' }}>
          <div className="text-center mb-6">
            <div className="w-12 h-12 bg-tertiary text-primary rounded-md flex items-center justify-center mx-auto mb-4">
              <IconShield size={22} aria-hidden="true" />
            </div>
            <h2 id="registroOkTitle" className="text-xl font-bold">
              Negocio creado
            </h2>
            <p className="text-sm text-textSecondary mt-2">
              <span className="font-semibold text-textPrimary">{resultado.negocio.nombre}</span> quedó
              registrado con <span className="font-semibold">{resultado.administrador.nombre}</span> como
              administrador.
            </p>
          </div>

          <div className="rounded-md bg-surface border p-4 mb-4" role="region" aria-label="Código de activación">
            <p className="text-sm font-semibold mb-2 flex items-center gap-2">
              <IconKey size={15} aria-hidden="true" />
              Código de activación
            </p>
            <p className="text-lg font-bold tracking-wider break-all select-all" id="activationCodeResult">
              {codigo.token}
            </p>
            <p className="text-xs text-textSecondary mt-2" id="activationCodeHint">
              {venceEnMinutos !== null
                ? `Código de un solo uso. Consérvelo: vence en ${venceEnMinutos} minutos y sirve para el primer ingreso al panel.`
                : 'Código de un solo uso. Es de un solo uso y expira; consérvelo para el primer ingreso al panel.'}
            </p>
          </div>

          <Button
            id="goToLoginBtn"
            onClick={() => router.push('/')}
            className="w-full"
          >
            Ir al inicio de sesión
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-surface px-4">
      <div className="card-elevated w-full" style={{ maxWidth: '440px' }}>
        <div className="text-center mb-6">
          <div className="w-12 h-12 bg-tertiary text-primary rounded-md flex items-center justify-center mx-auto mb-4">
            <IconShield size={22} aria-hidden="true" />
          </div>
          <h2 id="registroTitle" className="text-xl font-bold">
            Registre su negocio
          </h2>
          <p className="text-sm text-textSecondary mt-2">
            Cree su cuenta y obtenga el código de activación para el primer ingreso.
          </p>
        </div>

        <div className="space-y-4">
          <div>
            <Label htmlFor="negocioNombre">Nombre del negocio</Label>
            <Input
              id="negocioNombre"
              type="text"
              value={negocioNombre}
              onChange={(e) => setNegocioNombre(e.target.value)}
              placeholder="Ej: Distribuciones del Sur"
              aria-label="Nombre del negocio"
              autoComplete="organization"
              maxLength={255}
            />
          </div>

          <div>
            <Label htmlFor="nitNegocio">NIT (opcional)</Label>
            <Input
              id="nitNegocio"
              type="text"
              value={nit}
              onChange={(e) => setNit(e.target.value)}
              placeholder="Ej: 900123456"
              aria-label="NIT del negocio"
              autoComplete="off"
              maxLength={50}
            />
          </div>

          <hr className="border-borderColor" />

          <p className="text-sm font-semibold" id="adminSectionTitle">
            Administrador inicial
          </p>

          <div>
            <Label htmlFor="adminNombre">Nombre del administrador</Label>
            <Input
              id="adminNombre"
              type="text"
              value={adminNombre}
              onChange={(e) => setAdminNombre(e.target.value)}
              placeholder="Ej: María Pérez"
              aria-label="Nombre del administrador"
              autoComplete="name"
              maxLength={255}
            />
          </div>

          <div>
            <Label htmlFor="adminDocumento">Documento (opcional)</Label>
            <Input
              id="adminDocumento"
              type="text"
              value={adminDocumento}
              onChange={(e) => setAdminDocumento(e.target.value)}
              placeholder="Ej: CC 123456789"
              aria-label="Documento del administrador"
              maxLength={50}
            />
          </div>

          <Button
            id="registroBtn"
            onClick={handleRegistro}
            loading={loading}
            className="w-full"
          >
            {loading ? 'Creando negocio...' : 'Crear negocio y continuar'}
          </Button>

          {error && (
            <div id="registroError" className="text-sm text-error text-center" role="alert">
              {error}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
