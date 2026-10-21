"""Taxonomía común de hallazgos."""

from __future__ import annotations

import pytest

from yutani.hallazgos import (
    CATEGORIAS,
    CLAVES,
    ESQUEMA,
    enlace_apunte,
    hallazgo,
    main,
    normalizar_severidad,
    resumen_por_categoria,
    ruta_archivo,
    validar_hallazgo,
    validar_salida,
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


def test_ruta_relativa_normalizada(tmp_path):
    adentro = tmp_path / "ej1" / "main.c"
    assert ruta_archivo(adentro, tmp_path) == "ej1/main.c"
    assert ruta_archivo("./ej1/../ej1/main.c", tmp_path) == "ej1/main.c"
    assert ruta_archivo("ej1\\main.c", tmp_path) == "ej1/main.c"
    assert ruta_archivo("/usr/include/stdio.h", tmp_path) == "/usr/include/stdio.h"
    assert ruta_archivo(None) is None and ruta_archivo("") is None


def test_hallazgo_normaliza_el_archivo_y_explica(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    h = hallazgo("daedalus", "punto-y-coma", "sintaxis", "error", "Falta un ;",
                 archivo=tmp_path / "tp" / "m.c", linea=4, explicacion="Cada sentencia termina en ;")
    assert h["archivo"] == "tp/m.c" and h["explicacion"] == "Cada sentencia termina en ;"
    assert validar_hallazgo(h, tmp_path) == []


def test_validar_salida():
    bueno = hallazgo("gaff", "0x1002h", "estilo", "ESTILO", "Uso de continue", archivo="a.c", linea=3)
    assert validar_salida({"hallazgos": [bueno]}) == []
    assert validar_salida({"diagnosticos": []}) == ["la salida no tiene la lista «hallazgos»"]
    malo = dict(bueno, archivo="./a.c", linea=0, severidad="ESTILO", id="gaff:otro")
    del malo["enlace"]
    assert validar_salida({"hallazgos": [malo]}) == ["hallazgos[0]: falta «enlace»"]
    malo["enlace"] = None
    problemas = validar_salida({"hallazgos": [malo]})
    assert any("severidad" in p for p in problemas) and any("id" in p for p in problemas)
    assert any("«linea» empieza en 1" in p for p in problemas) and any("normalizada" in p for p in problemas)


def test_validar_ruta_absoluta_adentro_del_directorio(tmp_path):
    h = hallazgo("hal", "acceso-invalido", "punteros", "error", "m", archivo="x.c")
    h["archivo"] = str(tmp_path / "x.c")
    assert validar_hallazgo(h) == []
    assert validar_hallazgo(h, tmp_path) == [f"«archivo» debería ser relativa: «{tmp_path / 'x.c'}»"]


def test_esquema_y_linea_de_comandos(tmp_path, capsys):
    import json

    assert set(ESQUEMA["required"]) == {c for c, (_, ob) in CLAVES.items() if ob}
    salida = tmp_path / "s.json"
    salida.write_text("aviso previo\n" + json.dumps({"hallazgos": [{"id": "x"}]}))
    assert main([str(salida)]) == 1
    assert "falta «herramienta»" in capsys.readouterr().err
    salida.write_text(json.dumps({"hallazgos": []}))
    assert main([str(salida)]) == 0
    assert main(["--esquema"]) == 0
    assert json.loads(capsys.readouterr().out)["title"].startswith("Hallazgo común")
