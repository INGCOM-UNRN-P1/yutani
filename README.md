# yutani — núcleo común de las herramientas de Programación 1

_(Weyland-Yutani, la corporación detrás de todo.)_

Biblioteca con lo que hoy está copiado en tres o más herramientas del
ecosistema. Regla de admisión: **solo entra código repetido en al menos tres
herramientas**, para que yutani no se convierta en otro monolito.

| Módulo | Qué resuelve | Reemplaza |
|:--|:--|:--|
| `yutani.cli` | App Typer con el contrato de LINEAMIENTOS §3.2: `-h/--help`, `--version/-v`, y `TyperConErrores`, que muestra los errores de datos (YAML mal formado, ruta inexistente, archivo que ya existe…) como un mensaje en español con exit 1 en lugar de un traceback | Contrato copiado en 41 herramientas (N-ECO-04); `errores.py` copiado en deckard, scorm-tools y dredd (N-ECO-05) |
| `yutani.doctor` | Chequeos de binarios y módulos, tabla legible y `doctor --json` con el sobre común (`schema_version`, `ok`, `chequeos`) | Un doctor distinto por herramienta |
| `yutani.report` | Sobre JSON versionado (`sobre`, `emitir_json`) y secciones para dredd (`<!-- dredd-section: … -->`) con su lector | Encabezado copiado en 28 herramientas |
| `yutani.textos` | Ayuda y errores de Typer/Click en español («Comandos», «Falta el argumento…», «No existe el comando…») | N-ECO-14 |
| `yutani.testing` | Test de contrato parametrizado para pegar en cada repo | `tests/test_contrato_cli.py` copiado en 38 repos |

## Instalación

yutani no se publica en PyPI: las herramientas la declaran como referencia
directa a git, fijada a un commit o tag:

```toml
[project]
dependencies = [
    "yutani[yaml] @ git+https://github.com/INGCOM-UNRN-P1/yutani@v0.1.0",
]

[tool.hatch.metadata]
allow-direct-references = true
```

## Uso

```python
from yutani.cli import crear_app
from yutani.doctor import agregar_doctor, binario
from yutani.report import seccion_dredd

from mi_herramienta import __version__

app = crear_app("mi-herramienta", __version__, "Qué hace la herramienta.")
agregar_doctor(app, "mi-herramienta", __version__, lambda: [
    binario("gcc", "Compilar el código del estudiante", sugerencia="sudo apt install gcc"),
])


@app.command()
def analizar(archivo: str) -> None:
    """Analiza un archivo C."""
    ...
```

`crear_app` pasa por defecto los textos de Typer al español; una herramienta
que necesita opciones globales propias usa `TyperConErrores` y
`opcion_version` por separado. Con `P1_DEPURAR=1` los errores de datos se
muestran con el traceback completo.

Test de contrato en la herramienta (`tests/test_contrato_cli.py`):

```python
from yutani.testing import pruebas_de_contrato
from mi_herramienta.cli import app

test_ayuda, test_version, test_doctor_json = pruebas_de_contrato(app)
```

## Desarrollo

```bash
uv sync
uv run pytest -q
```

## Licencia

GPL-3.0-or-later (ver `LICENSE`).
