# Web UI Blueprint — Daily System

**Fecha:** 2026-07-31
**Estado:** Prototipo visual (no aplicación productiva)

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

| Aspecto | Prototipo | Productivo |
|---|---|---|
| Datos | Estáticos en HTML | API backend |
| Auth | Ninguna | JWT + session |
| Routing | Links estáticos | React Router / Next.js |
| Estado | Ninguno | Zustand / Redux |
| Build | HTML + CSS puro | Vite / Next.js |
