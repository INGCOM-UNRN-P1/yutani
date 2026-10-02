"""Taxonomía común de hallazgos."""

from __future__ import annotations

import pytest

from yutani.hallazgos import (
    CATEGORIAS,
    enlace_apunte,
    hallazgo,
    normalizar_severidad,
    resumen_por_categoria,
)


def test_hallazgo_con_la_forma_comun():
    h = hallazgo("gaff", "0x1002h", "estilo", "ESTILO", "Uso de continue", archivo="a.c", linea=3)
    assert h["id"] == "gaff:0x1002h" and h["severidad"] == "estilo"
    assert h["enlace"] == "https://ingcom-unrn-p1.github.io/x1002h"


def test_enlace_por_categoria_y_por_regla():
    assert enlace_apunte("punteros") == "https://ingcom-unrn-p1.github.io/punteros"
    assert enlace_apunte("estilo") is None
    assert enlace_apunte("estilo", "0x000Ah").endswith("/x000ah")


@pytest.mark.parametrize("cruda, comun", [("ERROR", "error"), ("fatal error", "error"), ("warning", "advertencia"),
                                         ("ADVERTENCIA", "advertencia"), ("style", "estilo"), ("note", "info")])
def test_normalizar_severidad(cruda, comun):
    assert normalizar_severidad(cruda) == comun


def test_valores_desconocidos():
    with pytest.raises(ValueError):
        normalizar_severidad("gravisimo")
    with pytest.raises(ValueError):
        hallazgo("gaff", "x", "magia", "error", "m")


def test_resumen_por_categoria():
    hs = [hallazgo("hal", "SIGSEGV", "punteros", "error", "m"),
          hallazgo("hal", "SIGSEGV", "punteros", "error", "m"),
          hallazgo("tetsuo", "heap-use-after-free", "memoria", "error", "m")]
    resumen = resumen_por_categoria(hs)
    assert [f["categoria"] for f in resumen] == ["punteros", "memoria"]
    assert resumen[0]["mas_frecuentes"] == [{"id": "hal:SIGSEGV", "total": 2}]


def test_todas_las_categorias_tienen_descripcion():
    assert all(desc for desc, _ in CATEGORIAS.values())
