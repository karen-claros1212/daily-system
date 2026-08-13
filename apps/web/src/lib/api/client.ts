import type { components } from './generated';

export type Ruta = components['schemas']['RutaResponse'];
export type Jornada = components['schemas']['JornadaResponse'];
export type InversionistaSummary = components['schemas']['InversionistaSummaryResponse'];

export type DesafioAuth = components['schemas']['DesafioAuthResponse'];
export type CanjearDesafio = components['schemas']['CanjearDesafioResponse'];

export const API_BASE =
  process.env.API_BASE || 'http://localhost:8000';

async function parseJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new Error(`API error ${res.status}: ${body}`);
  }
  return res.json() as Promise<T>;
}

/** GET /api/jornadas (BFF: inyecta Bearer desde la cookie HttpOnly server-side). */
export function fetchJornadas(): Promise<Jornada[]> {
  return fetch('/api/jornadas', { cache: 'no-store' }).then((r) => parseJson<Jornada[]>(r));
}

/** GET /api/rutas (BFF). */
export function fetchRutas(): Promise<Ruta[]> {
  return fetch('/api/rutas', { cache: 'no-store' }).then((r) => parseJson<Ruta[]>(r));
}

/** GET /api/rutas/{id} (BFF). */
export function fetchRuta(id: string): Promise<Ruta> {
  return fetch(`/api/rutas/${id}`, { cache: 'no-store' }).then((r) => parseJson<Ruta>(r));
}

/** GET /api/inversionista/resumen via server component o BFF. */
export function fetchResumen(): Promise<InversionistaSummary> {
  return fetch('/api/inversionista/resumen', { cache: 'no-store' }).then((r) =>
    parseJson<InversionistaSummary>(r),
  );
}