"""Test de contrato de línea de comandos para pegar en cada herramienta (LINEAMIENTOS §3.2).

En `tests/test_contrato_cli.py` de la herramienta:

    from yutani.testing import pruebas_de_contrato
    from mi_herramienta.cli import app

    test_ayuda, test_version, test_doctor_json = pruebas_de_contrato(app)

Requiere pytest (grupo de desarrollo de la herramienta).
"""

from __future__ import annotations

import json
from typing import Callable

import pytest
import typer
from typer.testing import CliRunner


def pruebas_de_contrato(app: typer.Typer, *, doctor: bool = True) -> tuple[Callable[..., None], ...]:
    """Devuelve los tests de `-h/--help`, `--version/-v` y (opcional) `doctor --json`."""
    runner = CliRunner()

    @pytest.mark.parametrize("opcion", ["-h", "--help"])
    def test_ayuda(opcion: str) -> None:
        resultado = runner.invoke(app, [opcion])
        assert resultado.exit_code == 0, resultado.output

    @pytest.mark.parametrize("opcion", ["--version", "-v"])
    def test_version(opcion: str) -> None:
        resultado = runner.invoke(app, [opcion])
        assert resultado.exit_code == 0, resultado.output
        assert resultado.output.strip()

    def test_doctor_json() -> None:
        resultado = runner.invoke(app, ["doctor", "--json"])
        datos = json.loads(resultado.stdout)
        assert "schema_version" in datos
        assert resultado.exit_code == (0 if datos.get("ok", True) else 1)

    return (test_ayuda, test_version, test_doctor_json) if doctor else (test_ayuda, test_version)
