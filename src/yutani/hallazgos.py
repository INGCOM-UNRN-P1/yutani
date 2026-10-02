"""Taxonomía común de hallazgos: la misma forma para todas las herramientas (revisión 05 §3).

Cada herramienta informaba sus hallazgos con su propio esquema (gaff con `codigo`, daedalus con
`titulo`, hal con `senal`…), así que dredd no podía agruparlos por cohorte ni la devolución enlazar
al apunte. Un hallazgo común tiene:

- `id`: `<herramienta>:<código>` (`gaff:0x1002h`, `daedalus:undefined-reference`), estable entre
  versiones para poder contarlo de un cuatrimestre a otro;
- `categoria`: una de `CATEGORIAS`, los temas del programa de P1;
- `severidad`: una de `SEVERIDADES` (`normalizar_severidad` traduce las de cada herramienta);
- `enlace`: la página del apunte (la regla exacta, si el código es una regla de estilo `0x....h`).

`resumen_por_categoria` agrega una lista de hallazgos (de una entrega o de toda una cohorte).
"""

from __future__ import annotations

import re
from collections import Counter
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


def hallazgo(
    herramienta: str,
    codigo: str,
    categoria: str,
    severidad: str,
    mensaje: str,
    *,
    archivo: str | None = None,
    linea: int | None = None,
    columna: int | None = None,
    sugerencia: str | None = None,
) -> dict[str, Any]:
    """Un hallazgo con la forma común (ver el docstring del módulo)."""
    if categoria not in CATEGORIAS:
        raise ValueError(f"categoría «{categoria}» desconocida: usá {', '.join(CATEGORIAS)}")
    datos: dict[str, Any] = {
        "id": id_hallazgo(herramienta, codigo),
        "herramienta": herramienta,
        "codigo": codigo,
        "categoria": categoria,
        "severidad": normalizar_severidad(severidad),
        "mensaje": mensaje,
        "archivo": archivo,
        "linea": linea,
        "columna": columna,
        "enlace": enlace_apunte(categoria, codigo),
    }
    if sugerencia:
        datos["sugerencia"] = sugerencia
    return datos


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
