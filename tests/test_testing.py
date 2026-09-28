"""El test de contrato reutilizable se puede usar tal cual en una herramienta."""

from __future__ import annotations

from yutani.cli import crear_app
from yutani.doctor import Chequeo, agregar_doctor
from yutani.testing import pruebas_de_contrato

app = crear_app("demo", "1.0.0", "Demo.")
agregar_doctor(app, "demo", "1.0.0", lambda: [Chequeo("python", True, True)])

test_ayuda, test_version, test_doctor_json = pruebas_de_contrato(app)
