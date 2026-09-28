"""Diagnóstico del entorno (`doctor`) con el sobre JSON común (LINEAMIENTOS §3.2, N-ECO-04).

Cada herramienta declara sus chequeos (binarios, módulos, capacidades) y
`agregar_doctor` registra el comando `doctor [--json]`:

    {"schema_version": "1.0.0", "herramienta": ..., "version": ..., "ok": ...,
     "chequeos": [{"nombre", "requerido", "ok", "detalle", "proposito", "sugerencia"}]}

Sale con 1 si falla algún chequeo requerido.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
from dataclasses import asdict, dataclass
from typing import Any, Callable, Iterable, Sequence

import typer
from rich.console import Console
from rich.table import Table

SCHEMA_VERSION = "1.0.0"


@dataclass
class Chequeo:
    nombre: str
    requerido: bool
    ok: bool
    detalle: str = ""
    proposito: str = ""
    sugerencia: str = ""


def binario(
    nombre: str,
    proposito: str = "",
    *,
    requerido: bool = True,
    sugerencia: str = "",
    args_version: Sequence[str] = ("--version",),
    timeout: float = 5.0,
) -> Chequeo:
    """Busca `nombre` en el PATH y toma la primera línea de su versión."""
    ruta = shutil.which(nombre)
    if ruta is None:
        return Chequeo(nombre, requerido, False, "No encontrado en el PATH", proposito, sugerencia)
    try:
        salida = subprocess.run([ruta, *args_version], capture_output=True, text=True, timeout=timeout)
        lineas = (salida.stdout or salida.stderr).strip().splitlines()
        version = lineas[0] if lineas else "versión desconocida"
    except (OSError, subprocess.TimeoutExpired):
        version = "versión desconocida"
    return Chequeo(nombre, requerido, True, f"{version} ({ruta})", proposito, "")


def modulo(nombre: str, proposito: str = "", *, requerido: bool = True, sugerencia: str = "") -> Chequeo:
    """Verifica que un módulo de Python se pueda importar."""
    disponible = importlib.util.find_spec(nombre) is not None
    return Chequeo(nombre, requerido, disponible, "disponible" if disponible else "no instalado", proposito,
                   "" if disponible else sugerencia)


def informe(herramienta: str, version: str, chequeos: Iterable[Chequeo]) -> dict[str, Any]:
    """Sobre JSON común de `doctor --json`."""
    lista = list(chequeos)
    return {
        "schema_version": SCHEMA_VERSION,
        "herramienta": herramienta,
        "version": version,
        "ok": all(c.ok for c in lista if c.requerido),
        "chequeos": [asdict(c) for c in lista],
    }


def mostrar(datos: dict[str, Any], console: Console | None = None) -> None:
    """Tabla legible del informe."""
    consola = console or Console()
    tabla = Table(title=f"Diagnóstico del entorno ({datos['herramienta']} {datos['version']})")
    tabla.add_column("Componente", style="bold")
    tabla.add_column("Estado", justify="center")
    tabla.add_column("Detalle")
    tabla.add_column("Para qué / cómo resolverlo", style="yellow")
    for c in datos["chequeos"]:
        estado = "[green]✓[/green]" if c["ok"] else ("[red]✗[/red]" if c["requerido"] else "[yellow]–[/yellow]")
        tabla.add_row(c["nombre"], estado, c["detalle"], c["sugerencia"] or c["proposito"])
    consola.print(tabla)
    if datos["ok"]:
        consola.print("[bold green]✓ Están todos los componentes requeridos.[/bold green]")
    else:
        consola.print("[bold red]✗ Falta al menos un componente requerido.[/bold red]")


def agregar_doctor(app: typer.Typer, herramienta: str, version: str,
                   chequeos: Callable[[], Iterable[Chequeo]]) -> None:
    """Registra `doctor [--json]` en `app`."""

    @app.command("doctor")
    def doctor(json_salida: bool = typer.Option(False, "--json", help="Informe en JSON con schema_version.")) -> None:
        """Verifica que el entorno tenga lo necesario para usar la herramienta."""
        datos = informe(herramienta, version, chequeos())
        if json_salida:
            typer.echo(json.dumps(datos, ensure_ascii=False, indent=2))
        else:
            mostrar(datos)
        raise typer.Exit(0 if datos["ok"] else 1)
