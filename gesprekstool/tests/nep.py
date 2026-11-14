"""Nagebootste onderdelen voor de tests: whisper-cli, llama-server en de microfoon."""
import json
import math
import os
import stat
import struct
import sys
import textwrap
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSLAG = "VERSLAG OUDERGESPREK\n\nAFSPRAKEN (WAT, WIE, WANNEER)\n- Sam gebruikt een huiswerkplanner (Sam, vanaf maandag)"

NEP_WHISPER = """
    import os, sys, time
    args = sys.argv[1:]
    for vlag in ("-m", "-f", "-l", "-of", "-t", "-otxt"):
        assert vlag in args, vlag
    assert args[args.index("-f") + 1] == "opname.wav", "audio moet relatief zijn (cwd = gespreksmap)"
    assert os.path.exists("opname.wav")
    if os.environ.get("NEP_GPU_KAPOT") and "-ng" not in args:
        sys.stderr.write("GPU-fout (nagebootst)\\n")
        sys.exit(3)
    regels = int(os.environ.get("NEP_REGELS", "3"))
    with open(args[args.index("-of") + 1] + ".txt", "w", encoding="utf-8") as f:
        for i in range(regels):
            f.write(" Regel %d: de mentor en de ouders bespreken de voortgang van Sam.\\n" % i)
    for i in range(3):
        print("[00:00:%02d.000 --> 00:00:%02d.000]   nep-uitvoer" % (i, i + 1), flush=True)
        time.sleep(float(os.environ.get("NEP_TRAAG", "0")))
"""

NEP_LLAMA = """
    import json, os, sys, time
    from http.server import BaseHTTPRequestHandler, HTTPServer
    args = sys.argv[1:]
    assert args[args.index("--host") + 1] == "127.0.0.1"
    assert os.environ.get("LLAMA_ARG_OFFLINE") == "1"
    assert not any("proxy" in k.lower() for k in os.environ), "proxy lekt naar het taalmodel"
    if os.environ.get("NEP_GPU_KAPOT") and args[args.index("-ngl") + 1] != "0":
        sys.exit(3)
    port = int(args[args.index("--port") + 1])
    VERSLAG = %r

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass
        def do_GET(self):
            self.send_response(200 if self.path == "/health" else 404)
            self.end_headers()
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            prompt = body["messages"][0]["content"]
            with open(os.environ["NEP_LLM_LOG"], "a", encoding="utf-8") as f:
                f.write(json.dumps(prompt) + "\\n")
            if "=== TEMPLATE ===" in prompt:
                tekst = "```\\n## " + VERSLAG.replace("AFSPRAKEN", "**AFSPRAKEN**") + "\\n```"
            else:
                tekst = "- aantekening van een deel"
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            for i in range(0, len(tekst), 12):
                data = {"choices": [{"delta": {"content": tekst[i:i + 12]}}]}
                self.wfile.write(("data: %%s\\n\\n" %% json.dumps(data)).encode())
                self.wfile.flush()
                time.sleep(float(os.environ.get("NEP_TRAAG", "0")) / 10)
            self.wfile.write(b"data: [DONE]\\n\\n")

    HTTPServer(("127.0.0.1", port), H).serve_forever()
""" % VERSLAG


def maak_omgeving(tmp):
    """Bouwt een nep-installatie in tmp en geeft de omgevingsvariabelen terug."""
    tmp = Path(tmp)
    app, home, systeem = tmp / "app", tmp / "home", tmp / "systeem"
    (systeem / "models").mkdir(parents=True)
    home.mkdir()
    (app / "templates").mkdir(parents=True)
    for sjabloon in (ROOT / "templates").glob("*.txt"):
        (app / "templates" / sjabloon.name).write_text(sjabloon.read_text("utf-8"), "utf-8")
    (systeem / "models" / "ggml-nep.bin").write_bytes(b"x")
    (systeem / "models" / "nep.gguf").write_bytes(b"x")
    for submap, naam, code in (("whisper", "whisper-cli", NEP_WHISPER),
                               ("llama", "llama-server", NEP_LLAMA)):
        pad = app / "bin" / submap / naam
        pad.parent.mkdir(parents=True)
        pad.write_text("#!%s\n%s" % (sys.executable, textwrap.dedent(code)), "utf-8")
        pad.chmod(pad.stat().st_mode | stat.S_IEXEC)
    return {
        "GESPREKSTOOL_APP": str(app), "GESPREKSTOOL_HOME": str(home),
        "GESPREKSTOOL_SYSTEEM": str(systeem), "NEP_LLM_LOG": str(tmp / "llm.jsonl"),
        "HTTP_PROXY": "http://192.0.2.1:9", "https_proxy": "http://192.0.2.1:9",
    }


def schrijf_config(env, **instellingen):
    cfg = {"data_map": str(Path(env["GESPREKSTOOL_HOME"]) / "gesprekken")}
    cfg.update(instellingen)
    (Path(env["GESPREKSTOOL_HOME"]) / "config.json").write_text(json.dumps(cfg), "utf-8")


def maak_wav(pad, seconden=2.0, hz=16000):
    monsters = [int(9000 * math.sin(i * 0.05)) for i in range(int(seconden * hz))]
    data = struct.pack("<%dh" % len(monsters), *monsters)
    kop = struct.pack("<4sI4s4sIHHIIHH4sI", b"RIFF", 36 + len(data), b"WAVE", b"fmt ", 16,
                      1, 1, hz, hz * 2, 2, 16, b"data", len(data))
    Path(pad).write_bytes(kop + data)


def prompts(env):
    pad = Path(env["NEP_LLM_LOG"])
    if not pad.exists():
        return []
    return [json.loads(r) for r in pad.read_text("utf-8").splitlines()]


class NepStream:
    def __init__(self, sd, samplerate, callback, finished_callback):
        if samplerate in sd.weiger:
            raise ValueError("Invalid sample rate (nagebootst)")
        self.sd, self.hz, self.callback, self.finished = sd, samplerate, callback, finished_callback
        self._stop = threading.Event()
        self._draad = None

    def start(self):
        def loop():
            n = self.hz // 100
            sterkte = 0 if self.sd.stil else 12000
            blok = struct.pack("<%dh" % n, *[int(sterkte * math.sin(i * 0.3)) for i in range(n)])
            while not self._stop.wait(0.01):
                self.callback(blok, n, None, None)
                if self.sd.valt_weg:
                    self.finished()
                    return
        self._draad = threading.Thread(target=loop, daemon=True)
        self._draad.start()

    def stop(self):
        self._stop.set()
        if self._draad:
            self._draad.join(timeout=2)
        time.sleep(0.02)

    def close(self):
        pass


class NepSd:
    """Staat in voor de module sounddevice."""

    def __init__(self, weiger=(), stil=False, geen_microfoon=False):
        self.weiger, self.stil, self.geen_microfoon, self.valt_weg = set(weiger), stil, geen_microfoon, False

    def query_devices(self, device=None, kind=None):
        if self.geen_microfoon:
            raise ValueError("No input device (nagebootst)")
        return {"name": "Nep-microfoon", "max_input_channels": 1, "default_samplerate": 48000.0}

    def RawInputStream(self, samplerate, channels, dtype, device, callback, finished_callback):
        assert channels == 1 and dtype == "int16"
        return NepStream(self, samplerate, callback, finished_callback)
