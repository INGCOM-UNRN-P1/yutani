"""`yutani env-check`: dependencias del sistema y variables de entorno del ecosistema (Ola 26).

Cada herramienta tiene su `doctor` con lo que ella necesita; esto verifica lo común a todas,
con la versión mínima que exige el ecosistema cuando hay una razón concreta:

- gcc ≥ 10: daedalus, ripley y dredd compilan con `-fanalyzer`, que apareció en GCC 10;
- Python ≥ 3.11: el `requires-python` de los paquetes;
- uv ≥ 0.4.27: los `pyproject.toml` declaran `[dependency-groups]` (PEP 735), que uv entiende
  desde esa versión; con una anterior `uv sync` no instala las dependencias de desarrollo.

clang, make, gdb y valgrind se verifican presentes, con su versión, sin mínimo: ninguna
herramienta usa algo que lo fije. Además: que la carpeta de los ejecutables de `uv tool` esté
en el PATH (si no, «instalé ripley y no lo encuentra») y qué variables P1 están definidas.

Sale con 1 si falta algo requerido o una versión no alcanza el mínimo. Mismo sobre JSON que
`doctor` (`schema_version`, `ok`, `chequeos`).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Mapping, Optional, Sequence, Tuple

import typer

from yutani.doctor import Chequeo, informe, mostrar

Version = Tuple[int, ...]


@dataclass(frozen=True)
class Requisito:
    nombre: str
    minimo: Optional[Version]
    motivo: str
    requerido: bool = True
    args_version: Sequence[str] = ("--version",)
    sugerencia: str = ""


REQUISITOS: List[Requisito] = [
    Requisito("gcc", (10,), "compilar con los flags de la cátedra; -fanalyzer existe desde GCC 10",
              sugerencia="sudo apt install gcc  ·  sudo dnf install gcc  ·  MSYS2: pacman -S mingw-w64-ucrt-x86_64-gcc"),
    Requisito("make", None, "compilar los TP con su Makefile", sugerencia="sudo apt install make"),
    Requisito("gdb", None, "depurar (bishop, hal)", requerido=False, sugerencia="sudo apt install gdb"),
    Requisito("valgrind", None, "pérdidas de memoria (tetsuo, ripley)", requerido=False,
              sugerencia="sudo apt install valgrind (no existe en Windows nativo: usar WSL)"),
    Requisito("clang", None, "análisis estático (ub-sentinel de ripley)", requerido=False,
              sugerencia="sudo apt install clang"),
    Requisito("uv", (0, 4, 27), "instalar las herramientas; dependency-groups (PEP 735) desde uv 0.4.27",
              sugerencia="uv self update  ·  https://docs.astral.sh/uv/getting-started/installation/"),
]

PYTHON_MINIMO: Version = (3, 11)

# Variables que leen las herramientas del ecosistema (el valor de las secretas no se muestra).
VARIABLES = {
    "P1_PISTA": "modo pista en daedalus y ripley",
    "P1_IA_CONFIG": "configuración de la IA (yutani.ia)",
    "P1_IA_TIMEOUT": "tiempo máximo de las consultas a la IA",
    "MEET_TOOLS_PIN": "PIN de un daemon de meet-tools en otro equipo",
    "SLIDE_TOOLS_PIN": "PIN de un daemon de slide-tools en otro equipo",
    "XDG_STATE_HOME": "dónde va el registro de meet-tools y slide-tools",
}
SECRETAS = {"MEET_TOOLS_PIN", "SLIDE_TOOLS_PIN"}

_RE_VERSION = re.compile(r"(\d+)\.(\d+)(?:\.(\d+))?")


def extraer_version(texto: str) -> Optional[Version]:
    """La primera versión X.Y[.Z] del texto (`gcc (GCC) 14.2.1 20250110` → (14, 2, 1))."""
    m = _RE_VERSION.search(texto)
    return tuple(int(g) for g in m.groups() if g is not None) if m else None


def _formato(version: Version) -> str:
    return ".".join(str(n) for n in version)


Ejecutor = Callable[[Sequence[str]], str]


def _ejecutar(args: Sequence[str]) -> str:
    salida = subprocess.run(list(args), capture_output=True, text=True, timeout=10)
    return (salida.stdout or salida.stderr).strip()


def chequear_requisito(req: Requisito, which: Callable[[str], Optional[str]] = shutil.which,
                       ejecutar: Ejecutor = _ejecutar) -> Chequeo:
    ruta = which(req.nombre)
    if ruta is None:
        return Chequeo(req.nombre, req.requerido, False, "No encontrado en el PATH", req.motivo, req.sugerencia)
    try:
        primera = (ejecutar([ruta, *req.args_version]).splitlines() or ["?"])[0]
    except (OSError, subprocess.TimeoutExpired):
        primera = "?"
    version = extraer_version(primera)
    if req.minimo is None:
        return Chequeo(req.nombre, req.requerido, True, primera, req.motivo, "")
    if version is None:
        return Chequeo(req.nombre, req.requerido, False, f"no se pudo leer la versión: {primera}", req.motivo,
                       req.sugerencia)
    ok = version >= req.minimo
    detalle = f"{_formato(version)} (mínimo {_formato(req.minimo)})"
    return Chequeo(req.nombre, req.requerido, ok, detalle, req.motivo, "" if ok else req.sugerencia)


def chequear_python(version: Version = tuple(sys.version_info[:3])) -> Chequeo:
    ok = version >= PYTHON_MINIMO
    return Chequeo("python", True, ok, f"{_formato(version)} (mínimo {_formato(PYTHON_MINIMO)})",
                   "requires-python de los paquetes", "" if ok else "instalá Python 3.11 o posterior (uv python install 3.12)")


def chequear_path_de_uv(ejecutar: Ejecutor = _ejecutar, path: Optional[str] = None,
                        which: Callable[[str], Optional[str]] = shutil.which) -> Chequeo:
    """La carpeta de los ejecutables de `uv tool` tiene que estar en el PATH."""
    nombre = "PATH de uv tool"
    if which("uv") is None:
        return Chequeo(nombre, False, False, "sin uv", "", "")
    try:
        carpeta = ejecutar(["uv", "tool", "dir", "--bin"]).splitlines()[-1]
    except (OSError, subprocess.TimeoutExpired, IndexError):
        return Chequeo(nombre, False, False, "no se pudo consultar `uv tool dir --bin`", "", "")
    partes = [str(Path(p).expanduser().resolve()) for p in (path if path is not None else os.environ.get("PATH", "")).split(os.pathsep) if p]
    ok = str(Path(carpeta).expanduser().resolve()) in partes
    return Chequeo(nombre, True, ok, carpeta, "las herramientas instaladas con mother o uv tool",
                   "" if ok else "uv tool update-shell (y abrir otra terminal)")


def chequear_variables(entorno: Optional[Mapping[str, str]] = None) -> List[Chequeo]:
    variables: Mapping[str, str] = os.environ if entorno is None else entorno
    resultado = []
    for nombre, proposito in VARIABLES.items():
        if nombre not in variables:
            continue
        valor = "definida" if nombre in SECRETAS else variables[nombre]
        ok = True
        sugerencia = ""
        if nombre == "P1_IA_CONFIG" and not Path(variables[nombre]).expanduser().is_file():
            ok, sugerencia = False, "el archivo no existe"
        resultado.append(Chequeo(f"${nombre}", False, ok, valor, proposito, sugerencia))
    return resultado


def chequeos() -> List[Chequeo]:
    return [chequear_python(), *(chequear_requisito(r) for r in REQUISITOS), chequear_path_de_uv(),
            *chequear_variables()]


app = typer.Typer(add_completion=False, no_args_is_help=True, help="Utilidades comunes del ecosistema P1.")


@app.callback()
def _principal() -> None:
    """Utilidades comunes del ecosistema P1."""


@app.command("env-check")
def env_check(json_salida: bool = typer.Option(False, "--json", help="Informe en JSON con schema_version.")) -> None:
    """Herramientas del sistema (con su versión mínima) y variables de entorno del ecosistema."""
    from yutani import __version__

    datos = informe("yutani env-check", __version__, chequeos())
    if json_salida:
        typer.echo(json.dumps(datos, ensure_ascii=False, indent=2))
    else:
        mostrar(datos)
    raise typer.Exit(0 if datos["ok"] else 1)


def main() -> None:
    app()
