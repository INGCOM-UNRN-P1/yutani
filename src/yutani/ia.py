"""Modelos de lenguaje con la misma interfaz y la misma configuración en todo el ecosistema.

Cada herramienta que usa IA (voight, deckard…) pide un cliente y le pasa un prompt; qué
proveedor responde lo decide la configuración, no la herramienta:

- ``google``: la API de Gemini (SDK ``google-genai``, extra ``yutani[google]``), con
  ``GEMINI_API_KEY`` o ``GOOGLE_API_KEY``.
- ``local``: un servidor propio con la API de OpenAI (``/v1/chat/completions``): Ollama,
  llama.cpp (``llama-server``), LM Studio, vLLM… Sin dependencias: solo la biblioteca estándar.
- ``opencode``: la CLI de OpenCode (``opencode run``), o el envoltorio ``opencode-sandboxed``
  si está instalado.
- ``claude``: la API de Anthropic (SDK ``anthropic``, extra ``yutani[claude]``), con
  ``ANTHROPIC_API_KEY``.

Configuración, de mayor a menor prioridad: los argumentos de la herramienta (``--proveedor``,
``--modelo``), las variables ``P1_IA_PROVEEDOR``, ``P1_IA_MODELO``, ``P1_IA_URL``,
``P1_IA_CLAVE`` y ``P1_IA_TIMEOUT``, el archivo ``~/.config/p1/ia.toml`` (o el de
``P1_IA_CONFIG``; en Windows, ``%APPDATA%\\p1\\ia.toml``) y, por último, el proveedor por
defecto de cada herramienta::

    proveedor = "local"            # el de todas las herramientas

    [local]
    url = "http://localhost:11434/v1"
    modelo = "qwen2.5-coder:7b"

    [google]
    modelo = "gemini-2.0-flash"

    [opencode]
    modelo = "opencode-go/qwen3.8-max"
    sandbox = true

    [herramientas.deckard]         # lo que cambia para una herramienta
    proveedor = "opencode"

Uso::

    from yutani import ia

    cliente = ia.cliente(herramienta="voight", proveedor=args.proveedor, modelo=args.modelo)
    texto = cliente.generar("Mejorá esta consigna: …", sistema="Sos docente de Programación 1.")
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Callable, Optional, Protocol

from yutani.doctor import Chequeo

PROVEEDORES = ("google", "local", "opencode", "claude")
# Nombres con que las herramientas los conocían: voight decía gemini; los servidores locales
# suelen nombrarse por el programa.
ALIAS = {"gemini": "google", "ollama": "local", "openai": "local", "llamacpp": "local",
         "lmstudio": "local", "anthropic": "claude"}
MODELOS_POR_DEFECTO = {"google": "gemini-2.0-flash", "opencode": "opencode-go/qwen3.8-max",
                       "claude": "claude-opus-5", "local": None}  # local: el primero que ofrezca el servidor
URL_LOCAL = "http://localhost:11434/v1"  # Ollama; llama-server usa :8080/v1 y LM Studio :1234/v1
TIMEOUT = 180.0


class ErrorIA(RuntimeError):
    """El proveedor no está disponible, no está configurado o falló la consulta."""


def normalizar(proveedor: str) -> str:
    """El nombre canónico del proveedor (acepta los alias); ErrorIA si no existe."""
    nombre = ALIAS.get(proveedor.strip().lower(), proveedor.strip().lower())
    if nombre not in PROVEEDORES:
        raise ErrorIA(f"Proveedor de IA desconocido: «{proveedor}». Opciones: {', '.join(PROVEEDORES)}.")
    return nombre


# ── configuración ─────────────────────────────────────────────────────────────

@dataclass
class ConfigIA:
    proveedor: str
    modelo: Optional[str] = None
    url: Optional[str] = None
    clave: Optional[str] = None
    timeout: float = TIMEOUT
    sandbox: bool = True  # opencode: preferir opencode-sandboxed
    origen: dict[str, str] = field(default_factory=dict)  # de dónde salió cada valor (para doctor)


def ruta_configuracion() -> Path:
    if os.environ.get("P1_IA_CONFIG"):
        return Path(os.environ["P1_IA_CONFIG"])
    if sys.platform == "win32" and os.environ.get("APPDATA"):
        return Path(os.environ["APPDATA"]) / "p1" / "ia.toml"
    base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "p1" / "ia.toml"


def _archivo() -> dict[str, Any]:
    ruta = ruta_configuracion()
    if not ruta.is_file():
        return {}
    try:
        return tomllib.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ErrorIA(f"No se pudo leer la configuración de IA {ruta}: {exc}") from exc


def _clave_de_entorno(proveedor: str) -> tuple[Optional[str], str]:
    nombres = {"google": ("GEMINI_API_KEY", "GOOGLE_API_KEY"), "claude": ("ANTHROPIC_API_KEY",),
               "local": ("P1_IA_CLAVE",), "opencode": ()}[proveedor]
    for nombre in nombres:
        if os.environ.get(nombre):
            return os.environ[nombre], nombre
    return None, ""


def configuracion(
    herramienta: Optional[str] = None,
    *,
    proveedor: Optional[str] = None,
    modelo: Optional[str] = None,
    url: Optional[str] = None,
    proveedor_por_defecto: str = "google",
) -> ConfigIA:
    """Resuelve la configuración con la prioridad del módulo (argumentos > entorno > archivo)."""
    datos = _archivo()
    propia = (datos.get("herramientas") or {}).get(herramienta or "", {}) if herramienta else {}
    origen: dict[str, str] = {}

    def elegir(nombre: str, argumento: Any, variable: str, *secciones: dict) -> Any:
        if argumento not in (None, ""):
            origen[nombre] = "argumento"
            return argumento
        if os.environ.get(variable):
            origen[nombre] = variable
            return os.environ[variable]
        for seccion in secciones:
            if seccion.get(nombre) not in (None, ""):
                origen[nombre] = str(ruta_configuracion())
                return seccion[nombre]
        return None

    elegido = elegir("proveedor", proveedor, "P1_IA_PROVEEDOR", propia, datos)
    if elegido is None:
        origen["proveedor"] = "por defecto de la herramienta"
    nombre = normalizar(elegido or proveedor_por_defecto)
    del_proveedor = datos.get(nombre) or {}
    # Si el proveedor salió de un argumento, un modelo del entorno pensado para otro no aplica.
    modelo_final = elegir("modelo", modelo, "P1_IA_MODELO" if origen["proveedor"] != "argumento" else "",
                          propia if propia.get("proveedor") in (None, nombre) else {}, del_proveedor)
    if modelo_final is None:
        modelo_final = MODELOS_POR_DEFECTO[nombre]
        origen["modelo"] = "por defecto"
    url_final = elegir("url", url, "P1_IA_URL", del_proveedor) if nombre == "local" else None
    clave, de_donde = _clave_de_entorno(nombre)
    if clave is None and del_proveedor.get("clave"):
        clave, de_donde = del_proveedor["clave"], str(ruta_configuracion())
    if de_donde:
        origen["clave"] = de_donde
    timeout = os.environ.get("P1_IA_TIMEOUT") or propia.get("timeout") or datos.get("timeout") or TIMEOUT
    return ConfigIA(
        proveedor=nombre,
        modelo=modelo_final,
        url=(url_final or URL_LOCAL) if nombre == "local" else None,
        clave=clave,
        timeout=float(timeout),
        sandbox=bool(del_proveedor.get("sandbox", True)),
        origen=origen,
    )


# ── clientes ──────────────────────────────────────────────────────────────────

class ClienteIA(Protocol):
    config: ConfigIA

    def generar(self, prompt: str, *, sistema: Optional[str] = None, modelo: Optional[str] = None) -> str: ...

    def modelos(self) -> list[str]: ...


def _modelo(config: ConfigIA, modelo: Optional[str]) -> str:
    elegido = modelo or config.modelo
    if not elegido:
        raise ErrorIA(f"Falta el modelo para el proveedor {config.proveedor}: indicalo con --modelo, "
                      f"P1_IA_MODELO o [{config.proveedor}] modelo en {ruta_configuracion()}.")
    return elegido


class ClienteGoogle:
    """Gemini con el SDK google-genai."""

    def __init__(self, config: ConfigIA, sdk: Any = None):
        self.config = config
        if sdk is None:
            try:
                from google import genai as sdk  # type: ignore[no-redef,import-not-found,unused-ignore]
            except ImportError as exc:
                raise ErrorIA("Falta el paquete google-genai para usar Gemini: instalá la herramienta con su "
                              "extra de IA (o yutani[google]).") from exc
        if not config.clave:
            raise ErrorIA("Falta la clave de Gemini: definí GEMINI_API_KEY (o GOOGLE_API_KEY).")
        self._sdk = sdk
        self._cliente = sdk.Client(api_key=config.clave)

    def generar(self, prompt: str, *, sistema: Optional[str] = None, modelo: Optional[str] = None) -> str:
        extra: dict[str, Any] = {}
        if sistema:
            extra["config"] = {"system_instruction": sistema}
        try:
            respuesta = self._cliente.models.generate_content(model=_modelo(self.config, modelo), contents=prompt,
                                                              **extra)
        except ErrorIA:
            raise
        except Exception as exc:  # noqa: BLE001 - el SDK lanza sus propias excepciones
            raise ErrorIA(f"Gemini falló: {exc}") from exc
        return getattr(respuesta, "text", None) or ""

    def modelos(self) -> list[str]:
        try:
            return [m.name for m in self._cliente.models.list()
                    if "generateContent" in (getattr(m, "supported_actions", None)
                                             or getattr(m, "supported_methods", None) or [])]
        except Exception as exc:  # noqa: BLE001
            raise ErrorIA(f"No se pudieron listar los modelos de Gemini: {exc}") from exc


def _es_local(url: str) -> bool:
    return (urllib.parse.urlparse(url).hostname or "") in ("localhost", "127.0.0.1", "::1")


class ClienteLocal:
    """Un servidor con la API de OpenAI (Ollama, llama.cpp, LM Studio, vLLM…), con urllib."""

    def __init__(self, config: ConfigIA):
        self.config = config
        self.url = (config.url or URL_LOCAL).rstrip("/")
        # Un servidor en la misma máquina no va por el proxy institucional aunque http_proxy esté definido.
        manejadores = [urllib.request.ProxyHandler({})] if _es_local(self.url) else []
        self._abrir = urllib.request.build_opener(*manejadores).open

    def _pedir(self, ruta: str, cuerpo: Optional[dict] = None, timeout: Optional[float] = None) -> dict:
        cabeceras = {"Content-Type": "application/json"}
        if self.config.clave:
            cabeceras["Authorization"] = f"Bearer {self.config.clave}"
        datos = json.dumps(cuerpo).encode("utf-8") if cuerpo is not None else None
        pedido = urllib.request.Request(self.url + ruta, data=datos, headers=cabeceras,
                                        method="POST" if datos is not None else "GET")
        try:
            with self._abrir(pedido, timeout=timeout or self.config.timeout) as respuesta:
                return json.loads(respuesta.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detalle = exc.read().decode("utf-8", "replace")[:300]
            raise ErrorIA(f"El servidor local respondió {exc.code} en {self.url}{ruta}: {detalle}") from exc
        except (urllib.error.URLError, OSError) as exc:
            raise ErrorIA(f"No se pudo conectar con el servidor local {self.url} ({exc}). ¿Está corriendo? "
                          "Con Ollama: `ollama serve`; con llama.cpp: `llama-server -m modelo.gguf`.") from exc
        except json.JSONDecodeError as exc:
            raise ErrorIA(f"El servidor local {self.url} no devolvió JSON en {ruta}.") from exc

    def modelos(self) -> list[str]:
        return [m.get("id", "") for m in self._pedir("/models", timeout=10).get("data", []) if m.get("id")]

    def generar(self, prompt: str, *, sistema: Optional[str] = None, modelo: Optional[str] = None) -> str:
        elegido = modelo or self.config.modelo
        if not elegido:
            # Sin modelo configurado, el primero que genere texto (Ollama lista también los de embeddings).
            disponibles = [m for m in self.modelos() if "embed" not in m.lower()]
            if not disponibles:
                raise ErrorIA(f"El servidor local {self.url} no ofrece ningún modelo de texto.")
            elegido = disponibles[0]
        mensajes = ([{"role": "system", "content": sistema}] if sistema else []) + [{"role": "user", "content": prompt}]
        datos = self._pedir("/chat/completions", {"model": elegido, "messages": mensajes, "stream": False})
        try:
            texto = datos["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise ErrorIA(f"Respuesta inesperada del servidor local: {str(datos)[:300]}") from exc
        return sin_razonamiento(texto)


_PENSAMIENTO = re.compile(r"^\s*<think>.*?</think>\s*", re.DOTALL)


def sin_razonamiento(texto: str) -> str:
    """Saca el bloque <think>…</think> con que empiezan los modelos de razonamiento (deepseek-r1,
    qwen3): las herramientas esperan solo la respuesta."""
    return _PENSAMIENTO.sub("", texto, count=1)


def buscar_opencode(sandbox: bool = True) -> tuple[Optional[str], bool]:
    """(ruta, es_sandboxed): el envoltorio opencode-sandboxed si se prefiere y existe, o opencode."""
    candidatos = []
    if sandbox:
        candidatos.append((shutil.which("opencode-sandboxed") or os.path.expanduser("~/bin/opencode-sandboxed"), True))
    candidatos.append((shutil.which("opencode") or os.path.expanduser("~/.opencode/bin/opencode"), False))
    for ruta, es_sandboxed in candidatos:
        if ruta and os.path.isfile(ruta) and os.access(ruta, os.X_OK):
            return ruta, es_sandboxed
    return None, False


class ClienteOpenCode:
    """La CLI de OpenCode: `opencode run -m MODELO --dir DIR PROMPT` (o el envoltorio sandboxed)."""

    def __init__(self, config: ConfigIA, directorio: Optional[Path] = None,
                 ejecutar: Callable[..., subprocess.CompletedProcess] = subprocess.run):
        self.config = config
        self.directorio = directorio
        self._ejecutar = ejecutar
        self.ejecutable, self.sandboxed = buscar_opencode(config.sandbox)
        if not self.ejecutable:
            raise ErrorIA("No se encontró OpenCode: instalalo (`opencode` en el PATH o en ~/.opencode/bin) "
                          "o elegí otro proveedor de IA.")

    def _correr(self, args: list[str], timeout: float, cwd: Optional[str] = None) -> str:
        try:
            proc = self._ejecutar(args, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False)
        except subprocess.TimeoutExpired as exc:
            raise ErrorIA(f"OpenCode excedió el tiempo límite de {timeout:g} s.") from exc
        except OSError as exc:
            raise ErrorIA(f"No se pudo ejecutar OpenCode: {exc}") from exc
        if proc.returncode != 0:
            raise ErrorIA(f"OpenCode terminó con código {proc.returncode}: "
                          f"{(proc.stderr or proc.stdout or '').strip()[:500]}")
        return (proc.stdout or "").strip()

    def generar(self, prompt: str, *, sistema: Optional[str] = None, modelo: Optional[str] = None) -> str:
        cwd = str((self.directorio or Path.cwd()).resolve())
        texto = f"### DIRECTIVA DEL SISTEMA:\n{sistema}\n\n### TAREA:\n{prompt}" if sistema else prompt
        args = [str(self.ejecutable)] + ([] if self.sandboxed else ["run"])
        args += ["-m", _modelo(self.config, modelo), "--dir", cwd, texto]
        return self._correr(args, self.config.timeout, cwd)

    def modelos(self) -> list[str]:
        directo, _ = buscar_opencode(sandbox=False)
        salida = self._correr([str(directo or self.ejecutable), "models"], 30)
        return [linea.strip() for linea in salida.splitlines()
                if linea.strip() and " " not in linea.strip() and not linea.startswith("Models cache")]


class ClienteClaude:
    """Claude con el SDK anthropic (reintentos del SDK y fallback del servidor ante una negativa)."""

    def __init__(self, config: ConfigIA, sdk: Any = None, max_tokens: int = 16000):
        self.config = config
        self.max_tokens = max_tokens
        if sdk is None:
            try:
                import anthropic  # type: ignore[import-not-found,unused-ignore]
            except ImportError as exc:
                raise ErrorIA("Falta el paquete anthropic para usar Claude: instalá la herramienta con su "
                              "extra de IA (o yutani[claude]).") from exc
            sdk = anthropic.Anthropic(api_key=config.clave, max_retries=5) if config.clave \
                else anthropic.Anthropic(max_retries=5)
        self._cliente = sdk

    def generar(self, prompt: str, *, sistema: Optional[str] = None, modelo: Optional[str] = None) -> str:
        extra: dict[str, Any] = {"system": sistema} if sistema else {}
        try:
            respuesta = self._cliente.beta.messages.create(
                model=_modelo(self.config, modelo), max_tokens=self.max_tokens,
                betas=["server-side-fallback-2026-07-01"], fallbacks="default",
                messages=[{"role": "user", "content": prompt}], **extra)
        except Exception as exc:  # noqa: BLE001
            raise ErrorIA(f"Claude falló: {exc}") from exc
        if getattr(respuesta, "stop_reason", None) == "refusal":
            categoria = getattr(getattr(respuesta, "stop_details", None), "category", None)
            raise ErrorIA(f"El modelo declinó la consulta (categoría: {categoria or 'sin dato'}).")
        return "".join(b.text for b in respuesta.content if getattr(b, "type", "") == "text")

    def modelos(self) -> list[str]:
        try:
            return [m.id for m in self._cliente.models.list()]
        except Exception as exc:  # noqa: BLE001
            raise ErrorIA(f"No se pudieron listar los modelos de Claude: {exc}") from exc


def cliente(config: Optional[ConfigIA] = None, *, directorio: Optional[Path] = None, **kwargs: Any) -> ClienteIA:
    """El cliente del proveedor configurado. `kwargs` va a `configuracion()` si no se pasa `config`."""
    config = config or configuracion(**kwargs)
    if config.proveedor == "google":
        return ClienteGoogle(config)
    if config.proveedor == "local":
        return ClienteLocal(config)
    if config.proveedor == "opencode":
        return ClienteOpenCode(config, directorio=directorio)
    return ClienteClaude(config)


def generar(prompt: str, *, sistema: Optional[str] = None, **kwargs: Any) -> str:
    """Atajo: `cliente(**kwargs).generar(prompt, sistema=sistema)`."""
    return cliente(**kwargs).generar(prompt, sistema=sistema)


# ── diagnóstico para doctor ───────────────────────────────────────────────────

def diagnostico(config: Optional[ConfigIA] = None, *, requerido: bool = False, **kwargs: Any) -> list[Chequeo]:
    """Chequeos del proveedor de IA para sumar al `doctor` de una herramienta (sin consultar al modelo)."""
    try:
        config = config or configuracion(**kwargs)
    except ErrorIA as exc:
        return [Chequeo("ia", requerido, False, str(exc), "Funciones con modelos de lenguaje",
                        f"Revisá {ruta_configuracion()}")]
    detalle = f"{config.proveedor} · modelo {config.modelo or '(el primero del servidor)'}"
    chequeos = [Chequeo("ia: proveedor", requerido, True, f"{detalle} (de {config.origen.get('proveedor', '?')})",
                        "Funciones con modelos de lenguaje")]
    sug = f"P1_IA_PROVEEDOR o {ruta_configuracion()}"
    if config.proveedor in ("google", "claude"):
        paquete = "google.genai" if config.proveedor == "google" else "anthropic"
        try:
            hay_sdk = importlib.util.find_spec(paquete) is not None
        except ModuleNotFoundError:  # find_spec("google.genai") sin el paquete google
            hay_sdk = False
        chequeos.append(Chequeo(f"ia: {paquete}", requerido, hay_sdk, "instalado" if hay_sdk else "no instalado",
                                "SDK del proveedor", "" if hay_sdk else "Instalá el extra de IA de la herramienta"))
        variable = "GEMINI_API_KEY" if config.proveedor == "google" else "ANTHROPIC_API_KEY"
        chequeos.append(Chequeo("ia: clave", requerido, bool(config.clave),
                                f"de {config.origen['clave']}" if config.clave else "no definida",
                                "Autenticación con la API", "" if config.clave else f"Definí {variable}"))
    elif config.proveedor == "local":
        try:
            modelos = ClienteLocal(replace(config, timeout=5)).modelos()
            ok, texto = True, f"{config.url} responde ({len(modelos)} modelos)"
            if config.modelo and config.modelo not in modelos:
                ok, texto = False, f"{config.url} responde, pero no ofrece {config.modelo}"
        except ErrorIA as exc:
            ok, texto = False, str(exc)
        chequeos.append(Chequeo("ia: servidor local", requerido, ok, texto, "Modelo en un servidor propio",
                                "" if ok else f"Levantá el servidor o corregí la URL ({sug})"))
    else:
        ruta, sandboxed = buscar_opencode(config.sandbox)
        chequeos.append(Chequeo("ia: opencode", requerido, bool(ruta),
                                (f"{ruta}" + (" (sandboxed)" if sandboxed else "")) if ruta else "no encontrado",
                                "CLI de OpenCode", "" if ruta else "Instalá OpenCode o elegí otro proveedor"))
    return chequeos
