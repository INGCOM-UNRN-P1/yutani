"""Salidas para otras herramientas: sobre JSON versionado y secciones para dredd.

`sobre` y `emitir_json` dan la forma común de `--json` (hoy repetida en cada
herramienta). `seccion_dredd` produce el bloque Markdown que dredd agrega a la
devolución de cada entrega, con el encabezado del contrato de integración
(copiado hoy en 28 herramientas):

    <!-- dredd-section: gaff, tool=gaff, version=1.0.0, status=ok -->

`leer_secciones_dredd` hace el camino inverso.
"""

from __future__ import annotations

import json
import re
from typing import Any

import typer

SCHEMA_VERSION = "1.0.0"
CONTRATO_DREDD = "1.0.0"
ESTADOS_DREDD = ("ok", "warn", "fail")

_RE_ENCABEZADO = re.compile(
    r"<!-- dredd-section: (?P<nombre>[\w.-]+), tool=(?P<herramienta>[\w.-]+), "
    r"version=(?P<version>[\w.-]+), status=(?P<estado>\w+) -->"
)


def sobre(herramienta: str, comando: str, datos: dict[str, Any], version: str | None = None) -> dict[str, Any]:
    """Datos de un comando dentro del sobre común (`schema_version`, herramienta, comando)."""
    carga: dict[str, Any] = {"schema_version": SCHEMA_VERSION, "herramienta": herramienta, "comando": comando}
    if version is not None:
        carga["version"] = version
    carga.update(datos)
    return carga


def emitir_json(herramienta: str, comando: str, datos: dict[str, Any], version: str | None = None) -> None:
    """Imprime el sobre por stdout, sin formato Rich (que podría cortar líneas)."""
    typer.echo(json.dumps(sobre(herramienta, comando, datos, version), ensure_ascii=False, indent=2))


def encabezado_dredd(herramienta: str, estado: str, nombre: str | None = None) -> str:
    if estado not in ESTADOS_DREDD:
        raise ValueError(f"estado «{estado}» inválido: usá {', '.join(ESTADOS_DREDD)}")
    return (f"<!-- dredd-section: {nombre or herramienta}, tool={herramienta}, "
            f"version={CONTRATO_DREDD}, status={estado} -->")


def seccion_dredd(herramienta: str, titulo: str, cuerpo: str, estado: str, nombre: str | None = None) -> str:
    """Sección Markdown para la devolución de dredd."""
    return f"{encabezado_dredd(herramienta, estado, nombre)}\n## {titulo}\n\n{cuerpo.strip()}\n"


def leer_secciones_dredd(texto: str) -> list[dict[str, str]]:
    """Secciones de un informe: encabezado y contenido hasta la siguiente sección."""
    marcas = list(_RE_ENCABEZADO.finditer(texto))
    secciones = []
    for i, marca in enumerate(marcas):
        fin = marcas[i + 1].start() if i + 1 < len(marcas) else len(texto)
        secciones.append({**marca.groupdict(), "contenido": texto[marca.end():fin].strip()})
    return secciones
