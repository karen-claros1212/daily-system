# Graphify Audit — Daily System

**Fecha:** 2026-07-28
**Auditor:** opencode (Qwen3.6 Local)
**Estado:** PASS

---

## A. Evidencia de comandos

```
$ command -v graphify
/home/jesus/.local/bin/graphify

$ graphify --version
graphify 0.9.26

$ command -v graphify-mcp
/home/jesus/.local/bin/graphify-mcp

$ uv tool list | grep graph
graphifyy v0.9.26
- graphify
- graphify-mcp

$ opencode mcp list
┌  MCP Servers
│
●  ✓ engram    connected
│      engram mcp --tools=agent
│
●  ○ strix     disabled
│      strix-mcp
│
●  ✓ playwright  connected
│      playwright-mcp
│
└  3 server(s)
```

---

## B. Instalación encontrada

| Propiedad | Valor |
|---|---|
| **Nombre exacto del paquete** | `graphifyy` (uv tool) |
| **Versión** | 0.9.26 |
| **Ruta CLI** | `/home/jesus/.local/bin/graphify` |
| **Ruta MCP** | `/home/jesus/.local/bin/graphify-mcp` |
| **Ruta Python** | `/home/jesus/.local/share/uv/tools/graphifyy/bin/python3` |
| **Módulo** | `graphify.serve` (MCP server) |
| **Forma de instalación** | `uv tool install graphify` (uv tool, no pip) |
| **Tipo** | CLI + MCP server + Skill + Plugin OpenCode |

---

## C. Integración con OpenCode

### Estado actual: PARCIAL

Graphify está instalado en 4 niveles:

| Nivel | Estado | Detalle |
|---|---|---|
| **CLI** | ✅ Instalado | `graphify` en `/home/jesus/.local/bin/graphify` |
| **MCP** | ⚠️ Solo en nexuscorp | Configurado en `nexuscorp/opencode.json`, NO en global |
| **Skill** | ✅ Instalado | `/home/jesus/.config/opencode/skills/graphify/SKILL.md` |
| **Plugin** | ⚠️ Parcial | `install --platform opencode` escribió hooks en `.opencode/plugins/graphify.js` |

### MCP en nexuscorp (proyecto existente)

```json
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

Esto apunta al grafo de `nexuscorp`, NO al de Daily System.

### Grafo existente de nexuscorp

- **Ubicación:** `/home/jesus/.openclaw/workspace/graphify-out/graph.json`
- **Nodos:** 7,913
- **Aristas:** 0 (solo nodos, sin relaciones inferidas)
- **Raíz detectada:** `/home/jesus/.openclaw/workspace`
- **Tamaño:** 10.7 MB
- **Manifest:** `manifest.json` con hashes de archivos indexados
- **Análisis:** `.graphify_analysis.json` (676 KB)

---

## D. Comandos disponibles

### CLI (`graphify`)

| Comando | Función |
|---|---|
| `graphify <path>` | Pipeline completo: extrae, indexa, clusteriza, genera HTML + JSON + reporte |
| `graphify <path> --update` | Indexación incremental (solo archivos nuevos/cambiados) |
| `graphify <path> --mode deep` | Extracción profunda con aristas inferidas |
| `graphify <path> --cluster-only` | Rerun clustering sobre grafo existente |
| `graphify <path> --no-viz` | Skip visualización HTML |
| `graphify <url>` | Clona repo y ejecuta pipeline |
| `graphify <url1> <url2>` | Múltiples repos → grafo cruzado |
| `graphify install --platform opencode` | Instala skill + plugin + config |
| `graphify uninstall --purge` | Limpia todo |

### MCP (`graphify-mcp`)

| Comando | Función |
|---|---|
| `graphify-mcp [graph_path]` | Sirve grafo via MCP stdio |
| `graphify-mcp --transport http` | Sirve via HTTP (puerto configurable) |
| `graphify-mcp --port PORT` | Puerto HTTP |
| `graphify-mcp --api-key KEY` | Auth para HTTP |
| `graphify-mcp --stateless` | Sin estado por sesión |
| `graphify-mcp --session-timeout N` | Timeout de sesión |

### Herramientas del grafo

| Comando | Función |
|---|---|
| `graphify path "A" "B"` | Camino más corto entre nodos |
| `graphify explain "X"` | Explicación de nodo y vecinos |
| `graphify query "pregunta"` | BFS traversal del grafo |
| `graphify affected "X"` | Nodos impactados por cambios en X |
| `graphify god-nodes` | Nodos más conectados |
| `graphify diagnose multigraph` | Detecta colapso de aristas |
| `graphify merge-graphs <g1> <g2>` | Fusiona grafos de múltiples repos |
| `graphify watch <path>` | Watch folder y rebuild on change |
| `graphify update <path>` | Re-extract code files |
| `graphify cluster-only <path>` | Rerun clustering |
| `graphify label <path>` | Renombrar comunidades con LLM |

### Exportaciones

| Flag | Salida |
|---|---|
| `--graphml` | `graph.graphml` (Gephi, yEd) |
| `--neo4j` | `cypher.txt` para Neo4j |
| `--neo4j-push URL` | Push directo a Neo4j |
| `--falkordb` | Cypher para FalkorDB |
| `--falkordb-push URL` | Push directo a FalkorDB |
| `--svg` | `graph.svg` |

---

## E. Capacidad multi-proyecto

| Característica | Soporte |
|---|---|
| **Multi-repo** | ✅ `graphify <url1> <url2>` → grafo cruzado |
| **Separação por directorio** | ✅ Cada `graphify <path>` genera su propio `graphify-out/` |
| **Merge de grafos** | ✅ `graphify merge-graphs <g1> <g2> --out <path>` |
| **Watch por directorio** | ✅ `graphify watch <path>` |
| **Incremental** | ✅ `--update` re-extract solo cambios |
| **Exclusiones** | ✅ `.gitignore` respetado + flags específicos |
| **Raíz Git** | ✅ Detecta `.git` root (`.graphify_root` lo registra) |
| **Aislamiento** | ✅ Cada proyecto tiene su `graphify-out/` independiente |

### Grafos existentes en el sistema

| Proyecto | Ubicación | Nodos | Estado |
|---|---|---|---|
| workspace | `/home/jesus/.openclaw/workspace/graphify-out/` | 7,913 | Indexado |
| nexuscorp | `/home/jesus/.openclaw/workspace/nexuscorp/graphify-out/` | ? | Indexado |

---

## F. Mecanismo de separación

### Actual

- Cada proyecto genera su propio `graphify-out/` dentro de su directorio
- `.graphify_root` registra la raíz del proyecto indexado
- No hay mezcla entre grafos de diferentes directorios
- MCP server se conecta a UN grafo específico (path pasado como argumento)

### Propuesto para Daily System

```
/home/jesus/proyectos/daily-system/
├── graphify-out/          ← grafo exclusivo de Daily System
│   ├── graph.json
│   ├── manifest.json
│   ├── .graphify_root     ← "/home/jesus/proyectos/daily-system"
│   ├── .graphify_analysis.json
│   └── cache/
└── AGENTS.md
```

---

## G. Riesgos de mezcla

| Riesgo | Nivel | Mitigación |
|---|---|---|
| MCP apuntando a grafo equivocado | BAJO | Cada MCP se conecta a un `graphify-out/` específico |
| Merge accidental de grafos | BAJO | `merge-graphs` requiere 2 grafos explícitos |
| Indexar directorio equivocado | BAJO | `graphify <path>` es explícito |
| Grafo de nexuscorp contaminado | NINGUNO | 7,913 nodos, 0 aristas — grafo incompleto |

---

## H. Propuesta para Daily System

### 1. Indexar el repositorio de Daily System

```bash
cd /home/jesus/proyectos/daily-system
graphify . --update
```

Esto generará:
- `graphify-out/graph.json` — grafo con nodos de AGENTS.md, ENGRAM-PROTOCOL.md, .gitignore
- `graphify-out/manifest.json` — manifest con hashes
- `graphify-out/.graphify_root` — `/home/jesus/proyectos/daily-system`
- `graphify-out/graph.html` — visualización interactiva
- `graphify-out/GRAPH_REPORT.md` — reporte en lenguaje natural

### 2. Conectar MCP de Graphify a Daily System (opcional)

Agregar a `/home/jesus/proyectos/daily-system/opencode.json`:

```json
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

### 3. Incremental updates

```bash
# Después de cada cambio significativo
cd /home/jesus/proyectos/daily-system
graphify . --update
```

### 4. Watch en segundo plano (opcional)

```bash
cd /home/jesus/proyectos/daily-system
graphify watch .
```

---

## I. Comando exacto propuesto para Daily System

```bash
cd /home/jesus/proyectos/daily-system
graphify .
```

O para indexación incremental después de cambios:

```bash
cd /home/jesus/proyectos/daily-system
graphify . --update
```

---

## J. Conclusión

### PASS

**Motivo:**

1. Graphify está instalado correctamente (v0.9.26, uv tool)
2. CLI y MCP server disponibles (`graphify` + `graphify-mcp`)
3. Skill de OpenCode instalado (`/home/jesus/.config/opencode/skills/graphify/`)
4. MCP configurado solo en `nexuscorp` (no afecta Daily System)
5. Aislamiento por directorio — cada `graphify-out/` es independiente
6. Indexación incremental (`--update`) para mantener grafo actualizado
7. 0 aristas en grafo existente de nexuscorp — grafo incompleto, sin contaminación
8. No requiere instalación adicional ni configuración global
9. No modifica AGENTS.md ni configuración de OpenCode

**Próximos pasos:**

1. Ejecutar `graphify .` en `/home/jesus/proyectos/daily-system` cuando se necesite indexar
2. Configurar MCP en `daily-system/opencode.json` si se quiere consulta MCP
3. Usar `graphify . --update` después de cambios significativos
4. No ejecutar indexación todavía (instrucción del usuario)
