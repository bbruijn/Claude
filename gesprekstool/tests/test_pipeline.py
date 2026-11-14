"""Test de hele keten met nagebootste ffmpeg, whisper-cli en llama-server.

Draaien:  python3 -m unittest discover -s gesprekstool/tests -v
"""
import json
import os
import stat
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GESPREK = ROOT / "gesprek.py"

NEP_FFMPEG = """
    import sys
    args = sys.argv[1:]
    if "-list_devices" in args:
        sys.stderr.write("[AVFoundation indev @ 0x1] [0] Nep-microfoon\\n")
        sys.exit(1)
    if "avfoundation" in args:
        while sys.stdin.read(1) not in ("q", ""):
            pass
    open(args[-1], "wb").write(b"RIFF" + b"0" * 4000)
"""

NEP_WHISPER = """
    import os, sys
    args = sys.argv[1:]
    for vlag in ("-m", "-f", "-l", "-of", "-t"):
        assert vlag in args, vlag
    assert "-otxt" in args and "-np" in args
    regels = int(os.environ.get("NEP_REGELS", "3"))
    with open(args[args.index("-of") + 1] + ".txt", "w", encoding="utf-8") as f:
        for i in range(regels):
            f.write(" Regel %d: de mentor en de ouders bespreken de voortgang van Sam.\\n" % i)
    print("[00:00:00.000 --> 00:00:02.000]  nep-uitvoer")
"""

NEP_LLAMA = """
    import json, os, sys
    from http.server import BaseHTTPRequestHandler, HTTPServer
    args = sys.argv[1:]
    assert args[args.index("--host") + 1] == "127.0.0.1"
    assert os.environ.get("LLAMA_ARG_OFFLINE") == "1"
    port = int(args[args.index("--port") + 1])

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
                antwoord = ["```markdown\\n# Verslag", " nep\\n\\nAfspraak: ", "huiswerkplanner\\n```"]
            else:
                antwoord = ["- aantekening ", "van een deel"]
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            for stuk in antwoord:
                data = {"choices": [{"delta": {"content": stuk}}]}
                self.wfile.write(("data: %s\\n\\n" % json.dumps(data)).encode())
            self.wfile.write(b"data: [DONE]\\n\\n")

    HTTPServer(("127.0.0.1", port), H).serve_forever()
"""


class Keten(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        self.home, self.data, self.bin = t / "home", t / "data", t / "bin"
        (self.home / "models").mkdir(parents=True)
        (self.home / "templates").mkdir()
        self.bin.mkdir()
        for sjabloon in (ROOT / "templates").glob("*.md"):
            (self.home / "templates" / sjabloon.name).write_text(sjabloon.read_text("utf-8"), "utf-8")
        for model in ("whisper.bin", "llm.gguf"):
            (self.home / "models" / model).write_bytes(b"x")
        for naam, code in (("ffmpeg", NEP_FFMPEG), ("whisper-cli", NEP_WHISPER),
                           ("llama-server", NEP_LLAMA)):
            pad = self.bin / naam
            pad.write_text("#!%s\n%s" % (sys.executable, textwrap.dedent(code)), "utf-8")
            pad.chmod(pad.stat().st_mode | stat.S_IEXEC)
        self.llm_log = t / "llm.jsonl"
        self.config(context_tokens=16384)

    def tearDown(self):
        self.tmp.cleanup()

    def config(self, **extra):
        cfg = {"data_map": str(self.data), "sandbox": False}
        cfg.update(extra)
        (self.home / "config.json").write_text(json.dumps(cfg), "utf-8")

    def draai(self, *args, invoer="", regels=3):
        env = dict(os.environ, GESPREKSTOOL_HOME=str(self.home),
                   PATH=str(self.bin) + os.pathsep + os.environ["PATH"],
                   NEP_LLM_LOG=str(self.llm_log), NEP_REGELS=str(regels),
                   HTTP_PROXY="http://192.0.2.1:9", http_proxy="http://192.0.2.1:9")
        return subprocess.run([sys.executable, str(GESPREK)] + list(args), input=invoer,
                              env=env, capture_output=True, text=True, timeout=120)

    def prompts(self):
        return [json.loads(r) for r in self.llm_log.read_text("utf-8").splitlines()]

    def enige_map(self):
        mappen = list(self.data.iterdir())
        self.assertEqual(len(mappen), 1, mappen)
        return mappen[0]

    def test_bestaand_audiobestand_verwerken(self):
        audio = Path(self.tmp.name) / "memo.m4a"
        audio.write_bytes(b"audio")
        r = self.draai("verwerk", str(audio), "--template", "oudergesprek", "--naam", "Sam de Vries")
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        map_ = self.enige_map()
        self.assertIn("oudergesprek_sam-de-vries", map_.name)
        self.assertEqual(stat.S_IMODE(map_.stat().st_mode), 0o700)
        samenvatting = (map_ / "samenvatting.md").read_text("utf-8")
        self.assertEqual(samenvatting, "# Verslag nep\n\nAfspraak: huiswerkplanner\n")
        self.assertTrue((map_ / "transcript.txt").exists())
        self.assertTrue((map_ / "opname.wav").exists())
        prompt, = self.prompts()
        self.assertIn("## Afspraken", prompt)
        self.assertIn("**Leerling:** Sam de Vries", prompt)
        self.assertIn("Regel 2: de mentor", prompt)
        self.assertNotIn("{naam}", prompt)

    def test_opnemen_met_enter_stoppen(self):
        r = self.draai("nieuw", "--template", "leerlinggesprek", "--naam", "", invoer="\n")
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        map_ = self.enige_map()
        self.assertTrue((map_ / "samenvatting.md").exists())
        self.assertIn("**Leerling:** Onbekend", self.prompts()[0])

    def test_interactieve_keuze_zonder_argumenten(self):
        r = self.draai(invoer="2\nNoor\n\n")
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertIn("oudergesprek_noor", self.enige_map().name)

    def test_lang_gesprek_wordt_in_delen_verwerkt(self):
        self.config(context_tokens=4096)
        audio = Path(self.tmp.name) / "lang.wav"
        audio.write_bytes(b"audio")
        r = self.draai("verwerk", str(audio), "--template", "oudergesprek", "--naam", "X", regels=500)
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        prompts = self.prompts()
        self.assertGreater(len(prompts), 2)
        self.assertTrue(all("TRANSCRIPT (deel" in p for p in prompts[:-1]))
        self.assertIn("=== AANTEKENINGEN ===", prompts[-1])
        self.assertIn("aantekening van een deel", prompts[-1])
        # Elke prompt moet binnen het contextvenster passen (3 tekens per token).
        self.assertTrue(all(len(p) / 3 < 4096 for p in prompts))
        # Geen regel van het transcript mag verloren gaan bij het opdelen.
        alles = "".join(prompts[:-1])
        self.assertTrue(all("Regel %d:" % i in alles for i in range(500)))

    def test_opnieuw_samenvatten_met_ander_template(self):
        audio = Path(self.tmp.name) / "memo.wav"
        audio.write_bytes(b"audio")
        self.draai("verwerk", str(audio), "--template", "oudergesprek", "--naam", "Sam")
        r = self.draai("samenvat", str(self.enige_map()), "--template", "leerlinggesprek")
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertIn("# Verslag leerlinggesprek", self.prompts()[-1])
        self.assertIn("**Leerling:** Sam", self.prompts()[-1])

    def test_audio_verwijderen_na_verwerking(self):
        self.config(verwijder_audio_na_verwerking=True)
        audio = Path(self.tmp.name) / "memo.wav"
        audio.write_bytes(b"audio")
        r = self.draai("verwerk", str(audio), "--template", "oudergesprek")
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertFalse((self.enige_map() / "opname.wav").exists())
        self.assertTrue(audio.exists(), "het oorspronkelijke bestand blijft staan")

    def test_sandbox_aan_zonder_sandbox_exec_weigert(self):
        if os.path.exists("/usr/bin/sandbox-exec"):
            self.skipTest("sandbox-exec aanwezig")
        self.config(sandbox=True)
        audio = Path(self.tmp.name) / "memo.wav"
        audio.write_bytes(b"audio")
        r = self.draai("verwerk", str(audio), "--template", "oudergesprek")
        self.assertEqual(r.returncode, 1)
        self.assertIn("Netwerkblokkade", r.stderr)
        self.assertFalse(self.llm_log.exists())

    def test_controle_en_microfoons(self):
        r = self.draai("controle")
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertIn("leerlinggesprek, oudergesprek", r.stdout)
        (self.home / "models" / "llm.gguf").unlink()
        self.assertEqual(self.draai("controle").returncode, 1)
        r = self.draai("microfoons")
        self.assertIn("Nep-microfoon", r.stdout)


if __name__ == "__main__":
    unittest.main()
