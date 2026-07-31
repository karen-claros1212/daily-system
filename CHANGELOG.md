# Changelog

## [Unreleased]

### Added
- Sistema de diseño compartido (tokens JSON + Dart + CSS)
- 13 componentes Daily* reutilizables
- Adaptive icon y splash nativo para Android
- Prototipo web visual (4 páginas)
- Token generator con modo --check
- UI gate script y GitHub Actions workflow
- Brand identity: Concepto A (Ruta D) seleccionado

### Changed
- Login refactorizado con DailyLogo, sin strings técnicas
- Colores generados con 8-digit hex (0xFF prefix)
- README profesionalizado con estructura completa
- GitHub templates: issue forms, PR template, workflows

## [M3.6.6-F] - Migration V4
- JornadaSnapshot único, idempotencia obligatoria
- Hash reproducible SHA-256
- PDF recuperable desde snapshot

## [M3.6.6] - Domain model unification
- JornadaGuard, atomic payments, typed exceptions

## [M3.6.5] - Atomic post-close block
- JornadaCerradaException + PDF evidence

## [M3.6.4] - Integration test validation
- Transactional and offline emulator validation

## [M3.6.3] - Navigation enums fix
- Real SQLite data, ThemeExtension

## [M3.6.2] - IndexedStack navigation
- Real SQLite data + design tokens

## [M3.6.1] - Visual Alpha Premium
- Material 3 Expressive redesign

## [M3.6] - Flutter Offline Alpha
- APK construida con 10 pantallas

## [M3] - Suscripcion, Telegram, inversionista
- Planes y suscripciones
- Bot Telegram (cobrador/inversionista)
- Panel inversionista
- Reporte diario automático
- Límite de rutas por plan

## [M2] - Jornada, caja y Terminar Jornada
- Iniciar/cerrar/anular jornada
- Movimientos de caja
- Reporte de jornada

## [M1] - Hoja viva y pagos
- Calcular crédito, caja, pico y residuo
- Hoja viva del día
- Registrar/reversar pago
- Historial de pagos
- Renegociación básica

## [M0] - Fundación ejecutable
- Repo, AGENTS.md, Engram, Graphify
- Infraestructura Docker
- Backend FastAPI
- Database layer, modelos, schemas
- Routes, services, tests
