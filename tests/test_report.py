"""Sobre JSON y secciones para dredd."""

from __future__ import annotations

import json

import pytest

from yutani.report import emitir_json, encabezado_dredd, leer_secciones_dredd, seccion_dredd, sobre


def test_sobre():
    datos = sobre("gaff", "lint", {"hallazgos": []}, version="1.0.0")
    assert datos == {"schema_version": "1.0.0", "herramienta": "gaff", "comando": "lint", "version": "1.0.0",
                     "hallazgos": []}


def test_emitir_json(capsys):
    emitir_json("gaff", "lint", {"ok": True})
    assert json.loads(capsys.readouterr().out)["comando"] == "lint"


def test_encabezado_compatible_con_el_contrato_de_dredd():
    assert encabezado_dredd("gaff", "ok") == "<!-- dredd-section: gaff, tool=gaff, version=1.0.0, status=ok -->"
    with pytest.raises(ValueError):
        encabezado_dredd("gaff", "bien")


def test_ida_y_vuelta():
    informe = seccion_dredd("gaff", "Estilo", "Sin hallazgos.", "ok") + "\n" + \
        seccion_dredd("vasquez", "Robustez", "| a | b |", "fail")
    secciones = leer_secciones_dredd(informe)
    assert [(s["herramienta"], s["estado"]) for s in secciones] == [("gaff", "ok"), ("vasquez", "fail")]
    assert secciones[0]["contenido"] == "## Estilo\n\nSin hallazgos."
