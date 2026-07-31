# Contributing to Daily System

## Cómo contribuir

1. Fork el repositorio
2. Crea una rama (`feat/nueva-funcion` o `fix/bug-descripcion`)
3. Haz cambios
4. Ejecuta los gates:
   ```bash
   flutter analyze
   flutter test
   dart run tool/generate_design_tokens.dart --check
   ```
5. Abre un Pull Request

## Reglas

- No modificar fórmulas financieras sin aprobación
- No romper tests existentes
- Seguir el sistema de diseño (`design/tokens/`)
- Commits descriptivos en español

## Estructura de commits

```
feat(mobile): nueva pantalla de caja
fix(ui): corregir contraste en modo oscuro
docs: actualizar README
test(ui): agregar tests de accesibilidad
```
