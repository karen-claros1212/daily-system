# Graphify Status — Daily System

> ## Nota (2026-08-15)
>
> Documento **regenerable** (clase E): el grafo describe un snapshot histórico
> (737371d). `graphify-out/` se regenera con `graphify .` tras cambios estructurales;
> ver [AGENTS.md](../AGENTS.md) §Graphify. Reconciliación documental 2026-08-15 —
> rama `product/web-premium-v1`, HEAD `bbb3e102`.

**Fecha:** 2026-07-31
**SHA:** 737371dbb89cdc49ef7961ef43347ca416edbf54d
**Graphify version:** 0.9.29 (skill 0.9.26)

---

## Graph Status

| Campo | Valor |
|---|---|
| **Graph built from** | 737371dbb89cdc49ef7961ef43347ca416edbf54d |
| **AST extraction** | 26/26 uncached files (100%) |
| **Semantic extraction** | 77/77 files |
| **Status** | PARTIAL — deepseek balance insufficient for full graph |

---

## Previous Graph (2026-07-31)

| Campo | Valor |
|---|---|
| **Nodes** | 63 |
| **Edges** | 49 |
| **Communities** | 22 |
| **Extraction** | 92% EXTRACTED |

---

## Next Steps

1. Re-run Graphify when deepseek balance is replenished
2. Install tree_sitter_sql for SQL analysis: `pip install "graphifyy[sql]"`
3. Update this file with fresh graph data

## Known Warnings

- 3 source files produced zero nodes (Contents.json x3)
- 1 .sql file missing tree_sitter_sql dependency
- 77 files omitted from semantic extraction (deepseek balance)
