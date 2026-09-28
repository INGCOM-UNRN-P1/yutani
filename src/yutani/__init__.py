"""yutani: núcleo común de las herramientas del ecosistema de Programación 1.

Solo entra código que ya está copiado en tres o más herramientas: la app Typer
base con el contrato de línea de comandos (`yutani.cli`), el `doctor` con su
sobre JSON (`yutani.doctor`), las salidas para dredd (`yutani.report`), los
textos de Typer y Click en español (`yutani.textos`) y el test de contrato
reutilizable (`yutani.testing`).
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("yutani")
except PackageNotFoundError:  # pragma: no cover - ejecución desde el árbol sin instalar
    __version__ = "0.0.0"
