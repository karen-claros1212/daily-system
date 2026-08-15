# Web UI Blueprint — Daily System

**Fecha:** 2026-07-31
**Estado:** ⚠️ **HISTÓRICO** — describe el prototipo estático MOCK (`design/prototypes/web/`), ya **no** es la fuente del panel web.

> ## ⚠️ ARCHIVADO — DOCUMENTO HISTÓRICO
>
> Este documento describe el **prototipo web visual (MOCK)** que precedió a la Web Premium.
> El panel web administrativo **productivo** vive en `apps/web/` (Next.js 16 · React 19 ·
> TypeScript · Tailwind) y tiene su propia documentación en [docs/ARCHITECTURE.md](../ARCHITECTURE.md)
> y [docs/STATUS.md](../STATUS.md). El prototipo MOCK de `design/prototypes/web/` se conserva
> como referencia de diseño (histórica), no como producto.
> Reconciliación documental 2026-08-15 — rama `product/web-premium-v1`.

---

## Arquitectura Visual

- **Sidebar** fija a la izquierda (240px) con navegación
- **Main content** flexible con CSS Grid
- **Tokens compartidos** desde `design/tokens/daily-system.tokens.json`
- **Responsive:** mobile-first con breakpoints compacto/medio/expandido

## Navegación

- Dashboard → Resumen ejecutivo
- Cartera → Lista de clientes con estados de mora
- Caja → Conciliación esperado vs contado
- Reportes → Jornadas y totales

## Responsive

- < 768px: sidebar colapsa a iconos
- Grid de métricas se adapta a 1 columna
- Tipografía escala con `clamp()`

## Componentes

- `MetricCard` — tarjeta de métrica con label y valor
- `StatusBadge` — indicador de estado con color + texto
- `ClientCard` — tarjeta de cliente con info y estado
- `RouteCard` — tarjeta de ruta con progreso
- `AlertCard` — alerta con icono y descripción

## Accesibilidad WCAG 2.2 AA

- Contraste mínimo 4.5:1 en todo texto
- Focus visible en todos los elementos interactivos
- Semántica HTML correcta (nav, main, header, h1-h3)
- Colores no son único indicador de estado

## Tokens

- Colores light/dark desde `daily-system.css`
- Shapes: 8px, 12px, 16px
- Spacing: 16px, 24px

## Diferencia prototipo vs productivo

| Aspecto | Prototipo (MOCK, histórico) | Productivo (`apps/web/`) |
|---|---|---|
| Datos | Estáticos en HTML | API backend (FastAPI) |
| Auth | Ninguna | Sesión httpOnly `daily_admin_token` → `/api/auth/me` |
| Routing | Links estáticos | Next.js App Router |
| Estado | Ninguno | React Server Components + server-side RBAC |
| Build | HTML + CSS puro | Next.js 16 + TypeScript + Tailwind |
| Tests | Ninguno | Playwright E2E (mock 107 + real 26) + a11y axe |
