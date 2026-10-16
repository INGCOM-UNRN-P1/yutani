"""yutani.ia: la misma interfaz y configuración para Gemini, un servidor local, OpenCode y Claude."""

import json
import os
import subprocess
import sys
import threading
import types
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from yutani import ia


@pytest.fixture(autouse=True)
def entorno_limpio(monkeypatch, tmp_path):
    for var in ("P1_IA_PROVEEDOR", "P1_IA_MODELO", "P1_IA_URL", "P1_IA_CLAVE", "P1_IA_TIMEOUT",
                "GEMINI_API_KEY", "GOOGLE_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("P1_IA_CONFIG", str(tmp_path / "ia.toml"))
    return tmp_path / "ia.toml"


# ── configuración ─────────────────────────────────────────────────────────────

def test_por_defecto_de_la_herramienta():
    c = ia.configuracion("deckard", proveedor_por_defecto="opencode")
    assert (c.proveedor, c.modelo) == ("opencode", "opencode-go/qwen3.8-max")


def test_prioridad_argumento_entorno_archivo(entorno_limpio, monkeypatch):
    entorno_limpio.write_text('proveedor = "google"\n[local]\nmodelo = "del-archivo"\n', encoding="utf-8")
    assert ia.configuracion().proveedor == "google"
    monkeypatch.setenv("P1_IA_PROVEEDOR", "local")
    c = ia.configuracion()
    assert (c.proveedor, c.modelo, c.url) == ("local", "del-archivo", ia.URL_LOCAL)
    assert ia.configuracion(proveedor="opencode").proveedor == "opencode"


def test_seccion_de_la_herramienta(entorno_limpio):
    entorno_limpio.write_text('proveedor = "local"\n[herramientas.deckard]\nproveedor = "opencode"\n'
                              'modelo = "otro/modelo"\n', encoding="utf-8")
    assert ia.configuracion("voight").proveedor == "local"
    c = ia.configuracion("deckard")
    assert (c.proveedor, c.modelo) == ("opencode", "otro/modelo")


def test_alias_y_desconocido():
    assert ia.normalizar("Gemini") == "google" and ia.normalizar("ollama") == "local"
    assert ia.normalizar("anthropic") == "claude"
    with pytest.raises(ia.ErrorIA, match="desconocido"):
        ia.normalizar("watson")


def test_modelo_del_entorno_no_se_aplica_a_otro_proveedor_pedido_por_argumento(monkeypatch):
    monkeypatch.setenv("P1_IA_PROVEEDOR", "local")
    monkeypatch.setenv("P1_IA_MODELO", "qwen2.5-coder:7b")
    assert ia.configuracion(proveedor="google").modelo == "gemini-2.0-flash"


def test_claves(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "g")
    monkeypatch.setenv("P1_IA_CLAVE", "local")
    assert ia.configuracion(proveedor="google").clave == "g"
    assert ia.configuracion(proveedor="local").clave == "local"
    assert ia.configuracion(proveedor="claude").clave is None


def test_archivo_invalido(entorno_limpio):
    entorno_limpio.write_text("proveedor = ", encoding="utf-8")
    with pytest.raises(ia.ErrorIA, match="No se pudo leer"):
        ia.configuracion()


# ── servidor local (API de OpenAI) ────────────────────────────────────────────

class _Servidor(BaseHTTPRequestHandler):
    pedidos: list = []

    def log_message(self, *a):
        pass

    def _responder(self, codigo, datos):
        cuerpo = json.dumps(datos).encode()
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def do_GET(self):
        self._responder(200, {"data": [{"id": "jina/jina-embeddings-v2-base-es:latest"}, {"id": "qwen2.5-coder:7b"},
                                       {"id": "llama3.2"}]})

    def do_POST(self):
        cuerpo = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        _Servidor.pedidos.append((self.path, dict(self.headers), cuerpo))
        if cuerpo["model"] == "roto":
            self._responder(404, {"error": "model not found"})
            return
        self._responder(200, {"choices": [{"message": {"content": f"eco: {cuerpo['messages'][-1]['content']}"}}]})


@pytest.fixture
def servidor():
    _Servidor.pedidos = []
    httpd = HTTPServer(("127.0.0.1", 0), _Servidor)
    hilo = threading.Thread(target=httpd.serve_forever, daemon=True)
    hilo.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}/v1"
    httpd.shutdown()


def test_local_genera_con_sistema_y_clave(servidor, monkeypatch):
    monkeypatch.setenv("P1_IA_CLAVE", "secreta")
    monkeypatch.setenv("http_proxy", "http://proxy.invalido:3128")  # no se usa para localhost
    c = ia.cliente(proveedor="local", url=servidor, modelo="qwen2.5-coder:7b")
    assert c.generar("hola", sistema="sos docente") == "eco: hola"
    ruta, cabeceras, cuerpo = _Servidor.pedidos[-1]
    assert ruta == "/v1/chat/completions" and cabeceras["Authorization"] == "Bearer secreta"
    assert cuerpo["messages"][0] == {"role": "system", "content": "sos docente"}


def test_local_sin_modelo_usa_el_primero(servidor):
    c = ia.cliente(proveedor="local", url=servidor)
    assert c.modelos()[1:] == ["qwen2.5-coder:7b", "llama3.2"]
    c.generar("x")  # saltea el de embeddings
    assert _Servidor.pedidos[-1][2]["model"] == "qwen2.5-coder:7b"


def test_local_errores(servidor):
    with pytest.raises(ia.ErrorIA, match="404"):
        ia.cliente(proveedor="local", url=servidor, modelo="roto").generar("x")
    with pytest.raises(ia.ErrorIA, match="No se pudo conectar"):
        ia.cliente(proveedor="local", url="http://127.0.0.1:9/v1", modelo="m").generar("x")


def test_diagnostico_local(servidor):
    chequeos = ia.diagnostico(proveedor="local", url=servidor)
    assert all(c.ok for c in chequeos) and "3 modelos" in chequeos[-1].detalle
    caido = ia.diagnostico(proveedor="local", url="http://127.0.0.1:9/v1")
    assert not caido[-1].ok and not caido[-1].requerido


# ── OpenCode ──────────────────────────────────────────────────────────────────

@pytest.fixture
def opencode_falso(tmp_path, monkeypatch):
    if os.name == "nt":
        pytest.skip("script ejecutable POSIX")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    script = bin_dir / "opencode"
    script.write_text(f"#!{sys.executable}\nimport sys\n"
                      "if sys.argv[1] == 'models':\n    print('Models cache refreshed\\nopencode-go/a\\nopencode-go/b')\n"
                      "else:\n    print('ARGS', repr(sys.argv[1:]))\n", encoding="utf-8")
    script.chmod(0o755)
    monkeypatch.setenv("PATH", str(bin_dir))  # solo el falso: no el opencode real de la máquina
    monkeypatch.setattr(ia.os.path, "expanduser", lambda p: str(tmp_path / "no-existe"))
    return script


def test_opencode_run_con_sistema(opencode_falso, tmp_path):
    c = ia.cliente(proveedor="opencode", directorio=tmp_path)
    salida = c.generar("tarea", sistema="directiva")
    assert "'run', '-m', 'opencode-go/qwen3.8-max', '--dir'" in salida
    assert "DIRECTIVA DEL SISTEMA:\\ndirectiva" in salida and "TAREA:\\ntarea" in salida
    assert c.modelos() == ["opencode-go/a", "opencode-go/b"]


def test_opencode_sandboxed_no_lleva_run(opencode_falso, tmp_path):
    sandboxed = opencode_falso.with_name("opencode-sandboxed")
    sandboxed.write_text(opencode_falso.read_text(), encoding="utf-8")
    sandboxed.chmod(0o755)
    c = ia.cliente(proveedor="opencode", directorio=tmp_path)
    assert c.sandboxed and "'run'" not in c.generar("x")


def test_opencode_falla_y_timeout(opencode_falso, tmp_path):
    c = ia.cliente(proveedor="opencode", directorio=tmp_path)
    c._ejecutar = lambda *a, **k: subprocess.CompletedProcess(a, 3, "", "sin cuota")
    with pytest.raises(ia.ErrorIA, match="código 3: sin cuota"):
        c.generar("x")

    def lento(*a, **k):
        raise subprocess.TimeoutExpired(a, 1)
    c._ejecutar = lento
    with pytest.raises(ia.ErrorIA, match="tiempo límite"):
        c.generar("x")


def test_opencode_ausente(monkeypatch, tmp_path):
    monkeypatch.setattr(ia, "buscar_opencode", lambda sandbox=True: (None, False))
    with pytest.raises(ia.ErrorIA, match="No se encontró OpenCode"):
        ia.cliente(proveedor="opencode")


# ── Google y Claude (SDK simulados) ───────────────────────────────────────────

def _sdk_google(registro):
    class Modelos:
        def generate_content(self, model, contents, **kw):
            registro.append((model, contents, kw))
            return types.SimpleNamespace(text="de gemini")

        def list(self):
            return [types.SimpleNamespace(name="models/gemini-x", supported_actions=["generateContent"]),
                    types.SimpleNamespace(name="models/embed", supported_actions=["embedContent"])]

    class Client:
        def __init__(self, api_key):
            registro.append(("clave", api_key))
            self.models = Modelos()

    return types.SimpleNamespace(Client=Client)


def test_google(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    registro = []
    c = ia.ClienteGoogle(ia.configuracion(proveedor="gemini"), sdk=_sdk_google(registro))
    assert c.generar("p", sistema="s") == "de gemini"
    assert registro[0] == ("clave", "k")
    assert registro[1] == ("gemini-2.0-flash", "p", {"config": {"system_instruction": "s"}})
    assert c.modelos() == ["models/gemini-x"]


def test_google_sin_clave():
    with pytest.raises(ia.ErrorIA, match="GEMINI_API_KEY"):
        ia.ClienteGoogle(ia.configuracion(proveedor="google"), sdk=_sdk_google([]))


def test_google_sin_sdk(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    monkeypatch.setitem(sys.modules, "google", None)
    with pytest.raises(ia.ErrorIA, match="google-genai"):
        ia.cliente(proveedor="google")


def _sdk_claude(stop="end_turn"):
    registro = []

    def create(**kw):
        registro.append(kw)
        return types.SimpleNamespace(stop_reason=stop, stop_details=types.SimpleNamespace(category="cyber"),
                                     content=[types.SimpleNamespace(type="text", text="de claude")])

    sdk = types.SimpleNamespace(beta=types.SimpleNamespace(messages=types.SimpleNamespace(create=create)))
    return sdk, registro


def test_claude_y_negativa():
    sdk, registro = _sdk_claude()
    c = ia.ClienteClaude(ia.configuracion(proveedor="anthropic"), sdk=sdk)
    assert c.generar("p", sistema="s") == "de claude"
    assert registro[0]["model"] == "claude-opus-5" and registro[0]["system"] == "s"
    sdk, _ = _sdk_claude(stop="refusal")
    with pytest.raises(ia.ErrorIA, match="declinó.*cyber"):
        ia.ClienteClaude(ia.configuracion(proveedor="claude"), sdk=sdk).generar("p")


def test_diagnostico_google_sin_clave_no_es_requerido():
    chequeos = {c.nombre: c for c in ia.diagnostico(proveedor="google")}
    assert not chequeos["ia: clave"].ok and not chequeos["ia: clave"].requerido
    assert chequeos["ia: proveedor"].ok


def test_diagnostico_con_configuracion_rota(entorno_limpio):
    entorno_limpio.write_text('proveedor = "watson"\n', encoding="utf-8")
    (c,) = ia.diagnostico()
    assert not c.ok and "desconocido" in c.detalle


def test_sin_razonamiento():
    assert ia.sin_razonamiento("<think>\nveamos…\n</think>\n\nHOLA") == "HOLA"
    assert ia.sin_razonamiento("sin bloque <think>x</think>") == "sin bloque <think>x</think>"
