import { execSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';

export interface SeedTokens {
  inversionista: string;
  administrador: string;
}

export interface SeedOutput {
  negocio_id: string;
  cobrador_id: string;
  ruta_id: string;
  inversionista_id: string;
  administrador_id: string;
  codigo_activacion: string;
  tokens: SeedTokens;
}

function readJwtKeys(): { priv: string; pub: string } {
  // Precedencia: env -> PEM files (/tmp/jwt_{priv,pub}.pem) -> fail-closed.
  const env = { ...process.env };
  if (env.AUTH_JWT_PRIVATE_KEY && env.AUTH_JWT_PUBLIC_KEY) {
    return { priv: env.AUTH_JWT_PRIVATE_KEY, pub: env.AUTH_JWT_PUBLIC_KEY };
  }
  const privPath = process.env.JWT_PRIV_PEM ?? '/tmp/jwt_priv.pem';
  const pubPath = process.env.JWT_PUB_PEM ?? '/tmp/jwt_pub.pem';
  try {
    const priv = readFileSync(privPath, 'utf-8').trim();
    const pub = readFileSync(pubPath, 'utf-8').trim();
    if (priv && pub) return { priv, pub };
  } catch {
    // fallthrough al fail-closed
  }
  throw new Error(
    'AUTH_JWT_PRIVATE_KEY / AUTH_JWT_PUBLIC_KEY requeridas: el seed mint los JWTs reales. ' +
      'Exportarlas o tener /tmp/jwt_priv.pem + /tmp/jwt_pub.pem.',
  );
}

/**
 * Ejecuta el seed reproducible del backend y devuelve el estado E2E:
 * negocio al_dia + 3 roles (COBRADOR/INVERSIONISTA/ADMINISTRADOR), ruta del
 * cobrador, codigo de activacion PENDING y JWTs reales de INVERSIONISTA y
 * ADMINISTRADOR firmados por el servidor (issue_token + AUTH_JWT_PRIVATE_KEY).
 * Idempotente: revoca dispositivos ACTIVE previos y regenera codigo en cada
 * invocacion, asi cada spec real arranca limpio.
 *
 * El JWT de COBRADOR NO sale del seed: el spec real-rbac lo obtiene por el
 * flujo de dispositivo real (activacion -> canje -> desafio -> JWT) porque el
 * indice unico ACTIVE por usuario solo deja un dispositivo del cobrador, y el
 * canje real lo crea.
 *
 * Requiere: python3, PYTHONPATH=apps/api, API_DATABASE_URL, Postgres arriba,
 * AUTH_JWT_PRIVATE_KEY / AUTH_JWT_PUBLIC_KEY.
 */
export function seedActivacion(): SeedOutput {
  // helpers/ (apps/web/e2e/helpers) -> ../../.. = apps/web -> ../../.. + la raiz.
  // Real: /repo/apps/web/e2e/helpers -> 4 niveles hasta /repo.
  const repo = path.resolve(__dirname, '..', '..', '..', '..');
  const seedPy = path.join(repo, 'apps', 'api', 'scripts', 'seed_web_integration.py');
  const tmp = path.join(tmpdir(), `web-e2e-real-${process.pid}-${Date.now()}.json`);
  const dbUrl = process.env.REAL_DB_URL ?? 'postgresql://postgres@127.0.0.1:5433/daily_web_e2e_test';
  const { priv, pub } = readJwtKeys();

  execSync(
    `PYTHONPATH=${path.join(repo, 'apps', 'api')} ` +
      `API_DATABASE_URL="${dbUrl}" DAILY_ENV=test ` +
      `python3 "${seedPy}" "${tmp}"`,
    {
      encoding: 'utf-8',
      env: {
        ...process.env,
        API_DATABASE_URL: dbUrl,
        DAILY_ENV: 'test',
        AUTH_JWT_PRIVATE_KEY: priv,
        AUTH_JWT_PUBLIC_KEY: pub,
      },
    },
  );
  return JSON.parse(readFileSync(tmp, 'utf-8')) as SeedOutput;
}

export function runSql(sql: string): void {
  const dbUrl = process.env.REAL_DB_URL ?? 'postgresql://postgres@127.0.0.1:5433/daily_web_e2e_test';
  execSync(`psql "${dbUrl}" -v ON_ERROR_STOP=1 -c "${sql.replace(/"/g, '\\"')}"`, {
    stdio: 'pipe',
  });
}
