"""Kern van de gesprekstool: instellingen, opslag, netwerkblokkade, transcriberen en
samenvatten. Bevat geen schermcode en gebruikt alleen de standaardbibliotheek.

Transcriberen -> whisper.cpp (whisper-cli), lokaal model
Samenvatten   -> llama.cpp (llama-server), lokaal model, alleen bereikbaar via 127.0.0.1
"""
import ctypes
import datetime
import json
import os
import re
import shutil
import socket
import struct
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

MAC = sys.platform == "darwin"
WINDOWS = sys.platform == "win32"
BEVROREN = getattr(sys, "frozen", False)          # True in het gebouwde pakket
_GEEN_VENSTER = 0x08000000 if WINDOWS else 0       # geen zwart consolevenster op Windows

STANDAARD = {
    "data_map": "",                # leeg = standaardmap per platform (zie data_map())
    "taal": "nl",
    "microfoon": None,             # None = standaardmicrofoon van het systeem
    "context_tokens": 0,           # 0 = automatisch op basis van werkgeheugen
    "netwerkblokkade": True,       # macOS: hulpprogramma's draaien in een sandbox zonder netwerk
    "gpu": True,                   # False = alleen processor gebruiken
    "audio_bewaren_dagen": 14,     # opname wissen N dagen na het verslag (0 = nooit wissen)
    "toestemming_vragen": True,    # vinkje "ik heb gemeld dat dit gesprek wordt opgenomen"
    "whisper_model": "",           # leeg = automatisch zoeken in de modelmappen
    "llm_model": "",
    "whisper_prompt": "",          # namen en vaktermen die vaak verkeerd verstaan worden
}
CFG = dict(STANDAARD)

SANDBOX_EXEC = "/usr/bin/sandbox-exec"
SB_GEEN_NETWERK = "(version 1)(allow default)(deny network*)"
SB_ALLEEN_LOOPBACK = (
    SB_GEEN_NETWERK
    + '(allow network* (local ip "localhost:*"))'
    + '(allow network* (remote ip "localhost:*"))'
)
FIREWALL_REGEL = "Gesprekstool netwerkblokkade"    # zelfde naam als in beheer/windows-installeren.ps1

UITVOER_TOKENS = 2000      # ruimte voor het verslag
NOTITIE_TOKENS = 800       # ruimte per deel bij lange gesprekken
TEKENS_PER_TOKEN = 3       # voorzichtige schatting voor Nederlands

# Nooit via een proxy praten, ook niet als er een in de omgeving staat.
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


class Fout(Exception):
    """Fout met een melding die we aan de gebruiker kunnen tonen."""


class Geannuleerd(Exception):
    pass


# ------------------------------------------------------------------ mappen

def app_map():
    """Map van het pakket: hier staan bin/, templates/ en eventueel models/."""
    if os.environ.get("GESPREKSTOOL_APP"):
        return Path(os.environ["GESPREKSTOOL_APP"])
    if BEVROREN:
        exe = Path(sys.executable).resolve()
        if MAC and exe.parent.name == "MacOS":
            return exe.parent.parent / "Resources"
        return exe.parent
    return Path(__file__).resolve().parent.parent


def gebruikers_map():
    """Instellingen per gebruiker. Op Windows bewust Local: dat zwerft niet mee naar de server."""
    if os.environ.get("GESPREKSTOOL_HOME"):
        return Path(os.environ["GESPREKSTOOL_HOME"])
    if MAC:
        return Path.home() / "Library" / "Application Support" / "Gesprekstool"
    if WINDOWS:
        return Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "Gesprekstool"
    return Path.home() / ".local" / "share" / "gesprekstool"


def systeem_map():
    """Map voor de hele computer: hier kan ICT modellen, templates en config.json neerzetten."""
    if os.environ.get("GESPREKSTOOL_SYSTEEM"):
        return Path(os.environ["GESPREKSTOOL_SYSTEEM"])
    if MAC:
        return Path("/Library/Application Support/Gesprekstool")
    if WINDOWS:
        return Path(os.environ.get("PROGRAMDATA") or r"C:\ProgramData") / "Gesprekstool"
    return Path("/etc/gesprekstool")


def laad_config():
    """Instellingen: standaard < computer (ICT) < pakket < gebruiker."""
    CFG.clear()
    CFG.update(STANDAARD)
    for map_ in (systeem_map(), app_map(), gebruikers_map()):
        pad = map_ / "config.json"
        if pad.is_file():
            try:
                CFG.update(json.loads(pad.read_text("utf-8-sig")))
            except ValueError as e:
                raise Fout("Het instellingenbestand is ongeldig:\n%s\n(%s)" % (pad, e))
    return CFG


def data_map():
    if CFG["data_map"]:
        return Path(os.path.expandvars(str(CFG["data_map"]))).expanduser()
    if WINDOWS:
        return gebruikers_map() / "Gesprekken"
    return Path.home() / "GesprekkenLokaal"


def templates():
    """Naam -> pad. Eigen templates van de gebruiker gaan voor die van ICT en het pakket."""
    gevonden = {}
    for map_ in (app_map() / "templates", systeem_map() / "templates", gebruikers_map() / "templates"):
        if map_.is_dir():
            for pad in sorted(map_.glob("*.txt")):
                gevonden[pad.stem] = pad
    return dict(sorted(gevonden.items()))


def model_mappen():
    mappen = []
    if os.environ.get("GESPREKSTOOL_MODELLEN"):
        mappen.append(Path(os.environ["GESPREKSTOOL_MODELLEN"]))
    mappen += [gebruikers_map() / "models", systeem_map() / "models", app_map() / "models"]
    if MAC and BEVROREN:      # map 'models' naast Gesprekstool.app
        mappen.append(app_map().parent.parent.parent / "models")
    return mappen


def zoek_model(soort):
    """soort is 'whisper' of 'llm'. Geeft het pad of None."""
    ingesteld = CFG.get(soort + "_model")
    if ingesteld:
        pad = Path(os.path.expandvars(str(ingesteld))).expanduser()
        return pad if pad.is_file() else None
    patroon = "ggml-*.bin" if soort == "whisper" else "*.gguf"
    for map_ in model_mappen():
        if map_.is_dir():
            gevonden = sorted(map_.glob(patroon))
            if gevonden:
                return gevonden[0]
    return None


def zoek_binair(submap, naam):
    """Zoekt eerst in het pakket (bin/<submap>/), daarna op het zoekpad."""
    bestand = naam + (".exe" if WINDOWS else "")
    lokaal = app_map() / "bin" / submap / bestand
    if lokaal.is_file():
        return str(lokaal)
    pad = os.pathsep.join([os.environ.get("PATH", ""), "/opt/homebrew/bin", "/usr/local/bin"])
    return shutil.which(naam, path=pad)


def _vereis_binair(submap, naam):
    pad = zoek_binair(submap, naam)
    if not pad:
        raise Fout("Het onderdeel '%s' ontbreekt in de installatie. Neem contact op met ICT." % naam)
    return pad


def _vereis_model(soort):
    pad = zoek_model(soort)
    if not pad:
        naam = "spraakmodel" if soort == "whisper" else "taalmodel"
        raise Fout("Het %s ontbreekt op deze computer. Neem contact op met ICT." % naam)
    return pad


# ------------------------------------------------------------ hulpfuncties

def werkgeheugen_gb():
    try:
        if MAC:
            return int(subprocess.check_output(["/usr/sbin/sysctl", "-n", "hw.memsize"])) / 2 ** 30
        if WINDOWS:
            class Status(ctypes.Structure):
                _fields_ = [("lengte", ctypes.c_ulong), ("belasting", ctypes.c_ulong),
                            ("totaal", ctypes.c_ulonglong)] + [
                                (n, ctypes.c_ulonglong) for n in "abcdef"]
            status = Status()
            status.lengte = ctypes.sizeof(Status)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
            return status.totaal / 2 ** 30
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 2 ** 30
    except Exception:
        return 0


def context_tokens():
    return int(CFG["context_tokens"]) or (16384 if werkgeheugen_gb() >= 15 else 8192)


def in_sandbox(cmd, loopback=False):
    """macOS: start het commando zonder netwerk (optioneel alleen 127.0.0.1)."""
    if not (MAC and CFG["netwerkblokkade"]):
        return cmd
    if not os.path.exists(SANDBOX_EXEC):
        raise Fout("De netwerkblokkade (sandbox-exec) is niet beschikbaar op deze Mac.")
    return [SANDBOX_EXEC, "-p", SB_ALLEEN_LOOPBACK if loopback else SB_GEEN_NETWERK] + cmd


def kind_env():
    env = {k: v for k, v in os.environ.items() if "proxy" not in k.lower()}
    env["LLAMA_ARG_OFFLINE"] = "1"
    env["HF_HUB_OFFLINE"] = "1"
    return env


def start_proces(cmd, loopback=False, **kw):
    return subprocess.Popen(in_sandbox([str(c) for c in cmd], loopback), stdin=subprocess.DEVNULL,
                            env=kind_env(), creationflags=_GEEN_VENSTER, **kw)


def staart(pad, regels=12):
    try:
        tekst = Path(pad).read_text("utf-8", errors="replace")
    except OSError:
        return ""
    return "\n".join(tekst.splitlines()[-regels:])


def log(map_, tekst):
    try:
        with open(str(Path(map_) / "verwerking.log"), "a", encoding="utf-8") as f:
            f.write("[%s] %s\n" % (datetime.datetime.now().strftime("%H:%M:%S"), tekst))
    except OSError:
        pass


def slug(tekst):
    return re.sub(r"[^\w\-]+", "-", tekst.strip().lower(), flags=re.UNICODE).strip("-")[:40]


def duur_tekst(seconden):
    seconden = int(seconden)
    return "%02d:%02d:%02d" % (seconden // 3600, seconden % 3600 // 60, seconden % 60)


def wav_duur(pad):
    """Lengte in seconden van een WAV zoals opname.py die schrijft (0 als onbekend)."""
    try:
        with open(str(pad), "rb") as f:
            kop = f.read(44)
        if len(kop) < 44 or kop[:4] != b"RIFF" or kop[36:40] != b"data":
            return 0
        bytes_per_seconde = struct.unpack("<I", kop[28:32])[0]
        return (os.path.getsize(str(pad)) - 44) / float(bytes_per_seconde or 1)
    except OSError:
        return 0


_wakker = {"proc": None}


def houd_wakker(aan):
    """Voorkom dat de laptop in slaap valt tijdens opnemen en verwerken."""
    try:
        if MAC:
            if aan and not _wakker["proc"]:
                _wakker["proc"] = subprocess.Popen(["/usr/bin/caffeinate", "-i", "-w", str(os.getpid())])
            elif not aan and _wakker["proc"]:
                _wakker["proc"].terminate()
                _wakker["proc"] = None
        elif WINDOWS:
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000001 if aan else 0x80000000)
    except Exception:
        pass


def open_map(pad):
    if WINDOWS:
        os.startfile(str(pad))                      # noqa: alleen Windows
    else:
        subprocess.Popen(["/usr/bin/open" if MAC else "xdg-open", str(pad)])


# -------------------------------------------------------------- gesprekken

def beveilig_map(pad):
    pad.mkdir(parents=True, exist_ok=True)
    if not WINDOWS:
        os.chmod(str(pad), 0o700)


def nieuw_gesprek(template, naam):
    nu = datetime.datetime.now()
    basis = data_map()
    beveilig_map(basis)
    delen = [nu.strftime("%Y-%m-%d_%H%M"), slug(template)] + ([slug(naam)] if slug(naam) else [])
    doel = basis / "_".join(delen)
    teller = 2
    while doel.exists():
        doel = basis / ("_".join(delen) + "_%d" % teller)
        teller += 1
    beveilig_map(doel)
    meta = {"datum": nu.strftime("%d-%m-%Y %H:%M"), "naam": naam.strip(), "template": template}
    (doel / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), "utf-8")
    return doel, meta


def lees_meta(map_):
    meta = {"datum": "", "naam": "", "template": ""}
    try:
        meta.update(json.loads((Path(map_) / "meta.json").read_text("utf-8")))
    except (OSError, ValueError):
        pass
    return meta


def status_gesprek(map_):
    map_ = Path(map_)
    if (map_ / "verslag.txt").is_file():
        return "klaar"
    if (map_ / "transcript.txt").is_file():
        return "transcript"
    wav = map_ / "opname.wav"
    if wav.is_file() and wav.stat().st_size > 1000:
        return "opname"
    return "leeg"


def lijst_gesprekken():
    """Nieuwste eerst: lijst van (map, meta, status)."""
    basis = data_map()
    if not basis.is_dir():
        return []
    uit = []
    for map_ in sorted(basis.iterdir(), reverse=True):
        if (map_ / "meta.json").is_file():
            uit.append((map_, lees_meta(map_), status_gesprek(map_)))
    return uit


def verwijder_gesprek(map_):
    map_ = Path(map_)
    if map_.parent.resolve() != data_map().resolve() or not (map_ / "meta.json").is_file():
        raise Fout("Deze map is geen gesprek van de gesprekstool:\n%s" % map_)
    shutil.rmtree(str(map_))


def ruim_audio_op():
    """Wis opnames waarvan het verslag ouder is dan de bewaartermijn. Geeft het aantal terug."""
    dagen = CFG["audio_bewaren_dagen"]
    if not dagen:
        return 0
    grens = time.time() - float(dagen) * 86400
    gewist = 0
    for map_, _meta, status in lijst_gesprekken():
        wav, verslag = map_ / "opname.wav", map_ / "verslag.txt"
        try:
            if status == "klaar" and wav.is_file() and verslag.stat().st_mtime < grens:
                wav.unlink()
                log(map_, "Opname gewist na bewaartermijn van %s dagen." % dagen)
                gewist += 1
        except OSError:
            pass
    return gewist


# ------------------------------------------------------------- verwerking

SAMENVAT_PROMPT = """Je maakt gespreksverslagen voor een docent of mentor.
Hieronder staat {bronsoort} van een gesprek ({soort}). De tekst is automatisch \
getranscribeerd: er kunnen fouten in staan en sprekers zijn niet gelabeld.

Vul het template in op basis van deze tekst. Regels:
- Gebruik alleen informatie uit de tekst. Verzin niets en vul niets aan.
- Schrijf "Niet besproken" bij onderdelen waarover niets is gezegd.
- Schrijf zakelijk, neutraal en in het Nederlands.
- Behoud de koppen en de volgorde van het template exact.
- Gebruik gewone tekst zonder opmaaktekens (geen #, * of tabellen). Gebruik een \
streepje (-) voor opsommingen.
- Negeer losse zinnen die duidelijk niet bij het gesprek horen, zoals ondertitel- of \
omroepteksten.
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


def maak_schoon(tekst):
    """Haal opmaaktekens weg die het taalmodel soms toch toevoegt."""
    tekst = tekst.strip()
    m = re.match(r"^```[a-zA-Z]*\n(.*)\n```$", tekst, flags=re.DOTALL)
    if m:
        tekst = m.group(1).strip()
    tekst = re.sub(r"^#{1,6}\s*", "", tekst, flags=re.MULTILINE)
    tekst = tekst.replace("**", "").replace("__", "")
    tekst = re.sub(r"^(\s*)\*\s+", r"\1- ", tekst, flags=re.MULTILINE)
    return tekst.strip() + "\n"


class Verwerking:
    """Maakt van opname.wav een transcript en een verslag. Kan worden geannuleerd."""

    def __init__(self, map_, meta, status=None, voortgang=None, tekst=None):
        self.map = Path(map_)
        self.meta = meta
        self.status = status or (lambda t: None)        # korte statusregel
        self.voortgang = voortgang or (lambda f: None)  # 0..1 of None (onbekend)
        self.tekst = tekst or (lambda s: None)          # stukjes verslag terwijl het ontstaat
        self._proc = None
        self._stop = threading.Event()
        self._port = None
        self.logpad = self.map / "verwerking.log"

    # -- besturing
    def annuleer(self):
        self._stop.set()
        proc = self._proc
        if proc and proc.poll() is None:
            proc.terminate()

    def _controleer(self):
        if self._stop.is_set():
            raise Geannuleerd()

    def uitvoeren(self):
        """Transcribeer (als dat nog niet gebeurd is) en maak het verslag. Geeft het pad terug."""
        if not (self.map / "transcript.txt").is_file():
            self.transcribeer()
        return self.samenvat()

    # -- transcriberen
    def transcribeer(self):
        wav = self.map / "opname.wav"
        if not wav.is_file() or wav.stat().st_size < 1000:
            raise Fout("Er is geen opname gevonden om te verwerken.")
        binair = _vereis_binair("whisper", "whisper-cli")
        model = _vereis_model("whisper")
        totaal = wav_duur(wav)
        uit = self.map / "transcript_bezig.txt"
        self.status("Stap 1 van 2: gesprek uitschrijven...")
        self.voortgang(0.0 if totaal else None)
        for gpu in ([True, False] if CFG["gpu"] else [False]):
            if uit.exists():
                uit.unlink()
            cmd = [binair, "-m", model, "-f", "opname.wav", "-l", CFG["taal"], "-otxt",
                   "-of", "transcript_bezig", "-t", str(min(8, os.cpu_count() or 4))]
            if not gpu:
                cmd.append("-ng")
            if CFG.get("whisper_prompt"):
                cmd += ["--prompt", CFG["whisper_prompt"]]
            log(self.map, "Start: " + " ".join(str(c) for c in cmd))
            with open(str(self.logpad), "ab") as logf:
                self._proc = start_proces(cmd, cwd=str(self.map), stdout=subprocess.PIPE, stderr=logf)
            for ruw in self._proc.stdout:
                m = re.search(rb"-->\s*(\d+):(\d+):(\d+)", ruw)
                if m and totaal:
                    h, mnt, s = (int(x) for x in m.groups())
                    self.voortgang(min(1.0, (h * 3600 + mnt * 60 + s) / totaal))
            self._proc.stdout.close()
            code = self._proc.wait()
            self._controleer()
            if code == 0 and uit.is_file():
                break
            log(self.map, "whisper-cli stopte met code %s (gpu=%s)" % (code, gpu))
        else:
            raise Fout("Het uitschrijven van het gesprek is mislukt.\n\n" + staart(self.logpad))
        if not uit.read_text("utf-8", errors="replace").strip():
            uit.unlink()
            raise Fout("Er is geen spraak herkend in de opname. Controleer de microfoon.")
        os.replace(str(uit), str(self.map / "transcript.txt"))
        self.voortgang(1.0)

    # -- taalmodel
    def _start_llm(self):
        binair = _vereis_binair("llama", "llama-server")
        model = _vereis_model("llm")
        for gpu in ([True, False] if CFG["gpu"] else [False]):
            with socket.socket() as s:
                s.bind(("127.0.0.1", 0))
                self._port = s.getsockname()[1]
            cmd = [binair, "-m", model, "--host", "127.0.0.1", "--port", str(self._port),
                   "-c", str(context_tokens()), "-ngl", "99" if gpu else "0", "-np", "1"]
            log(self.map, "Start: " + " ".join(str(c) for c in cmd))
            with open(str(self.logpad), "ab") as logf:
                self._proc = start_proces(cmd, loopback=True, stdout=logf, stderr=subprocess.STDOUT)
            eind = time.time() + 600
            while time.time() < eind and self._proc.poll() is None:
                self._controleer()
                try:
                    with OPENER.open("http://127.0.0.1:%d/health" % self._port, timeout=2) as r:
                        if r.status == 200:
                            return
                except OSError:
                    pass
                time.sleep(0.4)
            self._controleer()
            self._stop_llm()
            log(self.map, "llama-server startte niet (gpu=%s)" % gpu)
        raise Fout("Het taalmodel kon niet starten.\n\n" + staart(self.logpad))

    def _stop_llm(self):
        proc = self._proc
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()

    def _vraag(self, prompt, max_tokens, toon=False):
        body = json.dumps({
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "max_tokens": max_tokens,
            "stream": True,
        }).encode("utf-8")
        req = urllib.request.Request("http://127.0.0.1:%d/v1/chat/completions" % self._port,
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
                            self.tekst(stuk)
        except urllib.error.HTTPError as e:
            raise Fout("Het taalmodel gaf een fout: %s\n%s"
                       % (e, e.read().decode("utf-8", errors="replace")[:500]))
        except (OSError, ValueError) as e:
            self._controleer()          # afgebroken verbinding door annuleren
            raise Fout("De verbinding met het taalmodel is verbroken (%s).\n\n%s"
                       % (e, staart(self.logpad)))
        self._controleer()
        return "".join(delen).strip()

    # -- samenvatten
    def samenvat(self):
        transcript = (self.map / "transcript.txt").read_text("utf-8", errors="replace").strip()
        if not transcript:
            raise Fout("Het transcript is leeg.")
        soort = self.meta.get("template") or ""
        pad = templates().get(soort)
        if not pad:
            raise Fout("Het template '%s' bestaat niet (meer)." % soort)
        template = pad.read_text("utf-8-sig")
        for sleutel, waarde in (("{datum}", self.meta.get("datum", "")),
                                ("{naam}", self.meta.get("naam") or "Onbekend")):
            template = template.replace(sleutel, waarde)

        context = context_tokens()
        budget = (context - UITVOER_TOKENS - 600) * TEKENS_PER_TOKEN - len(template)
        if budget < 3000:
            raise Fout("Het contextvenster (%d) is te klein voor dit template." % context)
        deel_budget = (context - NOTITIE_TOKENS - 400) * TEKENS_PER_TOKEN

        self.status("Stap 2 van 2: taalmodel laden...")
        self.voortgang(None)
        self._start_llm()
        try:
            bron, bronsoort, bronkop = transcript, "het transcript", "TRANSCRIPT"
            ronde = 0
            while len(bron) > budget:
                ronde += 1
                if ronde > 3:
                    raise Fout("Het gesprek is te lang om samen te vatten met dit model.")
                stukken = splits(bron, deel_budget)
                notities = []
                for i, stuk in enumerate(stukken, 1):
                    self.status("Stap 2 van 2: lang gesprek lezen (deel %d van %d)..." % (i, len(stukken)))
                    self.voortgang((i - 1) / float(len(stukken)))
                    notities.append("[Deel %d]\n%s" % (i, self._vraag(NOTITIE_PROMPT.format(
                        i=i, n=len(stukken), soort=soort, stuk=stuk), NOTITIE_TOKENS)))
                bron, bronsoort, bronkop = "\n\n".join(notities), "aantekeningen", "AANTEKENINGEN"
            self.status("Stap 2 van 2: verslag schrijven...")
            self.voortgang(None)
            tekst = self._vraag(SAMENVAT_PROMPT.format(
                bronsoort=bronsoort, bronkop=bronkop, soort=soort, template=template, bron=bron),
                UITVOER_TOKENS, toon=True)
        finally:
            self._stop_llm()
        if not tekst:
            raise Fout("Het taalmodel gaf geen verslag terug.\n\n" + staart(self.logpad))
        doel = self.map / "verslag.txt"
        doel.write_text(maak_schoon(tekst), "utf-8")
        log(self.map, "Verslag opgeslagen.")
        return doel


# ---------------------------------------------------------------- controle

def eigen_commando():
    """Commando waarmee dit programma zichzelf kan starten (voor de netwerkproef)."""
    if BEVROREN:
        return [sys.executable]
    return [sys.executable, str(Path(__file__).resolve().parent.parent / "start.py")]


def netwerkproef(soort):
    """Draait binnen de sandbox. Geeft 0 terug als het gedrag klopt.

    'extern': verbinden met een extern adres moet door de sandbox geweigerd worden.
    192.0.2.1 is een gereserveerd documentatie-adres: er bestaat geen host achter.
    'lus': een verbinding binnen de computer (127.0.0.1) moet wel werken.
    """
    import errno
    try:
        if soort == "extern":
            s = socket.socket()
            s.settimeout(2)
            try:
                s.connect(("192.0.2.1", 9))
            except OSError as e:
                return 0 if e.errno == errno.EPERM else 3
            return 3
        a = socket.socket()
        a.bind(("127.0.0.1", 0))
        a.listen(1)
        b = socket.socket()
        b.settimeout(3)
        b.connect(a.getsockname())
        return 0
    except OSError:
        return 4


def controle(sd=None):
    """Controleert of de laptop klaar is voor gebruik. Geeft een lijst (niveau, tekst).

    niveau: 'ok', 'let_op' (werkt, maar verdient aandacht) of 'fout' (werkt niet).
    """
    uit = []

    def regel(goed, tekst, let_op=False):
        uit.append(("ok" if goed else ("let_op" if let_op else "fout"), tekst))

    for submap, naam, omschrijving in (("whisper", "whisper-cli", "Spraakherkenning"),
                                       ("llama", "llama-server", "Taalmodel-programma")):
        pad = zoek_binair(submap, naam)
        regel(bool(pad), "%s (%s): %s" % (omschrijving, naam, pad or "ontbreekt"))
    for soort, omschrijving in (("whisper", "Spraakmodel"), ("llm", "Taalmodel")):
        pad = zoek_model(soort)
        regel(bool(pad), "%s: %s" % (omschrijving, pad.name if pad else
                                     "ontbreekt (verwacht in %s)" % (systeem_map() / "models")))
    namen = list(templates())
    regel(bool(namen), "Templates: %s" % (", ".join(namen) or "geen gevonden"))

    try:
        from . import opname
        opname.controleer_microfoon(CFG["microfoon"], sd)
        regel(True, "Microfoon gevonden")
    except Exception as e:
        regel(False, "Microfoon: %s" % e)

    gb = werkgeheugen_gb()
    regel(gb >= 15, "Werkgeheugen: %.0f GB%s" % (
        gb, "" if gb >= 15 else " (16 GB aanbevolen; verwerken gaat langzamer)"), let_op=True)

    basis = data_map()
    try:
        beveilig_map(basis)
        echt = str(basis.resolve())
        vrij = shutil.disk_usage(echt).free / 2 ** 30
    except OSError as e:
        regel(False, "Opslagmap %s kan niet worden gebruikt (%s)" % (basis, e))
    else:
        verdacht = [w for w in ("Mobile Documents", "CloudStorage", "Dropbox", "OneDrive",
                                "Google Drive", "iCloud") if w.lower() in echt.lower()]
        if echt.startswith("\\\\"):
            verdacht.append("netwerkschijf")
        thuis = str(Path.home())
        verdacht += [m for m in ("Documents", "Desktop")
                     if echt.startswith(os.path.join(thuis, m) + os.sep)]
        regel(not verdacht, "Opslagmap: %s%s" % (echt, (
            " staat in een map die mogelijk met de cloud of het netwerk synchroniseert (%s)"
            % ", ".join(verdacht)) if verdacht else " (alleen op deze computer)"))
        regel(vrij >= 2, "Vrije schijfruimte: %.0f GB" % vrij, let_op=vrij >= 0.5)

        if MAC:
            def uitvoer(cmd):
                try:
                    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                    return r.stdout.decode("utf-8", errors="replace")
                except OSError:
                    return ""
            regel("FileVault is On" in uitvoer(["/usr/bin/fdesetup", "status"]),
                  "Schijfversleuteling (FileVault) staat aan", let_op=True)
            if "[Excluded]" not in uitvoer(["/usr/bin/tmutil", "isexcluded", echt]):
                uitvoer(["/usr/bin/tmutil", "addexclusion", echt])
            regel("[Excluded]" in uitvoer(["/usr/bin/tmutil", "isexcluded", echt]),
                  "Opslagmap is uitgesloten van Time Machine-back-ups", let_op=True)

    if MAC:
        if not CFG["netwerkblokkade"]:
            regel(False, "Netwerkblokkade staat UIT in de instellingen", let_op=True)
        elif not os.path.exists(SANDBOX_EXEC):
            regel(False, "Netwerkblokkade: sandbox-exec ontbreekt")
        else:
            def proef(profiel, soort):
                try:
                    return subprocess.call([SANDBOX_EXEC, "-p", profiel] + eigen_commando()
                                           + ["--netwerkproef", soort], timeout=60)
                except (OSError, subprocess.TimeoutExpired):
                    return 9
            regel(proef(SB_GEEN_NETWERK, "extern") == 0,
                  "Netwerkblokkade: spraakherkenning kan niet naar buiten")
            regel(proef(SB_ALLEEN_LOOPBACK, "extern") == 0,
                  "Netwerkblokkade: taalmodel kan niet naar buiten")
            regel(proef(SB_ALLEEN_LOOPBACK, "lus") == 0,
                  "Interne verbinding met het taalmodel (127.0.0.1) werkt")
    elif WINDOWS:
        try:
            code = subprocess.call(["netsh", "advfirewall", "firewall", "show", "rule",
                                    "name=" + FIREWALL_REGEL], stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL, creationflags=_GEEN_VENSTER)
        except OSError:
            code = 1
        regel(code == 0, "Netwerkblokkade: firewallregel '%s' %s" % (
            FIREWALL_REGEL, "is aanwezig" if code == 0 else
            "ontbreekt. De tool gebruikt zelf geen netwerk, maar dit wordt niet afgedwongen "
            "(ICT: zie BEHEER.md)"), let_op=True)
    else:
        regel(False, "Netwerkblokkade wordt op dit systeem niet afgedwongen", let_op=True)
    return uit


def is_gereed(resultaten):
    return not any(niveau == "fout" for niveau, _ in resultaten)
