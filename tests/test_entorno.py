"""`yutani env-check`: versiones mínimas del sistema y variables del ecosistema (Ola 26)."""

import json

from typer.testing import CliRunner

from yutani.entorno import (
    Requisito,
    app,
    chequear_path_de_uv,
    chequear_python,
    chequear_requisito,
    chequear_variables,
    extraer_version,
)


def test_extraer_version():
    assert extraer_version("gcc (GCC) 14.2.1 20250110 (Red Hat 14.2.1-7)") == (14, 2, 1)
    assert extraer_version("uv 0.4.27 (abc 2024-10-25)") == (0, 4, 27)
    assert extraer_version("valgrind-3.27.1") == (3, 27, 1)
    assert extraer_version("sin números") is None


def test_minimo_de_version():
    gcc = Requisito("gcc", (10,), "motivo", sugerencia="instalá gcc")
    viejo = chequear_requisito(gcc, which=lambda n: "/usr/bin/gcc", ejecutar=lambda a: "gcc (GCC) 9.4.0")
    nuevo = chequear_requisito(gcc, which=lambda n: "/usr/bin/gcc", ejecutar=lambda a: "gcc (GCC) 13.1.0")
    falta = chequear_requisito(gcc, which=lambda n: None)
    assert (viejo.ok, viejo.detalle, viejo.sugerencia) == (False, "9.4.0 (mínimo 10)", "instalá gcc")
    assert nuevo.ok and nuevo.detalle == "13.1.0 (mínimo 10)"
    assert not falta.ok and falta.requerido


def test_sin_minimo_alcanza_con_estar():
    make = Requisito("make", None, "Makefile")
    assert chequear_requisito(make, which=lambda n: "/usr/bin/make", ejecutar=lambda a: "GNU Make 3.81").ok


def test_python():
    assert chequear_python((3, 12, 1)).ok and not chequear_python((3, 10, 9)).ok


def test_path_de_uv():
    ejecutar = lambda a: "/home/ana/.local/bin"  # noqa: E731
    assert chequear_path_de_uv(ejecutar, path="/usr/bin:/home/ana/.local/bin", which=lambda n: "/usr/bin/uv").ok
    falta = chequear_path_de_uv(ejecutar, path="/usr/bin", which=lambda n: "/usr/bin/uv")
    assert not falta.ok and "update-shell" in falta.sugerencia


def test_variables_sin_mostrar_secretos(tmp_path):
    config = tmp_path / "ia.toml"
    config.write_text("", encoding="utf-8")
    res = {c.nombre: c for c in chequear_variables({"MEET_TOOLS_PIN": "482913", "P1_IA_CONFIG": str(config),
                                                    "P1_PISTA": "1", "OTRA": "x"})}
    assert res["$MEET_TOOLS_PIN"].detalle == "definida" and res["$P1_PISTA"].detalle == "1"
    assert res["$P1_IA_CONFIG"].ok and "$OTRA" not in res
    assert not chequear_variables({"P1_IA_CONFIG": str(tmp_path / "no.toml")})[0].ok


def test_cli_json():
    res = CliRunner().invoke(app, ["env-check", "--json"])
    datos = json.loads(res.output)
    assert datos["schema_version"] == "1.0.0" and datos["herramienta"] == "yutani env-check"
    assert {c["nombre"] for c in datos["chequeos"]} >= {"python", "gcc", "uv", "make"}
    assert res.exit_code == (0 if datos["ok"] else 1)
