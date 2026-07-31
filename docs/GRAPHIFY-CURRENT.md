# GRAPHIFY-CURRENT.md

**Proyecto:** daily-system
**Última actualización:** 2026-07-31
**Graphify version:** 0.9.29 (skill 0.9.26)

---

## Graph Status

| Campo | Valor |
|---|---|
| **Graph built from** | ff889a80 (2026-07-28) |
| **Nodes** | 63 |
| **Edges** | 49 |
| **Communities** | 22 |
| **Extraction** | 92% EXTRACTED · 8% INFERRED |
| **Freshness** | STALE — needs re-run |

---

## Graph Nodes (63)

### Documents (4)
- AGENTS.md
- Implementation Plan
- Documento Maestro v1.3
- Status

### API Endpoints (8)
- API: Cliente
- API: Crédito
- API: Health
- API: Hoja Viva
- API: Jornada
- API: Negocio
- API: Pago
- API: Ruta

### Database Tables (10)
- Table: cliente
- Table: credito
- Table: cuota_programada
- Table: jornada
- Table: movimiento_caja
- Table: negocio
- Table: pago
- Table: ruta
- Table: usuario
- Table: (additional)

### Concepts (4)
- Calcular Crédito
- Calcular Caja
- graphify
- mcp

### Infrastructure (3)
- command
- Graphify Protocol
- Daily System

---

## God Nodes (most connected)

1. `Documento Maestro v1.3` - 11 edges
2. `Implementation Plan` - 9 edges
3. `command` - 5 edges
4. `graphify` - 4 edges
5. `Graphify Protocol` - 3 edges

---

## Next Steps

1. Re-run Graphify: `graphify . --update`
2. Use alternative backend (deepseek balance insufficient)
3. Update this file with fresh graph data
