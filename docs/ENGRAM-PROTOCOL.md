# Engram Protocol — Daily System

**Project:** daily-system
**File:** `docs/ENGRAM-PROTOCOL.md`
**Last updated:** 2026-07-28

---

## Activación

```bash
cd /home/jesus/proyectos/daily-system
pwd
git rev-parse --show-toplevel
```

La raíz debe ser: `/home/jesus/proyectos/daily-system`

---

## REGLA OBLIGATORIA

Toda llamada `mem_*` que acepte `project` debe incluir explícitamente:

```
project: "daily-system"
```

No confiar únicamente en la detección automática por nombre de carpeta.

---

## PROTOCOLO DE INICIO DE SESIÓN

1. Confirma:
   - `pwd`
   - `git rev-parse --show-toplevel`
   - La raíz debe ser `/home/jesus/proyectos/daily-system`

2. Inicia o recupera contexto usando exclusivamente:
   - `project: "daily-system"`

3. Consulta:
   - estado actual
   - último hito
   - bloqueos
   - decisiones vigentes
   - siguiente paso

---

## PROTOCOLO DURANTE EL TRABAJO

Guarda memoria después de:

- una decisión de arquitectura
- una migración importante
- un endpoint terminado
- una corrección financiera
- un cambio de seguridad
- una prueba relevante
- un error cuya causa y solución deban conservarse
- un bloqueo
- un cambio en el orden de implementación
- un commit que cierre un hito

Cada observación debe incluir, cuando aplique:

- título preciso
- categoría
- decisión o avance
- razón
- archivos afectados
- pruebas ejecutadas
- resultado
- commit
- riesgos
- siguiente paso

### topic_key estables recomendados

Usa `topic_key` estable para actualizar el mismo asunto en vez de crear memorias duplicadas.

```
architecture/backend
architecture/sync
architecture/mobile
database/schema
security/route-isolation
finance/daily-close
finance/renewal
milestone/M0
milestone/M1
testing/current-status
blockers/current
next-step/current
```

---

## PROTOCOLO DE CIERRE DE SESIÓN

Antes de terminar cada sesión:

1. Ejecuta todas las pruebas aplicables.
2. Comprueba `git status`.
3. Guarda un resumen de sesión bajo:
   - `project: "daily-system"`
4. Registra:
   - qué quedó terminado
   - qué quedó parcialmente hecho
   - pruebas y resultados
   - errores pendientes
   - archivos principales modificados
   - último commit
   - siguiente acción exacta
5. Finaliza la sesión de Engram si la herramienta lo soporta.

---

## PROTOCOLO DE RECUPERACIÓN

Después de compactación, cambio de sesión o pérdida de contexto:

1. Recupera `mem_context` exclusivamente para:
   - `project: "daily-system"`
2. Lee `AGENTS.md`.
3. Lee `docs/ENGRAM-PROTOCOL.md`.
4. Revisa `git log` y `git status`.
5. Continúa desde `next-step/current`.

---

## NO GUARDAR EN ENGRAM

- tokens completos
- API keys
- contraseñas
- secretos硬coded
- datos sensibles del usuario

Guardar solo: decisiones, patrones, errores, configuraciones, avances.
