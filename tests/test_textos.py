"""Textos de Typer y Click en español (N-ECO-14)."""

from __future__ import annotations

from pathlib import Path

import pytest
import typer
import typer.rich_utils
from rich.text import Text
from typer.testing import CliRunner

from yutani.cli import crear_app
from yutani.textos import traducir_mensaje

runner = CliRunner()


def _app():
    app = crear_app("demo", "1.0.0", "Demo.")

    @app.command()
    def analizar(
        archivo: Path = typer.Argument(..., exists=True, dir_okay=False),
        veces: int = typer.Option(1, "--veces", "-n"),
    ) -> None:
        """Analiza un archivo."""

    return app


@pytest.fixture(params=[None, True], ids=["terminal-normal", "terminal-forzada"])
def modo_terminal(request, monkeypatch):
    """Con GITHUB_ACTIONS, FORCE_COLOR o PY_COLORS, Typer fuerza la terminal y resalta la salida con
    códigos ANSI aunque no sea una tty (así corre el CI): los textos se comparan en los dos modos."""
    monkeypatch.setattr(typer.rich_utils, "FORCE_TERMINAL", request.param)


def _salida(resultado) -> str:
    """La salida sin estilos: el resaltado parte `--faltante` en `-` y `-faltante` con códigos ANSI."""
    return Text.from_ansi(resultado.output).plain


def test_titulos_de_la_ayuda(modo_terminal):
    salida = _salida(runner.invoke(_app(), ["--help"], env={"COLUMNS": "120"}))
    assert "Comandos" in salida and "Opciones" in salida
    assert "Uso: " in salida
    assert "Muestra esta ayuda y sale." in salida
    assert "Commands" not in salida and "Show this message" not in salida


def test_opciones_de_autocompletado_y_marcadores_del_uso(modo_terminal):
    salida = _salida(runner.invoke(_app(), ["--help"], env={"COLUMNS": "150"}))
    assert "Uso: demo [OPCIONES] COMANDO [ARGUMENTOS]..." in " ".join(salida.split())
    assert "Instala el autocompletado" in salida
    assert "Muestra el autocompletado" in salida
    assert "[OPTIONS]" not in salida and "Install completion" not in salida


def test_uso_de_un_comando(modo_terminal):
    salida = _salida(runner.invoke(_app(), ["analizar", "--help"], env={"COLUMNS": "150"}))
    assert "Uso: demo analizar [OPCIONES] " in " ".join(salida.split())


def test_ayuda_de_un_comando(modo_terminal):
    salida = _salida(runner.invoke(_app(), ["analizar", "--help"], env={"COLUMNS": "120"}))
    assert "Argumentos" in salida
    assert "[obligatorio]" in salida
    assert "[por defecto: 1]" in salida


@pytest.mark.parametrize("args, esperado", [
    (["analizar"], "Falta el argumento 'archivo'."),
    (["analisar"], "No existe el comando 'analisar'. ¿Quisiste decir 'analizar'?"),
    (["analizar", "no_existe.c"], "No existe 'no_existe.c'."),
    (["analizar", "--faltante"], "No existe la opción --faltante"),
])
def test_errores_de_uso(modo_terminal, args, esperado):
    resultado = runner.invoke(_app(), args, env={"COLUMNS": "200"})
    assert resultado.exit_code == 2
    assert esperado in _salida(resultado)
    assert "para ver la ayuda" in _salida(resultado)


def test_valor_invalido(modo_terminal, tmp_path):
    archivo = tmp_path / "a.c"
    archivo.write_text("int x;")
    resultado = runner.invoke(_app(), ["analizar", str(archivo), "-n", "tres"], env={"COLUMNS": "200"})
    assert resultado.exit_code == 2
    assert "Valor inválido para" in _salida(resultado)
    assert "'tres' no es un número entero." in _salida(resultado)


@pytest.mark.parametrize("mensaje, esperado", [
    ("Got unexpected extra argument (b.c)", "Sobran argumentos: b.c"),
    ("Option '--salida' requires an argument.", "La opción '--salida' necesita un valor."),
    ("File 'src' is a directory.", "'src' es un directorio y se esperaba un archivo."),
    ("5 is not in the range 1<=x<=3.", "5 está fuera del rango 1<=x<=3."),
    ("'rojo' is not one of 'a', 'b'.", "'rojo' no es ninguna de estas opciones: 'a', 'b'."),
    ("Un mensaje propio en español.", "Un mensaje propio en español."),
])
def test_traducir_mensaje(mensaje, esperado):
    assert traducir_mensaje(mensaje) == esperado
