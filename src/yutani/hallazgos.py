"""Taxonomía común de hallazgos: la misma forma para todas las herramientas (revisión 05 §3).

Cada herramienta informaba sus hallazgos con su propio esquema (gaff con `codigo`, daedalus con
`titulo`, hal con `senal`…), así que dredd no podía agruparlos por cohorte ni la devolución enlazar
al apunte. Un hallazgo común tiene:

- `id`: `<herramienta>:<código>` (`gaff:0x1002h`, `daedalus:undefined-reference`), estable entre
  versiones para poder contarlo de un cuatrimestre a otro;
- `categoria`: una de `CATEGORIAS`, los temas del programa de P1;
- `severidad`: una de `SEVERIDADES` (`normalizar_severidad` traduce las de cada herramienta);
- `enlace`: la página del apunte (la regla exacta, si el código es una regla de estilo `0x....h`);
- `archivo`: la ruta relativa al directorio de trabajo, con `/` y sin `./` (`ruta_archivo`), para que
  jonesy y los demás clientes la resuelvan igual venga de la herramienta que venga.

Los clientes leen sólo la lista plana `hallazgos` de cada salida `--json`, con las claves de
`CLAVES` (`explicacion` y `sugerencia` son opcionales). `validar_salida` la verifica (también
`python -m yutani.hallazgos salida.json`, para el CI de punta a punta) y `ESQUEMA` es el mismo
contrato como JSON Schema.

`resumen_por_categoria` agrega una lista de hallazgos (de una entrega o de toda una cohorte).
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter
from pathlib import Path, PureWindowsPath
from typing import Any, Iterable

URL_APUNTE = "https://ingcom-unrn-p1.github.io"

# categoría: (qué agrupa, página del apunte). Las páginas son los slugs que publica MyST.
CATEGORIAS: dict[str, tuple[str, str | None]] = {
    "sintaxis": ("Sintaxis: puntos y comas, llaves, paréntesis", "base"),
    "declaraciones": ("Identificadores sin declarar, prototipos y firmas", "funciones"),
    "tipos": ("Tipos incompatibles, conversiones y casts", "casts"),
    "enlazado": ("Funciones sin definir, definiciones duplicadas y bibliotecas", "compilacion"),
    "compilacion": ("Compilación, banderas y Makefiles", "makefiles"),
    "control": ("Estructuras de control y flujo", "control-flujo"),
    "funciones": ("Diseño de funciones, retornos y parámetros", "funciones"),
    "punteros": ("Punteros nulos, sin inicializar o colgantes", "punteros"),
    "memoria": ("Memoria dinámica: fugas, liberaciones dobles y accesos inválidos", "memoria-dinamica"),
    "arreglos": ("Arreglos y cadenas: límites, terminador y tamaños", "secuencias"),
    "archivos": ("Entrada, salida y archivos", "archivos-texto"),
    "estructuras": ("Estructuras y uniones", "estructuras"),
    "tad": ("Tipos abstractos de datos y encapsulamiento", "tad"),
    "recursion": ("Recursión: caso base y profundidad", "recursividad-intro"),
    "numeros": ("Representación numérica, desbordes y portabilidad", "numeros"),
    "documentacion": ("Documentación y contratos", "contratos-intro"),
    "pruebas": ("Pruebas", "testing-basico"),
    "rendimiento": ("Complejidad y rendimiento", "complejidad"),
    "estilo": ("Reglas de estilo de la cátedra", None),
    "seguridad": ("Funciones inseguras y desbordes", None),
}

SEVERIDADES = ("error", "advertencia", "estilo", "info")

_SINONIMOS_SEVERIDAD = {
    "error": "error", "fatal": "error", "fatal error": "error", "critico": "error", "crítico": "error",
    "critical": "error", "high": "error", "alta": "error",
    "warning": "advertencia", "warn": "advertencia", "advertencia": "advertencia", "medium": "advertencia",
    "media": "advertencia",
    "estilo": "estilo", "style": "estilo", "convention": "estilo", "low": "estilo", "baja": "estilo",
    "info": "info", "note": "info", "nota": "info", "information": "info",
}

_RE_REGLA = re.compile(r"^0x[0-9A-Fa-f]{4}h$")


def normalizar_severidad(severidad: str) -> str:
    """La severidad de cada herramienta (ERROR, warning, ESTILO, note…) en las cuatro comunes."""
    clave = severidad.strip().lower()
    if clave not in _SINONIMOS_SEVERIDAD:
        raise ValueError(f"severidad «{severidad}» desconocida: usá {', '.join(SEVERIDADES)}")
    return _SINONIMOS_SEVERIDAD[clave]


def id_hallazgo(herramienta: str, codigo: str) -> str:
    """Identificador estable: `<herramienta>:<código>`."""
    if not herramienta or not codigo or ":" in herramienta:
        raise ValueError("el id necesita herramienta y código, y la herramienta no puede tener «:»")
    return f"{herramienta}:{codigo}"


def enlace_apunte(categoria: str, codigo: str | None = None) -> str | None:
    """La regla exacta si el código es una regla de estilo (`0x1002h` → `/x1002h`); si no, la
    página del tema de la categoría (o `None` si no tiene una propia)."""
    if codigo and _RE_REGLA.match(codigo):
        return f"{URL_APUNTE}/x{codigo[2:].lower()}"
    if categoria not in CATEGORIAS:
        raise ValueError(f"categoría «{categoria}» desconocida: usá {', '.join(CATEGORIAS)}")
    pagina = CATEGORIAS[categoria][1]
    return f"{URL_APUNTE}/{pagina}" if pagina else None


def ruta_archivo(ruta: str | os.PathLike[str] | None, base: str | os.PathLike[str] | None = None) -> str | None:
    """La ruta de un hallazgo como la esperan los clientes: relativa a `base` (el directorio de
    trabajo, por defecto) si está adentro, con `/` y sin `./`; si está afuera (un header del
    sistema), absoluta con `/`. Cada herramienta la informaba a su manera (daedalus y hal absoluta,
    ripley sólo el nombre, gaff relativa) y jonesy mostraba el mismo hallazgo dos veces."""
    if ruta is None or str(ruta) == "":
        return None
    texto = str(ruta)
    if "\\" in texto and not texto.startswith("/"):
        texto = PureWindowsPath(texto).as_posix()
    p = Path(texto)
    raiz = Path(base) if base is not None else Path.cwd()
    if p.is_absolute():
        try:
            relativa = os.path.relpath(p, raiz)
        except ValueError:  # otra unidad en Windows
            return p.as_posix()
        if relativa == os.pardir or relativa.startswith(os.pardir + os.sep):
            return p.as_posix()
        p = Path(relativa)
    return Path(os.path.normpath(p)).as_posix()


def hallazgo(
    herramienta: str,
    codigo: str,
    categoria: str,
    severidad: str,
    mensaje: str,
    *,
    archivo: str | os.PathLike[str] | None = None,
    linea: int | None = None,
    columna: int | None = None,
    sugerencia: str | None = None,
    explicacion: str | None = None,
) -> dict[str, Any]:
    """Un hallazgo con la forma común (ver el docstring del módulo). `explicacion` es el por qué
    en español (lo que jonesy muestra con F1); `sugerencia`, qué hacer."""
    if categoria not in CATEGORIAS:
        raise ValueError(f"categoría «{categoria}» desconocida: usá {', '.join(CATEGORIAS)}")
    datos: dict[str, Any] = {
        "id": id_hallazgo(herramienta, codigo),
        "herramienta": herramienta,
        "codigo": codigo,
        "categoria": categoria,
        "severidad": normalizar_severidad(severidad),
        "mensaje": mensaje,
        "archivo": ruta_archivo(archivo),
        "linea": linea,
        "columna": columna,
        "enlace": enlace_apunte(categoria, codigo),
    }
    if sugerencia:
        datos["sugerencia"] = sugerencia
    if explicacion:
        datos["explicacion"] = explicacion
    return datos


# clave: (tipos JSON aceptados, obligatoria).
CLAVES: dict[str, tuple[tuple[type, ...], bool]] = {
    "id": ((str,), True),
    "herramienta": ((str,), True),
    "codigo": ((str,), True),
    "categoria": ((str,), True),
    "severidad": ((str,), True),
    "mensaje": ((str,), True),
    "archivo": ((str, type(None)), True),
    "linea": ((int, type(None)), True),
    "columna": ((int, type(None)), True),
    "enlace": ((str, type(None)), True),
    "sugerencia": ((str,), False),
    "explicacion": ((str,), False),
}


def validar_hallazgo(h: Any, base: str | os.PathLike[str] | None = None) -> list[str]:
    """Los problemas de un hallazgo respecto de la forma común (vacía si cumple). Con `base`, una
    ruta absoluta que está adentro de `base` también es un problema: debió ser relativa."""
    if not isinstance(h, dict):
        return ["no es un objeto"]
    problemas = []
    for clave, (tipos, obligatoria) in CLAVES.items():
        if clave not in h:
            if obligatoria:
                problemas.append(f"falta «{clave}»")
            continue
        valor = h[clave]
        if not isinstance(valor, tipos) or isinstance(valor, bool):
            problemas.append(f"«{clave}» tiene un tipo inválido ({type(valor).__name__})")
    if problemas:
        return problemas
    if h["severidad"] not in SEVERIDADES:
        problemas.append(f"severidad «{h['severidad']}» fuera de {', '.join(SEVERIDADES)}")
    if h["categoria"] not in CATEGORIAS:
        problemas.append(f"categoría «{h['categoria']}» desconocida")
    if h["id"] != f"{h['herramienta']}:{h['codigo']}":
        problemas.append(f"el id «{h['id']}» no es «herramienta:codigo»")
    for clave in ("linea", "columna"):
        if h[clave] is not None and h[clave] < 1:
            problemas.append(f"«{clave}» empieza en 1 (vale {h[clave]})")
    archivo = h["archivo"]
    if archivo is not None:
        if not archivo or "\\" in archivo or archivo.startswith("./") or "/./" in archivo:
            problemas.append(f"«archivo» no está normalizada: «{archivo}»")
        elif base is not None and Path(archivo).is_absolute() and ruta_archivo(archivo, base) != archivo:
            problemas.append(f"«archivo» debería ser relativa: «{archivo}»")
    return problemas


def validar_salida(datos: Any, base: str | os.PathLike[str] | None = None) -> list[str]:
    """Los problemas de la salida `--json` de una herramienta: tiene que traer la lista plana
    `hallazgos` y cada uno, la forma común (`validar_hallazgo`)."""
    if not isinstance(datos, dict):
        return ["la salida no es un objeto JSON"]
    lista = datos.get("hallazgos")
    if not isinstance(lista, list):
        return ["la salida no tiene la lista «hallazgos»"]
    return [f"hallazgos[{i}]: {p}" for i, h in enumerate(lista) for p in validar_hallazgo(h, base)]


ESQUEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://github.com/INGCOM-UNRN-P1/yutani/hallazgo-v1.schema.json",
    "title": "Hallazgo común del ecosistema de Programación 1",
    "type": "object",
    "required": [c for c, (_, obligatoria) in CLAVES.items() if obligatoria],
    "properties": {
        "id": {"type": "string", "pattern": "^[^:]+:.+$"},
        "herramienta": {"type": "string"},
        "codigo": {"type": "string"},
        "categoria": {"enum": list(CATEGORIAS)},
        "severidad": {"enum": list(SEVERIDADES)},
        "mensaje": {"type": "string"},
        "archivo": {"type": ["string", "null"], "pattern": "^(?!\\./)[^\\\\]+$"},
        "linea": {"type": ["integer", "null"], "minimum": 1},
        "columna": {"type": ["integer", "null"], "minimum": 1},
        "enlace": {"type": ["string", "null"]},
        "sugerencia": {"type": "string"},
        "explicacion": {"type": "string"},
    },
}


def main(argv: list[str] | None = None) -> int:
    """`python -m yutani.hallazgos [salida.json ...]` (o la salida por stdin): valida la forma
    común; sale con 1 y lista los problemas si alguna no cumple. `--esquema` imprime el
    JSON Schema."""
    args = sys.argv[1:] if argv is None else argv
    if args == ["--esquema"]:
        print(json.dumps(ESQUEMA, indent=2, ensure_ascii=False))
        return 0
    fuentes = args or ["-"]
    total = 0
    for fuente in fuentes:
        texto = sys.stdin.read() if fuente == "-" else Path(fuente).read_text(encoding="utf-8")
        inicio = texto.find("{")
        try:
            datos = json.loads(texto[inicio:]) if inicio >= 0 else None
        except json.JSONDecodeError as e:
            print(f"{fuente}: no es JSON ({e})", file=sys.stderr)
            total += 1
            continue
        problemas = validar_salida(datos, Path.cwd())
        for p in problemas:
            print(f"{fuente}: {p}", file=sys.stderr)
        total += len(problemas)
    return 1 if total else 0


if __name__ == "__main__":
    raise SystemExit(main())


def resumen_por_categoria(hallazgos: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Cantidad de hallazgos por categoría (de mayor a menor), con los ids más frecuentes y el
    enlace al tema: lo que dredd muestra de una cohorte y el apunte usa para priorizar."""
    por_categoria: dict[str, Counter[str]] = {}
    for h in hallazgos:
        por_categoria.setdefault(h["categoria"], Counter())[h["id"]] += 1
    filas = []
    for categoria, ids in por_categoria.items():
        filas.append({
            "categoria": categoria,
            "descripcion": CATEGORIAS[categoria][0],
            "total": sum(ids.values()),
            "mas_frecuentes": [{"id": i, "total": n} for i, n in ids.most_common(5)],
            "enlace": enlace_apunte(categoria),
        })
    return sorted(filas, key=lambda f: (-f["total"], f["categoria"]))
