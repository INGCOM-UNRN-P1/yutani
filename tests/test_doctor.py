"""doctor con el sobre JSON común."""

from __future__ import annotations

import json
import sys

from typer.testing import CliRunner

from yutani.cli import crear_app
from yutani.doctor import Chequeo, agregar_doctor, binario, informe, modulo

runner = CliRunner()


def _app(chequeos):
    app = crear_app("demo", "1.0.0", "Demo.")
    agregar_doctor(app, "demo", "1.0.0", lambda: chequeos)
    return app


def test_binario_presente_y_ausente():
    python = binario(sys.executable, "Intérprete", requerido=True)
    assert python.ok and "Python" in python.detalle
    falta = binario("no-existe-este-binario", "x", requerido=False, sugerencia="sudo apt install x")
    assert not falta.ok and falta.sugerencia == "sudo apt install x"


def test_modulo():
    assert modulo("json").ok
    assert not modulo("modulo_que_no_existe_yutani").ok


def test_informe_ok_solo_mira_los_requeridos():
    datos = informe("demo", "1.0.0", [Chequeo("a", True, True), Chequeo("b", False, False)])
    assert datos["ok"] is True
    assert datos["schema_version"] == "1.0.0"
    assert set(datos["chequeos"][0]) == {"nombre", "requerido", "ok", "detalle", "proposito", "sugerencia"}


def test_doctor_json_y_codigo_de_salida():
    bien = runner.invoke(_app([Chequeo("gcc", True, True, "13.2")]), ["doctor", "--json"])
    assert bien.exit_code == 0
    assert json.loads(bien.stdout)["herramienta"] == "demo"
    mal = runner.invoke(_app([Chequeo("gcc", True, False)]), ["doctor", "--json"])
    assert mal.exit_code == 1
    assert json.loads(mal.stdout)["ok"] is False


def test_doctor_tabla():
    resultado = runner.invoke(_app([Chequeo("gcc", True, True, "13.2", "Compilar")]), ["doctor"])
    assert resultado.exit_code == 0
    assert "gcc" in resultado.output
