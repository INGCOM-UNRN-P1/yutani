# Instrucciones para el Agente (yutani)

1. **Commits semánticos en español**: `<tipo>(<alcance>): <descripción>` (feat, fix,
   docs, test, refactor, chore, ci, build).
2. **Regla de admisión**: solo entra código que ya está copiado en tres o más
   herramientas del ecosistema. Nada específico de una herramienta.
3. **Compatibilidad**: la API pública (lo que documenta el README) sigue SemVer; las
   herramientas la fijan por tag.
4. Todo cambio lleva tests; `yutani.textos` depende de detalles internos de Typer,
   así que sus tests son el aviso de que una versión nueva de Typer lo rompió.
