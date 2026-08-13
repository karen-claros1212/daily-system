"""Exporta el contrato OpenAPI de Daily System API a apps/api/openapi.json.

Reproducible y offline: no requiere que el servidor esté corriendo. Se levanta
la app con una base sqlite en memoria y se serializa app.openapi().

Uso:
    cd apps/api && python scripts/export_openapi.py
"""

import json
import os
import sys
from pathlib import Path

os.environ["API_DATABASE_URL"] = os.getenv(
    "API_DATABASE_URL", "sqlite:///:memory:"
)

_API_DIR = str(Path(__file__).resolve().parent.parent)
if _API_DIR not in sys.path:
    sys.path.insert(0, _API_DIR)

from src.main import app  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "openapi.json"


def main() -> None:
    spec = app.openapi()
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(spec, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"OpenAPI exportado: {OUT} ({len(spec.get('paths', {}))} paths)")


if __name__ == "__main__":
    main()
