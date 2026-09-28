"""App Typer base del ecosistema (LINEAMIENTOS §3.2, N-ECO-04, N-ECO-05).

- `-h` y `--help` en todos los comandos (CONTEXTO).
- `--version` / `-v` como opción ansiosa de la app raíz (`opcion_version`).
- `TyperConErrores`: los errores de datos esperables (YAML mal formado, ruta
  inexistente, archivo que ya existe…) se muestran como un mensaje en español
  y salen con 1 en lugar de un traceback. Con `P1_DEPURAR=1` se deja pasar la
  excepción para ver el traceback completo.
- `crear_app` arma todo lo anterior y, por defecto, pasa los textos de Typer y
  Click al español (`yutani.textos`).
"""

from __future__ import annotations

import os
import sys
from typing import Any, Iterable

import typer
from rich.console import Console
from rich.markup import escape

from yutani.textos import traducir

CONTEXTO: dict[str, Any] = {"help_option_names": ["-h", "--help"]}
VARIABLE_DEPURAR = "P1_DEPURAR"

try:  # PyYAML es opcional: solo se capturan sus errores si está instalado.
    import yaml

    _ERRORES_YAML: tuple[type[BaseException], ...] = (yaml.YAMLError,)
except ImportError:  # pragma: no cover - depende del entorno
    yaml = None  # type: ignore[assignment]
    _ERRORES_YAML = ()

ERRORES_DE_DATOS: tuple[type[BaseException], ...] = _ERRORES_YAML + (
    FileNotFoundError,
    NotADirectoryError,
    IsADirectoryError,
    FileExistsError,
    PermissionError,
    UnicodeDecodeError,
    ValueError,  # incluye pydantic.ValidationError
)

_err_console = Console(stderr=True)


def describir_error(error: BaseException) -> str:
    """Mensaje en español para un error de datos."""
    ruta = getattr(error, "filename", None)
    if yaml is not None and isinstance(error, yaml.YAMLError):
        marca = getattr(error, "problem_mark", None)
        problema = getattr(error, "problem", None) or str(error)
        donde = f" (línea {marca.line + 1}, columna {marca.column + 1})" if marca is not None else ""
        return f"el archivo no es un YAML válido: {problema}{donde}."
    if isinstance(error, FileExistsError):
        return f"ya existe {ruta}: elegí otra ruta."
    if isinstance(error, NotADirectoryError):
        return f"se esperaba un directorio y {ruta} no lo es."
    if isinstance(error, IsADirectoryError):
        return f"se esperaba un archivo y {ruta} es un directorio."
    if isinstance(error, FileNotFoundError):
        return f"no existe {ruta}." if ruta else str(error)
    if isinstance(error, PermissionError):
        return f"no hay permiso para acceder a {ruta}."
    if isinstance(error, UnicodeDecodeError):
        return "el archivo no está codificado en UTF-8."
    return str(error)


class TyperConErrores(typer.Typer):
    """App Typer que muestra los errores de datos como mensajes y sale con 1.

    `errores_extra` agrega excepciones de dominio propias de la herramienta.
    Actúa en `Typer.__call__`, que es lo que ejecuta el script instalado;
    `typer.testing.CliRunner` lo saltea (para probarlo, llamar a `app([...])`).
    """

    def __init__(self, *args: Any, errores_extra: Iterable[type[BaseException]] = (), **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.errores_de_datos: tuple[type[BaseException], ...] = ERRORES_DE_DATOS + tuple(errores_extra)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        try:
            return super().__call__(*args, **kwargs)
        except self.errores_de_datos as error:
            if os.environ.get(VARIABLE_DEPURAR):
                raise
            _err_console.print(f"[bold red]Error:[/bold red] {escape(describir_error(error))}")
            sys.exit(1)


def opcion_version(nombre: str, version: str) -> Any:
    """Opción `--version`/`-v` ansiosa: imprime «nombre versión» y sale con 0."""

    def mostrar(valor: bool) -> None:
        if valor:
            typer.echo(f"{nombre} {version}")
            raise typer.Exit(0)

    return typer.Option(False, "--version", "-v", callback=mostrar, is_eager=True,
                        help=f"Muestra la versión de {nombre} y sale.")


def crear_app(
    nombre: str,
    version: str,
    ayuda: str,
    *,
    errores_extra: Iterable[type[BaseException]] = (),
    en_espanol: bool = True,
    **kwargs: Any,
) -> TyperConErrores:
    """App raíz con el contrato del ecosistema: -h/--help, --version/-v y errores como mensajes.

    Registra el callback de la versión; una herramienta que necesite opciones
    globales propias puede usar `TyperConErrores` y `opcion_version` por separado.
    """
    if en_espanol:
        traducir()
    kwargs.setdefault("no_args_is_help", True)
    app = TyperConErrores(name=nombre, help=ayuda, context_settings=dict(CONTEXTO),
                          errores_extra=errores_extra, **kwargs)

    @app.callback()
    def principal(version_: bool = opcion_version(nombre, version)) -> None:  # noqa: ARG001
        pass

    principal.__doc__ = ayuda
    return app
