"""App base: contrato -h/--help, --version/-v y errores de datos como mensajes."""

from __future__ import annotations

import pytest
import typer
import yaml
from typer.testing import CliRunner

from yutani.cli import CONTEXTO, TyperConErrores, crear_app, describir_error

runner = CliRunner()


class ErrorPropio(Exception):
    pass


def _app():
    app = crear_app("demo", "1.2.3", "Herramienta de prueba.", errores_extra=(ErrorPropio,))

    @app.command()
    def leer(ruta: str) -> None:
        """Lee un YAML."""
        with open(ruta, encoding="utf-8") as archivo:
            yaml.safe_load(archivo)

    @app.command()
    def fallar() -> None:
        """Lanza un error de dominio."""
        raise ErrorPropio("falló a propósito")

    return app


@pytest.mark.parametrize("opcion", ["-h", "--help"])
def test_ayuda(opcion):
    resultado = runner.invoke(_app(), [opcion])
    assert resultado.exit_code == 0
    assert "Herramienta de prueba." in resultado.output


@pytest.mark.parametrize("opcion", ["--version", "-v"])
def test_version(opcion):
    resultado = runner.invoke(_app(), [opcion])
    assert resultado.exit_code == 0
    assert resultado.output.strip() == "demo 1.2.3"


def test_ayuda_de_subcomando_con_h():
    resultado = runner.invoke(_app(), ["leer", "-h"])
    assert resultado.exit_code == 0


def _invocar(app, args, capsys):
    with pytest.raises(SystemExit) as salida:
        app(args, prog_name="demo")
    return salida.value.code, capsys.readouterr().err


def test_archivo_inexistente_es_un_mensaje(tmp_path, capsys):
    codigo, err = _invocar(_app(), ["leer", str(tmp_path / "no.yaml")], capsys)
    assert codigo == 1
    assert "no existe" in err
    assert "Traceback" not in err


def test_yaml_invalido_indica_linea(tmp_path, capsys):
    ruta = tmp_path / "malo.yaml"
    ruta.write_text("clave: valor\notra: a: b\n", encoding="utf-8")
    codigo, err = _invocar(_app(), ["leer", str(ruta)], capsys)
    assert codigo == 1
    assert "línea 2" in err


def test_errores_extra_de_la_herramienta(capsys):
    codigo, err = _invocar(_app(), ["fallar"], capsys)
    assert codigo == 1
    assert "falló a propósito" in err


def test_p1_depurar_deja_ver_la_excepcion(tmp_path, monkeypatch):
    monkeypatch.setenv("P1_DEPURAR", "1")
    with pytest.raises(FileNotFoundError):
        _app()(["leer", str(tmp_path / "no.yaml")], prog_name="demo")


def test_typer_con_errores_sin_crear_app(capsys):
    app = TyperConErrores(context_settings=CONTEXTO)

    @app.command()
    def unico() -> None:
        raise FileExistsError(17, "File exists", "salida.txt")

    codigo, err = _invocar(app, [], capsys)
    assert codigo == 1
    assert "ya existe salida.txt" in err


@pytest.mark.parametrize("error, esperado", [
    (NotADirectoryError(20, "x", "a.c"), "se esperaba un directorio"),
    (IsADirectoryError(21, "x", "src"), "es un directorio"),
    (PermissionError(13, "x", "/root/a"), "no hay permiso"),
    (UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid"), "UTF-8"),
    (ValueError("dato raro"), "dato raro"),
])
def test_describir_error(error, esperado):
    assert esperado in describir_error(error)


def test_errores_de_uso_siguen_siendo_de_click():
    """Los errores de uso (exit 2) no los intercepta TyperConErrores."""
    resultado = runner.invoke(_app(), ["leer"])
    assert resultado.exit_code == 2


def test_app_sin_callback_de_crear_app_acepta_opcion_version():
    from yutani.cli import opcion_version

    app = TyperConErrores(context_settings=CONTEXTO)

    @app.callback()
    def principal(version: bool = opcion_version("otra", "0.9"), verboso: bool = typer.Option(False)) -> None:
        pass

    @app.command()
    def algo() -> None:
        pass

    resultado = runner.invoke(app, ["-v"])
    assert resultado.output.strip() == "otra 0.9"
