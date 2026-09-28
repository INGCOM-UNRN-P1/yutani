"""Textos de Typer y Click en español (N-ECO-14).

Typer 0.27 trae su propia copia de Click con los mensajes en inglés escritos en
el código (sin gettext), así que no alcanza con instalar una traducción:
`traducir()` cambia los títulos de la ayuda y traduce, con una tabla de
patrones, los mensajes de error más frecuentes (argumento faltante, comando u
opción inexistente, valor inválido, ruta que no existe).

Es idempotente y defensiva: si una versión futura de Typer renombra alguno de
esos elementos, ese texto queda en inglés en lugar de fallar (los tests de
yutani lo detectan).
"""

from __future__ import annotations

import re
from typing import Callable

TITULOS = {
    "COMMANDS_PANEL_TITLE": "Comandos",
    "OPTIONS_PANEL_TITLE": "Opciones",
    "ARGUMENTS_PANEL_TITLE": "Argumentos",
    "ERRORS_PANEL_TITLE": "Error",
    "ABORTED_TEXT": "Cancelado.",
    "DEFAULT_STRING": "[por defecto: {}]",
    "ENVVAR_STRING": "[variable de entorno: {}]",
    "REQUIRED_LONG_STRING": "[obligatorio]",
    "DEPRECATED_STRING": "(obsoleto) ",
    "RICH_HELP": "Probá [blue]'{command_path} {help_option}'[/] para ver la ayuda.",
}

AYUDA_HELP = "Muestra esta ayuda y sale."
PREFIJO_USO = "Uso: "

# (patrón, reemplazo); se aplican en orden sobre el mensaje completo.
MENSAJES: list[tuple[re.Pattern[str], str]] = [(re.compile(p), r) for p, r in [
    (r"Missing argument '(?P<x>[^']+)'\.", r"Falta el argumento '\g<x>'."),
    (r"Missing option '(?P<x>[^']+)'\.", r"Falta la opción '\g<x>'."),
    (r"Missing parameter: (?P<x>.+)", r"Falta el parámetro: \g<x>"),
    (r"No such command '(?P<x>[^']+)'\.", r"No existe el comando '\g<x>'."),
    (r"No such option: (?P<x>\S+)", r"No existe la opción \g<x>"),
    (r"\(Possible options: (?P<x>[^)]+)\)", r"(opciones posibles: \g<x>)"),
    (r"Did you mean (?P<x>.+?)\?", r"¿Quisiste decir \g<x>?"),
    (r"Invalid value for (?P<x>.+?): ", r"Valor inválido para \g<x>: "),
    (r"^Invalid value: ", r"Valor inválido: "),
    (r"Got unexpected extra arguments? \((?P<x>.*)\)", r"Sobran argumentos: \g<x>"),
    (r"Option '(?P<x>[^']+)' requires an argument\.", r"La opción '\g<x>' necesita un valor."),
    (r"Option '(?P<x>[^']+)' does not take a value\.", r"La opción '\g<x>' no lleva valor."),
    (r"(?P<x>'[^']*') is not a valid int(?:eger)?\.", r"\g<x> no es un número entero."),
    (r"(?P<x>'[^']*') is not a valid float\.", r"\g<x> no es un número."),
    (r"(?P<x>'[^']*') is not a valid boolean\. Recognized values: ", r"\g<x> no es un valor lógico. Valores aceptados: "),
    (r"(?P<x>'[^']*') is not one of (?P<y>.+)\.", r"\g<x> no es ninguna de estas opciones: \g<y>."),
    (r"(?P<x>'[^']*') is not (?P<y>'[^']*')\.", r"\g<x> no es \g<y>."),
    (r"(?P<x>.+) is not in the range (?P<y>.+)\.", r"\g<x> está fuera del rango \g<y>."),
    (r"(?:File|Directory|Path) (?P<x>'[^']*') does not exist\.", r"No existe \g<x>."),
    (r"File (?P<x>'[^']*') is a directory\.", r"\g<x> es un directorio y se esperaba un archivo."),
    (r"Directory (?P<x>'[^']*') is a file\.", r"\g<x> es un archivo y se esperaba un directorio."),
    (r"(?:File|Directory|Path) (?P<x>'[^']*') is not readable\.", r"No hay permiso de lectura sobre \g<x>."),
    (r"(?:File|Directory|Path) (?P<x>'[^']*') is not writable\.", r"No hay permiso de escritura sobre \g<x>."),
    (r"(?P<x>\d+) values are required, but (?P<y>\d+) given\.", r"Se necesitan \g<x> valores y se dieron \g<y>."),
]]

_aplicado = False


def traducir_mensaje(mensaje: str) -> str:
    """Traduce un mensaje de error de Click; lo que no reconoce queda igual."""
    for patron, reemplazo in MENSAJES:
        mensaje = patron.sub(reemplazo, mensaje)
    return mensaje


def _click():
    """La copia de Click que usa Typer (typer._click desde 0.20) o el paquete click."""
    try:
        from typer import _click as click
    except ImportError:  # pragma: no cover - Typer anterior a la copia propia
        import click  # type: ignore[import-not-found]
    return click


def _envolver_format_message(clase: type) -> None:
    # Propio o heredado: en Typer 0.27, ClickException lo hereda de TyperException.
    original = clase.__dict__.get("format_message") or getattr(clase, "format_message", None)
    if original is None or getattr(original, "_yutani", False):
        return

    def format_message(self) -> str:
        return traducir_mensaje(original(self))

    format_message._yutani = True  # type: ignore[attr-defined]
    clase.format_message = format_message  # type: ignore[attr-defined]


def _envolver(objeto: object, nombre: str, fabrica: Callable[[Callable], Callable]) -> None:
    original = getattr(objeto, nombre, None)
    if original is None or getattr(original, "_yutani", False):
        return
    nueva = fabrica(original)
    nueva._yutani = True  # type: ignore[attr-defined]
    setattr(objeto, nombre, nueva)


def traducir() -> None:
    """Pasa al español la ayuda y los errores de todas las apps Typer del proceso."""
    global _aplicado
    if _aplicado:
        return
    _aplicado = True

    import typer.rich_utils as rich_utils

    for nombre, texto in TITULOS.items():
        if hasattr(rich_utils, nombre):
            setattr(rich_utils, nombre, texto)
    # El resaltador de la ayuda reconoce «Usage: »; se agrega «Uso: ».
    resaltador = getattr(rich_utils, "OptionHighlighter", None)
    if resaltador is not None:
        resaltador.highlights = [h.replace("(?P<usage>Usage: )", "(?P<usage>(?:Usage|Uso): )")
                                 for h in resaltador.highlights]

    click = _click()
    excepciones = click.exceptions
    for nombre in ("ClickException", "UsageError", "BadParameter", "MissingParameter", "NoSuchOption",
                   "BadOptionUsage", "BadArgumentUsage"):
        clase = getattr(excepciones, nombre, None)
        if clase is not None:
            _envolver_format_message(clase)

    formateador = getattr(getattr(click, "formatting", None), "HelpFormatter", None)
    if formateador is not None:
        _envolver(formateador, "write_usage", lambda original: (
            lambda self, prog, args="", prefix=None: original(self, prog, args, PREFIJO_USO if prefix is None else prefix)))

    import typer.core

    def ayuda_en_espanol(original):
        def get_help_option(self, ctx):
            opcion = original(self, ctx)
            if opcion is not None and opcion.help == "Show this message and exit.":
                opcion.help = AYUDA_HELP
            return opcion
        return get_help_option

    for clase in (typer.core.TyperCommand, typer.core.TyperGroup):
        _envolver(clase, "get_help_option", ayuda_en_espanol)
