# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/);
versiones según [SemVer](https://semver.org/lang/es/).

## [Sin publicar]

### Agregado

- `yutani env-check` (`yutani.entorno`): herramientas del sistema con la versión mínima que exige el ecosistema (gcc ≥ 10 por `-fanalyzer`, Python ≥ 3.11, uv ≥ 0.4.27 por `dependency-groups`; make, gdb, valgrind y clang presentes), la carpeta de `uv tool` en el PATH y las variables P1 definidas (sin mostrar los PIN). Mismo sobre JSON que `doctor` (Ola 26).

## [0.1.0] - 2026-09-28

### Agregado

- `yutani.cli`: `crear_app`, `TyperConErrores`, `opcion_version`, `describir_error`
  y `CONTEXTO` (contrato de LINEAMIENTOS §3.2 y errores de datos como mensajes).
- `yutani.doctor`: `Chequeo`, `binario`, `modulo`, `informe`, `mostrar` y
  `agregar_doctor` con el sobre JSON común.
- `yutani.report`: `sobre`, `emitir_json`, `encabezado_dredd`, `seccion_dredd` y
  `leer_secciones_dredd`.
- `yutani.textos`: ayuda y errores de Typer/Click en español.
- `yutani.testing`: `pruebas_de_contrato`.
