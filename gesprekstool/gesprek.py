#!/usr/bin/env python3
"""Gesprekstool: gesprekken volledig offline opnemen, transcriberen en samenvatten.

Opnemen      -> ffmpeg (microfoon)
Transcriberen -> whisper.cpp (lokaal model)
Samenvatten  -> llama.cpp (lokaal model, alleen bereikbaar via 127.0.0.1)

Alle hulpprogramma's draaien in een macOS-sandbox die netwerkverkeer blokkeert.
Gebruikt alleen de Python-standaardbibliotheek (werkt vanaf Python 3.8).
"""
import argparse
import datetime
import errno
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

APP_HOME = Path(os.environ.get("GESPREKSTOOL_HOME", str(Path.home() / ".gesprekstool")))
CONFIG_FILE = APP_HOME / "config.json"
TEMPLATE_MAP = APP_HOME / "templates"

STANDAARD = {
    "data_map": str(Path.home() / "GesprekkenLokaal"),
    "whisper_model": str(APP_HOME / "models" / "whisper.bin"),
    "llm_model": str(APP_HOME / "models" / "llm.gguf"),
    "taal": "nl",
    "microfoon": ":default",
    "context_tokens": 16384,
    "sandbox": True,
    "verwijder_audio_na_verwerking": False,
    "whisper_prompt": "",
}

# Sandbox-profielen (laatste regel die past wint).
SANDBOX_EXEC = "/usr/bin/sandbox-exec"
SB_GEEN_NETWERK = "(version 1)(allow default)(deny network*)"
SB_ALLEEN_LOOPBACK = (
    SB_GEEN_NETWERK
    + '(allow network* (local ip "localhost:*"))'
    + '(allow network* (remote ip "localhost:*"))'
)

UITVOER_TOKENS = 2000      # ruimte voor de samenvatting
NOTITIE_TOKENS = 800       # ruimte per deel bij lange gesprekken
TEKENS_PER_TOKEN = 3       # voorzichtige schatting voor Nederlands

# Nooit via een proxy praten, ook niet als er een in de omgeving staat.
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

CFG = dict(STANDAARD)


# ---------------------------------------------------------------- hulpjes

def fout(bericht):
    print("\nFOUT: " + bericht, file=sys.stderr)
    sys.exit(1)


def laad_config():
    if CONFIG_FILE.exists():
        try:
            CFG.update(json.loads(CONFIG_FILE.read_text("utf-8")))
        except ValueError as e:
            fout("config.json is ongeldig (%s): %s" % (CONFIG_FILE, e))


def zoek(*namen):
    pad = os.pathsep.join([os.environ.get("PATH", ""), "/opt/homebrew/bin", "/usr/local/bin"])
    for naam in namen:
        gevonden = shutil.which(naam, path=pad)
        if gevonden:
            return gevonden
    return None


def vereis(*namen):
    pad = zoek(*namen)
    if not pad:
        fout("'%s' niet gevonden. Draai install.sh opnieuw." % namen[0])
    return pad


def in_sandbox(cmd, loopback=False):
    """Zet een commando in een sandbox zonder netwerk (optioneel alleen loopback)."""
    if not CFG["sandbox"]:
        return cmd
    if not os.path.exists(SANDBOX_EXEC):
        fout("Netwerkblokkade (sandbox-exec) is niet beschikbaar op dit systeem.\n"
             "Zet \"sandbox\": false in %s als je zonder wilt werken." % CONFIG_FILE)
    return [SANDBOX_EXEC, "-p", SB_ALLEEN_LOOPBACK if loopback else SB_GEEN_NETWERK] + cmd


def kind_env():
    env = {k: v for k, v in os.environ.items() if "proxy" not in k.lower()}
    env["LLAMA_ARG_OFFLINE"] = "1"
    env["HF_HUB_OFFLINE"] = "1"
    return env


def staart(pad, regels=15):
    try:
        tekst = Path(pad).read_text("utf-8", errors="replace")
    except OSError:
        return ""
    return "\n".join(tekst.splitlines()[-regels:])


def slug(tekst):
    tekst = re.sub(r"[^\w\-]+", "-", tekst.strip().lower(), flags=re.UNICODE)
    return tekst.strip("-")[:40]


def duur(seconden):
    seconden = int(seconden)
    return "%02d:%02d:%02d" % (seconden // 3600, seconden % 3600 // 60, seconden % 60)


# -------------------------------------------------------------- templates

def templates():
    return sorted(p.stem for p in TEMPLATE_MAP.glob("*.md"))


def kies_template(voorkeur):
    beschikbaar = templates()
    if not beschikbaar:
        fout("Geen templates gevonden in %s" % TEMPLATE_MAP)
    if voorkeur:
        if voorkeur not in beschikbaar:
            fout("Template '%s' bestaat niet. Beschikbaar: %s" % (voorkeur, ", ".join(beschikbaar)))
        return voorkeur
    print("\nWelk soort gesprek?")
    for i, naam in enumerate(beschikbaar, 1):
        print("  %d. %s" % (i, naam))
    while True:
        keuze = input("Keuze [1]: ").strip() or "1"
        if keuze.isdigit() and 1 <= int(keuze) <= len(beschikbaar):
            return beschikbaar[int(keuze) - 1]
        if keuze in beschikbaar:
            return keuze


def nieuwe_map(template, naam):
    nu = datetime.datetime.now()
    delen = [nu.strftime("%Y-%m-%d_%H%M"), template]
    if naam:
        delen.append(slug(naam))
    basis = Path(CFG["data_map"]).expanduser()
    basis.mkdir(parents=True, exist_ok=True)
    os.chmod(str(basis), 0o700)
    doel = basis / "_".join(d for d in delen if d)
    teller = 2
    while doel.exists():
        doel = basis / ("_".join(d for d in delen if d) + "_%d" % teller)
        teller += 1
    doel.mkdir(mode=0o700)
    meta = {"datum": nu.strftime("%d-%m-%Y %H:%M"), "naam": naam, "template": template}
    (doel / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), "utf-8")
    return doel, meta


# ---------------------------------------------------------------- opnemen

def opnemen(wav, log):
    ffmpeg = vereis("ffmpeg")
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-f", "avfoundation",
           "-i", CFG["microfoon"], "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le",
           "-y", str(wav)]
    with open(str(log), "ab") as logf:
        proc = subprocess.Popen(in_sandbox(cmd), stdin=subprocess.PIPE,
                                stdout=logf, stderr=logf, env=kind_env())
    start = time.time()
    klaar = threading.Event()

    def klok():
        while not klaar.wait(1):
            if proc.poll() is not None:
                print("\n  De opname is onverwacht gestopt. Druk op Enter.")
                return
            if sys.stdout.isatty():
                print("\r  ● Opname loopt %s  (Enter = stoppen) " % duur(time.time() - start),
                      end="", flush=True)

    print("\n  ● Opname gestart. Druk op Enter om te stoppen.")
    draad = threading.Thread(target=klok, daemon=True)
    draad.start()
    try:
        input()
    except (KeyboardInterrupt, EOFError):
        pass
    klaar.set()
    try:
        proc.communicate(b"q", timeout=20)
    except subprocess.TimeoutExpired:
        proc.terminate()
        proc.wait()
    if not wav.exists() or wav.stat().st_size < 1000:
        fout("Er is geen audio opgenomen.\n%s\n\n"
             "Tip: geef Terminal toegang tot de microfoon via Systeeminstellingen > "
             "Privacy en beveiliging > Microfoon, of kies een andere microfoon "
             "('gesprek microfoons')." % staart(log))
    print("  Opname opgeslagen (%s)." % duur(time.time() - start))


def importeer_audio(bron, wav, log):
    ffmpeg = vereis("ffmpeg")
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-i", str(bron),
           "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", "-y", str(wav)]
    with open(str(log), "ab") as logf:
        code = subprocess.call(in_sandbox(cmd), stdin=subprocess.DEVNULL,
                               stdout=logf, stderr=logf, env=kind_env())
    if code != 0 or not wav.exists():
        fout("Kon het audiobestand niet omzetten.\n" + staart(log))


def microfoons(_args):
    ffmpeg = vereis("ffmpeg")
    uit = subprocess.run(in_sandbox([ffmpeg, "-hide_banner", "-f", "avfoundation",
                                     "-list_devices", "true", "-i", ""]),
                         stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, env=kind_env())
    tekst = uit.stdout.decode("utf-8", errors="replace")
    regels = [r for r in tekst.splitlines() if "AVFoundation" in r]
    print("\n".join(regels) if regels else tekst)
    print('\nKies een audio-apparaat door in %s bijvoorbeeld "microfoon": ":1" te zetten '
          "(het cijfer is het nummer onder 'audio devices')." % CONFIG_FILE)


# ---------------------------------------------------------- transcriberen

def transcriberen(wav, map_, log):
    whisper = vereis("whisper-cli", "whisper-cpp")
    model = Path(CFG["whisper_model"]).expanduser()
    if not model.exists():
        fout("Whisper-model ontbreekt: %s" % model)
    basis = map_ / "transcript"
    cmd = [whisper, "-m", str(model), "-f", str(wav), "-l", CFG["taal"],
           "-otxt", "-of", str(basis), "-np", "-t", str(min(8, os.cpu_count() or 4))]
    if CFG.get("whisper_prompt"):
        cmd += ["--prompt", CFG["whisper_prompt"]]
    print("\n  Transcriberen (dit kan enkele minuten duren)...\n")
    with open(str(log), "ab") as logf:
        code = subprocess.call(in_sandbox(cmd), stdin=subprocess.DEVNULL,
                               stderr=logf, env=kind_env())
    transcript = Path(str(basis) + ".txt")
    if code != 0 or not transcript.exists():
        fout("Transcriberen is mislukt.\n" + staart(log))
    if not transcript.read_text("utf-8", errors="replace").strip():
        fout("Het transcript is leeg: er is geen spraak herkend.")
    return transcript


# ------------------------------------------------------------ samenvatten

class LlmServer:
    """Start llama-server op een vrije poort op 127.0.0.1 en stopt hem na gebruik."""

    def __init__(self, log):
        self.log = log
        self.proc = None
        self.port = None

    def __enter__(self):
        binair = vereis("llama-server")
        model = Path(CFG["llm_model"]).expanduser()
        if not model.exists():
            fout("Taalmodel ontbreekt: %s" % model)
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            self.port = s.getsockname()[1]
        cmd = [binair, "-m", str(model), "--host", "127.0.0.1", "--port", str(self.port),
               "-c", str(CFG["context_tokens"]), "-ngl", "99", "-np", "1"]
        with open(str(self.log), "ab") as logf:
            self.proc = subprocess.Popen(in_sandbox(cmd, loopback=True),
                                         stdin=subprocess.DEVNULL, stdout=logf,
                                         stderr=subprocess.STDOUT, env=kind_env())
        print("\n  Taalmodel laden...", flush=True)
        eind = time.time() + 300
        while time.time() < eind:
            if self.proc.poll() is not None:
                fout("Het taalmodel kon niet starten.\n" + staart(self.log))
            try:
                with OPENER.open("http://127.0.0.1:%d/health" % self.port, timeout=2) as r:
                    if r.status == 200:
                        return self
            except OSError:
                pass
            time.sleep(0.5)
        self.stop()
        fout("Het taalmodel reageert niet (time-out).\n" + staart(self.log))

    def __exit__(self, *_):
        self.stop()

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()

    def vraag(self, prompt, max_tokens, toon=False):
        body = json.dumps({
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "max_tokens": max_tokens,
            "stream": True,
        }).encode("utf-8")
        req = urllib.request.Request("http://127.0.0.1:%d/v1/chat/completions" % self.port,
                                     data=body, headers={"Content-Type": "application/json"})
        delen = []
        try:
            with OPENER.open(req, timeout=3600) as r:
                for ruw in r:
                    regel = ruw.decode("utf-8", errors="replace").strip()
                    if not regel.startswith("data:"):
                        continue
                    data = regel[5:].strip()
                    if data == "[DONE]":
                        break
                    keuzes = json.loads(data).get("choices") or [{}]
                    stuk = (keuzes[0].get("delta") or {}).get("content")
                    if stuk:
                        delen.append(stuk)
                        if toon:
                            print(stuk, end="", flush=True)
        except urllib.error.HTTPError as e:
            self.stop()
            fout("Het taalmodel gaf een fout: %s\n%s"
                 % (e, e.read().decode("utf-8", errors="replace")[:500]))
        if toon:
            print()
        return "".join(delen).strip()


SAMENVAT_PROMPT = """Je maakt gespreksverslagen voor een docent of mentor.
Hieronder staat {bronsoort} van een gesprek ({soort}). De tekst is automatisch \
getranscribeerd: er kunnen fouten in staan en sprekers zijn niet gelabeld.

Vul het template in op basis van deze tekst. Regels:
- Gebruik alleen informatie uit de tekst. Verzin niets en vul niets aan.
- Schrijf "Niet besproken" bij onderdelen waarover niets is gezegd.
- Schrijf zakelijk, neutraal en in het Nederlands.
- Behoud de koppen en de opbouw van het template exact.
- Geef alleen het ingevulde template terug, zonder inleiding of toelichting.

=== TEMPLATE ===
{template}

=== {bronkop} ===
{bron}
"""

NOTITIE_PROMPT = """Hieronder staat deel {i} van {n} van het transcript van een gesprek \
({soort}). Maak beknopte, feitelijke aantekeningen in het Nederlands: wat is besproken, \
zorgen, wat goed gaat, afspraken (wie doet wat en wanneer). Gebruik alleen wat in de \
tekst staat en verzin niets. Geef alleen de aantekeningen.

=== TRANSCRIPT (deel {i}/{n}) ===
{stuk}
"""


def splits(tekst, maximum):
    stukken, huidig, lengte = [], [], 0
    for regel in tekst.splitlines():
        while len(regel) > maximum:
            if huidig:
                stukken.append("\n".join(huidig))
                huidig, lengte = [], 0
            stukken.append(regel[:maximum])
            regel = regel[maximum:]
        if lengte + len(regel) + 1 > maximum and huidig:
            stukken.append("\n".join(huidig))
            huidig, lengte = [], 0
        huidig.append(regel)
        lengte += len(regel) + 1
    if huidig:
        stukken.append("\n".join(huidig))
    return stukken


def strip_codeblok(tekst):
    m = re.match(r"^```[a-zA-Z]*\n(.*)\n```$", tekst.strip(), flags=re.DOTALL)
    return m.group(1).strip() if m else tekst.strip()


def samenvatten(map_, meta):
    transcript = (map_ / "transcript.txt").read_text("utf-8", errors="replace").strip()
    if not transcript:
        fout("Het transcript is leeg.")
    template_pad = TEMPLATE_MAP / (meta["template"] + ".md")
    if not template_pad.exists():
        fout("Template ontbreekt: %s" % template_pad)
    template = template_pad.read_text("utf-8")
    for sleutel, waarde in (("{datum}", meta.get("datum", "")),
                            ("{naam}", meta.get("naam") or "Onbekend"),
                            ("{soort}", meta["template"])):
        template = template.replace(sleutel, waarde)

    budget = (CFG["context_tokens"] - UITVOER_TOKENS - 600) * TEKENS_PER_TOKEN - len(template)
    if budget < 3000:
        fout("context_tokens (%s) is te klein voor dit template." % CFG["context_tokens"])
    deel_budget = (CFG["context_tokens"] - NOTITIE_TOKENS - 400) * TEKENS_PER_TOKEN

    with LlmServer(map_ / "verwerking.log") as llm:
        bron, bronsoort, bronkop = transcript, "het transcript", "TRANSCRIPT"
        ronde = 0
        while len(bron) > budget:
            ronde += 1
            if ronde > 3:
                fout("Het gesprek is te lang om samen te vatten met dit model.")
            stukken = splits(bron, deel_budget)
            print("  Lang gesprek: eerst %d delen verwerken." % len(stukken))
            notities = []
            for i, stuk in enumerate(stukken, 1):
                print("    deel %d/%d..." % (i, len(stukken)), flush=True)
                notities.append("[Deel %d]\n%s" % (i, llm.vraag(NOTITIE_PROMPT.format(
                    i=i, n=len(stukken), soort=meta["template"], stuk=stuk), NOTITIE_TOKENS)))
            bron = "\n\n".join(notities)
            bronsoort, bronkop = "aantekeningen", "AANTEKENINGEN"
        print("  Samenvatten...\n")
        tekst = llm.vraag(SAMENVAT_PROMPT.format(
            bronsoort=bronsoort, bronkop=bronkop, soort=meta["template"],
            template=template, bron=bron), UITVOER_TOKENS, toon=True)

    if not tekst:
        fout("Het taalmodel gaf geen samenvatting terug.\n" + staart(map_ / "verwerking.log"))
    doel = map_ / "samenvatting.md"
    doel.write_text(strip_codeblok(tekst) + "\n", "utf-8")
    return doel


# ------------------------------------------------------------- commando's

def afronden(map_, meta, wav):
    samenvatting = samenvatten(map_, meta)
    if CFG["verwijder_audio_na_verwerking"] and wav.exists():
        wav.unlink()
        print("  Audio verwijderd (instelling verwijder_audio_na_verwerking).")
    print("\nKlaar. Alles staat in:\n  %s" % map_)
    print("  - %s\n  - transcript.txt" % samenvatting.name)
    if sys.platform == "darwin" and sys.stdout.isatty():
        subprocess.call(["/usr/bin/open", str(map_)])


def cmd_nieuw(args):
    template = kies_template(args.template)
    naam = args.naam if args.naam is not None else input("Naam leerling (mag leeg): ").strip()
    map_, meta = nieuwe_map(template, naam)
    log, wav = map_ / "verwerking.log", map_ / "opname.wav"
    opnemen(wav, log)
    transcriberen(wav, map_, log)
    afronden(map_, meta, wav)


def cmd_verwerk(args):
    bron = Path(args.audio).expanduser()
    if not bron.is_file():
        fout("Bestand niet gevonden: %s" % bron)
    template = kies_template(args.template)
    map_, meta = nieuwe_map(template, args.naam or "")
    log, wav = map_ / "verwerking.log", map_ / "opname.wav"
    importeer_audio(bron, wav, log)
    transcriberen(wav, map_, log)
    afronden(map_, meta, wav)


def cmd_samenvat(args):
    map_ = Path(args.map).expanduser()
    if not (map_ / "transcript.txt").exists():
        fout("Geen transcript.txt gevonden in %s" % map_)
    meta = {"datum": "", "naam": "", "template": ""}
    if (map_ / "meta.json").exists():
        meta.update(json.loads((map_ / "meta.json").read_text("utf-8")))
    meta["template"] = kies_template(args.template or meta["template"] or None)
    doel = samenvatten(map_, meta)
    print("\nKlaar: %s" % doel)


def cmd_controle(_args):
    ok = [True]

    def regel(goed, tekst, waarschuwing=False):
        teken = "OK  " if goed else ("LET OP" if waarschuwing else "FOUT")
        if not goed and not waarschuwing:
            ok[0] = False
        print("  [%s] %s" % (teken, tekst))

    print("Programma's")
    for namen in (("ffmpeg",), ("whisper-cli", "whisper-cpp"), ("llama-server",)):
        pad = zoek(*namen)
        regel(bool(pad), "%s: %s" % (namen[0], pad or "niet gevonden"))

    print("Modellen en templates")
    for sleutel in ("whisper_model", "llm_model"):
        pad = Path(CFG[sleutel]).expanduser()
        regel(pad.exists(), "%s: %s" % (sleutel, pad))
    regel(bool(templates()), "templates: %s" % (", ".join(templates()) or "geen gevonden"))

    print("Opslag")
    data = Path(CFG["data_map"]).expanduser()
    data.mkdir(parents=True, exist_ok=True)
    os.chmod(str(data), 0o700)
    echt = str(data.resolve())
    thuis = str(Path.home())
    verdacht = [w for w in ("Mobile Documents", "CloudStorage", "Dropbox", "OneDrive",
                            "Google Drive", "iCloud") if w.lower() in echt.lower()]
    verdacht += [m for m in ("Documents", "Desktop")
                 if echt.startswith(os.path.join(thuis, m) + os.sep)]
    regel(not verdacht, "data_map %s%s" % (
        echt, " staat mogelijk in een map die met de cloud synchroniseert (%s)"
        % ", ".join(verdacht) if verdacht else " (alleen lokaal, alleen voor jou leesbaar)"))

    if sys.platform == "darwin":
        def uitvoer(cmd):
            try:
                r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                return r.stdout.decode("utf-8", errors="replace")
            except OSError:
                return ""
        regel("FileVault is On" in uitvoer(["/usr/bin/fdesetup", "status"]),
              "FileVault (schijfversleuteling) staat aan", waarschuwing=True)
        regel("[Excluded]" in uitvoer(["/usr/bin/tmutil", "isexcluded", echt]),
              "data_map is uitgesloten van Time Machine-back-ups", waarschuwing=True)

    print("Netwerkblokkade")
    if not CFG["sandbox"]:
        regel(False, "sandbox staat UIT in config.json: netwerk wordt niet afgedwongen geblokkeerd",
              waarschuwing=True)
    elif not os.path.exists(SANDBOX_EXEC):
        regel(False, "sandbox-exec niet gevonden")
    else:
        # 192.0.2.1 is een gereserveerd documentatie-adres: er bestaat geen host achter.
        proef = ("import socket,errno,sys\n"
                 "s=socket.socket();s.settimeout(2)\n"
                 "try:\n s.connect(('192.0.2.1',9))\n"
                 "except OSError as e:\n sys.exit(0 if e.errno==errno.EPERM else 3)\n"
                 "sys.exit(3)\n")
        code = subprocess.call([SANDBOX_EXEC, "-p", SB_GEEN_NETWERK, sys.executable, "-c", proef])
        regel(code == 0, "uitgaand netwerk is geblokkeerd voor opname en transcriptie")
        code = subprocess.call([SANDBOX_EXEC, "-p", SB_ALLEEN_LOOPBACK, sys.executable, "-c", proef])
        regel(code == 0, "uitgaand netwerk is geblokkeerd voor het taalmodel (alleen 127.0.0.1)")
        lus = ("import socket\n"
               "a=socket.socket();a.bind(('127.0.0.1',0));a.listen(1)\n"
               "b=socket.socket();b.settimeout(3);b.connect(a.getsockname())\n")
        code = subprocess.call([SANDBOX_EXEC, "-p", SB_ALLEEN_LOOPBACK, sys.executable, "-c", lus])
        regel(code == 0, "interne verbinding (127.0.0.1) voor het taalmodel werkt")

    print("\nAlles in orde." if ok[0] else "\nEr zijn problemen gevonden (zie FOUT hierboven).")
    sys.exit(0 if ok[0] else 1)


def main():
    parser = argparse.ArgumentParser(
        prog="gesprek", description="Gesprekken offline opnemen, transcriberen en samenvatten.")
    sub = parser.add_subparsers(dest="commando")

    def gespreksopties(p):
        p.add_argument("--template", help="naam van het template (bijv. oudergesprek)")
        p.add_argument("--naam", help="naam van de leerling")

    p = sub.add_parser("nieuw", help="nieuw gesprek opnemen en verwerken (standaard)")
    gespreksopties(p)
    p.set_defaults(func=cmd_nieuw)
    p = sub.add_parser("verwerk", help="bestaand audiobestand verwerken")
    p.add_argument("audio")
    gespreksopties(p)
    p.set_defaults(func=cmd_verwerk)
    p = sub.add_parser("samenvat", help="samenvatting opnieuw maken voor een gespreksmap")
    p.add_argument("map")
    p.add_argument("--template")
    p.set_defaults(func=cmd_samenvat)
    p = sub.add_parser("controle", help="controleer installatie, opslag en netwerkblokkade")
    p.set_defaults(func=cmd_controle)
    p = sub.add_parser("microfoons", help="toon beschikbare microfoons")
    p.set_defaults(func=microfoons)

    args = parser.parse_args()
    laad_config()
    if not args.commando:
        args = parser.parse_args(["nieuw"])
    try:
        args.func(args)
    except KeyboardInterrupt:
        print("\nAfgebroken.")
        sys.exit(130)


if __name__ == "__main__":
    main()
