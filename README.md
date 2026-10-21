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
| `yutani.hallazgos` | La forma común de cada hallazgo (`id`, `herramienta`, `codigo`, `categoria`, `severidad`, `mensaje`, `archivo`, `linea`, `columna`, `enlace` y, opcionales, `sugerencia` y `explicacion`) en una lista plana `hallazgos`; `archivo` relativo al directorio de trabajo con `/` (`ruta_archivo`); `validar_salida` y `ESQUEMA` (JSON Schema) para verificarla | Un esquema por herramienta (gaff con `violaciones`, daedalus con `diagnosticos`, tetsuo con `diagnoses`…) y rutas absolutas, relativas o sólo el nombre |
| `yutani.textos` | Ayuda y errores de Typer/Click en español («Uso: … [OPCIONES] COMANDO [ARGUMENTOS]...», «Comandos», «Falta el argumento…», «No existe el comando…», la ayuda de `--install-completion`/`--show-completion`) | N-ECO-14 |
| `yutani.testing` | Test de contrato parametrizado para pegar en cada repo | `tests/test_contrato_cli.py` copiado en 38 repos |
| `yutani.ia` | Modelos de lenguaje con una interfaz (`cliente().generar(prompt, sistema=…)`, `modelos()`) y una configuración comunes: Gemini, un servidor local con la API de OpenAI (Ollama, llama.cpp, LM Studio, vLLM), OpenCode o Claude; `diagnostico()` para el doctor | El cliente de Gemini/Claude de voight y el de OpenCode de deckard. Excepción a la regla de las tres herramientas: entra por pedido explícito de unificar el uso de IA |

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

Para verificar la salida `--json` de cualquier analizador contra la forma común de los
hallazgos (lo hace el CI de punta a punta de p1-tools):

```bash
gaff check main.c --json | python -m yutani.hallazgos      # sale con 1 y lista los problemas
python -m yutani.hallazgos --esquema > hallazgo.schema.json
```

## Desarrollo

```bash
uv sync
uv run pytest -q
```

## Licencia

GPL-3.0-or-later (ver `LICENSE`).

## IA: un proveedor para todas las herramientas

Las herramientas que usan modelos de lenguaje (voight, deckard) piden el cliente a
`yutani.ia` y no saben qué proveedor responde: lo decide la configuración, que es
la misma para todas.

| Proveedor | Qué usa | Qué necesita |
|:--|:--|:--|
| `google` (alias `gemini`) | API de Gemini | extra `[google]` de la herramienta y `GEMINI_API_KEY` (o `GOOGLE_API_KEY`) |
| `local` (alias `ollama`, `openai`, `llamacpp`, `lmstudio`) | un servidor propio con la API de OpenAI (`/v1/chat/completions`) | el servidor corriendo; sin dependencias. URL por defecto `http://localhost:11434/v1` (Ollama) |
| `opencode` | la CLI `opencode run` (o `opencode-sandboxed` si está) | OpenCode instalado |
| `claude` (alias `anthropic`) | API de Anthropic | extra `[claude]` y `ANTHROPIC_API_KEY` |

Se elige, de mayor a menor prioridad, con la opción de la herramienta
(`--proveedor`, `--modelo`), las variables `P1_IA_PROVEEDOR`, `P1_IA_MODELO`,
`P1_IA_URL`, `P1_IA_CLAVE` (bearer del servidor local) y `P1_IA_TIMEOUT`, o el
archivo `~/.config/p1/ia.toml` (`%APPDATA%\p1\ia.toml` en Windows; otra ruta con
`P1_IA_CONFIG`):

```toml
proveedor = "local"

[local]
url = "http://localhost:11434/v1"
modelo = "qwen2.5-coder:7b"

[google]
modelo = "gemini-2.0-flash"

[opencode]
modelo = "opencode-go/qwen3.8-max"
sandbox = true            # preferir opencode-sandboxed

[herramientas.deckard]    # lo que cambia para una herramienta
proveedor = "opencode"
```

Sin nada configurado, cada herramienta usa su proveedor por defecto (voight:
`google`; deckard: `opencode`). Con `local` y sin modelo, se usa el primero que
ofrezca el servidor que no sea de embeddings, y el bloque `<think>…</think>` de
los modelos de razonamiento se saca de la respuesta. Para cada herramienta,
`<herramienta> doctor` muestra el proveedor elegido, de dónde salió y si está
disponible (clave, SDK, servidor que responde u OpenCode en el `PATH`).

```python
from yutani import ia

cliente = ia.cliente(herramienta="deckard", proveedor=args.proveedor, modelo=args.modelo,
                     proveedor_por_defecto="opencode")
texto = cliente.generar("Mejorá esta consigna: …", sistema="Sos docente de Programación 1.")
```

