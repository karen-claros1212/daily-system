# Graphify Protocol — Daily System

**Project:** daily-system
**File:** `docs/GRAPHIFY-PROTOCOL.md`
**Last updated:** 2026-07-28

---

## Configuración

- **Paquete:** graphifyy v0.9.26 (uv tool)
- **CLI:** `/home/jesus/.local/bin/graphify`
- **MCP:** `/home/jesus/.local/bin/graphify-mcp`
- **Skill:** `/home/jesus/.config/opencode/skills/graphify/SKILL.md`
- **Ruta del grafo:** `/home/jesus/proyectos/daily-system/graphify-out/`

---

## REGLA DE RAÍZ

Antes de ejecutar cualquier comando de Graphify:

```bash
cd /home/jesus/proyectos/daily-system
pwd
git rev-parse --show-toplevel
```

Ambos deben devolver `/home/jesus/proyectos/daily-system`.

---

## CUÁNDO EJECUTAR

Ejecutar `graphify . --update` después de:

- cerrar un hito (M0, M1, etc.)
- añadir o eliminar módulos
- modificar el schema de base de datos
- cambiar contratos API
- realizar una refactorización estructural
- preparar una auditoría de arquitectura

---

## COMANDOS

### Indexación completa (primera vez o después de cambios mayores)

```bash
cd /home/jesus/proyectos/daily-system
graphify .
```

### Indexación incremental (después de cambios menores)

```bash
cd /home/jesus/proyectos/daily-system
graphify . --update
```

### Re-clustering (después de añadir nodos)

```bash
cd /home/jesus/proyectos/daily-system
graphify cluster-only .
```

### Consulta del grafo

```bash
cd /home/jesus/proyectos/daily-system
graphify query "¿Cómo se relacionan los modelos financieros con los endpoints?"
```

### Camino entre nodos

```bash
cd /home/jesus/proyectos/daily-system
graphify path "calcular_credito" "hoja_viva"
```

### Explicación de nodo

```bash
cd /home/jesus/proyectos/daily-system
graphify explain "Credito"
```

---

## ARCHIVOS GENERADOS

| Archivo | Propósito | Tamaño típico |
|---|---|---|
| `graphify-out/graph.json` | Grafo raw (nodos + aristas) | 5-50 KB |
| `graphify-out/graph.html` | Visualización interactiva | 10-100 KB |
| `graphify-out/GRAPH_REPORT.md` | Reporte en lenguaje natural | 1-5 KB |
| `graphify-out/manifest.json` | Manifest de archivos indexados | 1-10 KB |
| `graphify-out/.graphify_root` | Raíz del proyecto indexado | 50 bytes |
| `graphify-out/.graphify_analysis.json` | Análisis interno | 1-5 KB |
| `graphify-out/cache/` | Cache de extracción | Variable |

---

## .gitignore

Los archivos de `graphify-out/` son regenerables y deben excluirse de Git:

```
graphify-out/
```

Conservar en `docs/` solamente un resumen pequeño y revisable si resulta útil para auditoría.

---

## MCP INTEGRATION

Graphify puede servir el grafo via MCP para consulta en tiempo real:

```bash
# Configurar en opencode.json del proyecto
{
  "mcp": {
    "graphify": {
      "type": "local",
      "command": [
        "/home/jesus/.local/share/uv/tools/graphifyy/bin/python3",
        "-m", "graphify.serve",
        "graphify-out/graph.json"
      ],
      "enabled": true
    }
  }
}
```

---

## DIFERENCIAS CON NEXUSCORP

| Aspecto | NexusCorp | Daily System |
|---|---|---|
| **Ruta del grafo** | `nexuscorp/graphify-out/` | `graphify-out/` |
| **MCP en opencode.json** | Sí (project-specific) | Sí (project-specific) |
| **Config global** | No | No |
| **Aislamiento** | Total (graphify-out separado) | Total (graphify-out separado) |
| **Nodos existentes** | 7,913 (sin aristas) | 7 (con aristas) |

---

## NO CONFUNDIR

- `graphify .` → indexa el directorio actual
- `graphify . --update` → re-indexa solo cambios
- `graphify cluster-only .` → re-clustering sin LLM
- `graphify query "..."` → consulta el grafo existente
- `graphify path "A" "B"` → camino más corto entre nodos
- `graphify explain "X"` → explicación de un nodo

---

## RESULTADO ACTUAL

- **Nodos:** 7
- **Aristas:** 9
- **Comunidades:** 2 (1 mostrada, 1 thin omitida)
- **Extracción:** 78% EXTRACTED · 22% INFERRED
- **Token cost:** 119 input · 212 output
- **Commit base:** 90493dbc

---

## CONCLUSIÓN

Graphify está configurado y operativo para Daily System. Cada ejecución genera su propio `graphify-out/` sin mezclar con NexusCorp ni otros proyectos.
