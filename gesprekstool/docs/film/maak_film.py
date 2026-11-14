#!/usr/bin/env python3
"""Maakt de instructiefilm van de gesprekstool (docs/instructiefilm.mp4).

De film toont de echte schermen van de tool. De microfoon, de spraakherkenning en het
taalmodel zijn nagebootst (zoals in de tests): het gesprek en het verslag in de film zijn
een fictief voorbeeld.

Nodig: Linux met Xvfb, ffmpeg, Python met tkinter en Pillow, lettertype Inter.

    xvfb-run -a -s "-screen 0 1280x900x24" python3 docs/film/maak_film.py

Voice-over: zet per scene een bestand docs/film/audio/s01.mp3 ... s11.mp3 neer (de tekst
staat in SCENES en in docs/instructiefilm-script.md). Zonder audio wordt de film stil, met
ondertitels, en wordt de lengte per scene geschat.
"""
import json
import math
import os
import random
import re
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageGrab

HIER = Path(__file__).resolve().parent
ROOT = HIER.parent.parent                      # map gesprekstool/
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
import nep  # noqa: E402

FPS = 12
B, H = 1280, 720
AANLOOP, UITLOOP = 0.35, 0.75                  # stilte voor en na de stem, in seconden
TEKENS_PER_SECONDE = 13.5                      # schatting als er geen audio is
LETTER = "/usr/share/fonts/opentype/inter/Inter-%s.otf"
DONKER, PANEEL, WIT, ZACHT, ACCENT, GEEL = "#12203a", "#1b2d4f", "#ffffff", "#aebbd2", "#5b9bff", "#ffc83d"

VERSLAG = """VERSLAG OUDERGESPREK

Datum: {datum}
Leerling: Sam de Vries
Aanwezig: moeder en vader van Sam, mentor

AANLEIDING EN DOEL VAN HET GESPREK
Voortgangsgesprek na het eerste rapport. Ouders willen weten hoe het gaat met wiskunde en met het plannen van huiswerk.

HOE GAAT HET MET DE LEERLING (THUIS EN OP SCHOOL)
- Sam gaat met plezier naar school en heeft een vaste vriendengroep.
- Thuis begint Sam vaak laat aan het huiswerk.

LEERRESULTATEN EN WERKHOUDING
- Nederlands en geschiedenis gaan goed.
- Wiskunde is onvoldoende; Sam vraagt in de les weinig hulp.

WAT GAAT GOED
- Sam is behulpzaam en werkt goed samen.

ZORGEN EN AANDACHTSPUNTEN
- Plannen van huiswerk en toetsen.
- Achterstand bij wiskunde.

AFSPRAKEN (WAT, WIE, WANNEER)
- Sam gebruikt een weekplanner en bespreekt die op maandag met de mentor (Sam en mentor, vanaf volgende week).
- Sam gaat naar de steunles wiskunde (Sam, elke dinsdag).
- Ouders kijken op zondag mee met de planning (ouders, wekelijks).

VERVOLG
Vervolggesprek over zes weken.
"""

CONTROLE = [
    ("ok", "Spraakherkenning (whisper-cli): aanwezig"),
    ("ok", "Taalmodel-programma (llama-server): aanwezig"),
    ("ok", "Spraakmodel: ggml-large-v3-turbo.bin"),
    ("ok", "Taalmodel: gemma-3-12b-it-Q4_K_M.gguf"),
    ("ok", "Templates: leerlinggesprek, oudergesprek"),
    ("ok", "Microfoon gevonden"),
    ("ok", "Werkgeheugen: 16 GB"),
    ("ok", "Opslagmap: /Users/docent/GesprekkenLokaal (alleen op deze computer)"),
    ("ok", "Schijfversleuteling (FileVault) staat aan"),
    ("ok", "Opslagmap is uitgesloten van Time Machine-back-ups"),
    ("ok", "Netwerkblokkade: spraakherkenning kan niet naar buiten"),
    ("ok", "Netwerkblokkade: taalmodel kan niet naar buiten"),
    ("ok", "Interne verbinding met het taalmodel (127.0.0.1) werkt"),
]

# soort: 'titel', 'kaart' (uitleg) of de naam van een schermopname.
SCENES = [
    dict(soort="titel", kop="Gesprekstool",
         punten=["Gesprekken opnemen en samenvatten,", "volledig op je eigen laptop"],
         tekst="De Gesprekstool. Gesprekken opnemen en samenvatten, volledig op je eigen laptop."),
    dict(soort="kaart", kop="Waarom de Gesprekstool?",
         punten=["Neemt het gesprek op", "Schrijft het gesprek uit",
                 "Maakt een conceptverslag in het template van de school",
                 "Jij leest na en zet het in het leerlingvolgsysteem"],
         tekst="Na een oudergesprek of leerlinggesprek hoort een verslag. Dat kost tijd. "
               "De Gesprekstool neemt het gesprek op, schrijft het uit en maakt een conceptverslag "
               "volgens het vaste template van de school. Jij leest het na en zet het in het "
               "leerlingvolgsysteem."),
    dict(soort="start", stap="Stap 1", kop="Gesprek starten",
         punten=["Kies het soort gesprek", "Vul de naam van de leerling in",
                 "Meld dat je opneemt en vink dat aan", "Klik op Start opname"],
         tekst="Zo werkt het. Open de Gesprekstool. Kies het soort gesprek en vul de naam van de "
               "leerling in. Vertel de aanwezigen dat je het gesprek opneemt en vink dat aan. "
               "Klik dan op Start opname."),
    dict(soort="opname", stap="Stap 2", kop="Opnemen",
         punten=["De groene balk beweegt: de microfoon hoort geluid",
                 "Pauze bij een vertrouwelijk moment", "Klaar? Stop en maak verslag"],
         tekst="De opname loopt. De groene balk laat zien dat de microfoon geluid opvangt. "
               "Wil iemand iets vertrouwelijks zeggen? Klik dan op Pauze. "
               "Is het gesprek klaar, klik dan op Stop en maak verslag."),
    dict(soort="verwerk", stap="Stap 3", kop="De laptop maakt het verslag",
         punten=["Het gesprek wordt uitgeschreven", "Het verslag wordt geschreven",
                 "Dit duurt enkele minuten: laat de laptop open staan"],
         tekst="De laptop schrijft het gesprek nu uit en maakt het verslag. Dat duurt een paar "
               "minuten. Laat de laptop open staan; je hoeft er niet bij te blijven."),
    dict(soort="verslag", stap="Stap 4", kop="Nalezen en overnemen",
         punten=["Lees het verslag altijd na", "Verbeter wat niet klopt",
                 "Kopieer het verslag naar het leerlingvolgsysteem"],
         tekst="Het verslag verschijnt in het template van de school. Lees het altijd na en "
               "verbeter wat niet klopt: de computer kan zich vergissen. Klik op Kopieer verslag "
               "en plak het in het leerlingvolgsysteem."),
    dict(soort="kaart", kop="Wat kan de tool nog meer?",
         punten=["Eigen templates van de school, bijvoorbeeld voor een zorgoverleg",
                 "Een verslag later afmaken via Eerdere gesprekken",
                 "Opnames worden na 14 dagen automatisch gewist",
                 "Werkt op Mac en op Windows"],
         tekst="Wat kan de tool nog meer? De school kan eigen templates toevoegen, bijvoorbeeld "
               "voor een zorgoverleg. Eerdere gesprekken blijven in de lijst staan, zodat je een "
               "verslag later kunt afmaken. Opnames worden na veertien dagen automatisch gewist. "
               "En de tool werkt op Mac en op Windows."),
    dict(soort="controle", stap="Privacy", kop="Alles blijft op de laptop",
         punten=["Geen internet nodig", "Er gaat niets naar de cloud",
                 "De verwerking krijgt geen toegang tot het netwerk",
                 "De knop Controle laat zien of alles in orde is"],
         tekst="Het belangrijkste: alles blijft op de laptop. Er is geen internet nodig en er gaat "
               "niets naar de cloud. De onderdelen die de opname verwerken, krijgen geen toegang "
               "tot het netwerk. Met de knop Controle zie je of alles in orde is."),
    dict(soort="kaart", kop="Wat is er nodig op school?",
         punten=["Laptop: Mac met Apple-chip of Windows, liefst 16 GB werkgeheugen",
                 "Geen server en geen abonnement",
                 "ICT haalt eenmalig het pakket en de AI-modellen op",
                 "Installeren met een script, daarna een proefopname met de docent"],
         tekst="Wat is er nodig op school? Een laptop met bij voorkeur zestien gigabyte "
               "werkgeheugen: een Mac met Apple-chip of een Windows-laptop. Geen server en geen "
               "abonnement. ICT haalt een keer het pakket en de AI-modellen op, installeert de "
               "tool met een script en doet samen met de docent een proefopname."),
    dict(soort="kaart", kop="Goede afspraken vooraf",
         punten=["Meld altijd dat je opneemt", "Lees elk verslag na", "Bewaar opnames kort",
                 "Betrek de functionaris gegevensbescherming",
                 "Begin met een kleine proef"],
         tekst="Maak vooraf een paar afspraken. Meld altijd dat je opneemt. Lees elk verslag na. "
               "Bewaar opnames kort. Betrek de functionaris gegevensbescherming en begin met een "
               "kleine proef."),
    dict(soort="titel", kop="Gesprekstool",
         punten=["Minder tijd aan verslagen,", "meer aandacht voor het gesprek"],
         voet="Handleiding voor docenten: README   -   Beheer en advies voor de school: BEHEER",
         tekst="De Gesprekstool: minder tijd aan verslagen, meer aandacht voor het gesprek. "
               "Meer weten? Lees de handleiding of vraag het aan ICT."),
]

# ----------------------------------------------------------------- hulpjes


def letter(gewicht, grootte):
    return ImageFont.truetype(LETTER % gewicht, grootte)


def audio_pad(i):
    return HIER / "audio" / ("s%02d.mp3" % (i + 1))


def audio_duur(pad):
    uit = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                          "csv=p=0", str(pad)], capture_output=True, text=True, check=True)
    return float(uit.stdout.strip())


def scene_duur(i):
    """(lengte van de scene, lengte van de stem) in seconden."""
    pad = audio_pad(i)
    stem = audio_duur(pad) if pad.exists() else len(SCENES[i]["tekst"]) / TEKENS_PER_SECONDE
    return AANLOOP + stem + UITLOOP, stem


def ondertitels(tekst):
    """Knip de tekst in korte stukken; geeft [(begin, eind, tekst)] als fracties van de stem."""
    stukken = []
    for zin in re.split(r"(?<=[.?!:;])\s+", tekst.strip()):
        while len(zin) > 88:
            knip = max(zin.rfind(", ", 30, 80), zin.rfind(" en ", 30, 80), zin.rfind(" of ", 30, 80))
            knip = knip if knip > 0 else zin.rfind(" ", 30, 80)
            stukken.append(zin[:knip + 1].strip())
            zin = zin[knip + 1:].strip()
        stukken.append(zin)
    totaal = float(sum(len(s) for s in stukken))
    uit, t = [], 0.0
    for s in stukken:
        uit.append((t, t + len(s) / totaal, s))
        t += len(s) / totaal
    return uit


# ------------------------------------------------------ nagebootste delen

FILM_WHISPER = """
    import os, sys, time
    args = sys.argv[1:]
    duur = float(os.environ["FILM_WHISPER_S"])
    with open(args[args.index("-of") + 1] + ".txt", "w", encoding="utf-8") as f:
        f.write(open(os.environ["FILM_TRANSCRIPT"], encoding="utf-8").read())
    totaal = (os.path.getsize("opname.wav") - 44) / 32000.0     # lengte van de opname in seconden
    stappen = 40
    for i in range(1, stappen + 1):                              # laat de voortgang oplopen
        t = int(totaal * i / stappen)
        print("[00:00:00.000 --> %02d:%02d:%02d.000]   ..." % (t // 3600, t % 3600 // 60, t % 60), flush=True)
        time.sleep(duur / stappen)
"""

FILM_LLAMA = """
    import json, os, re, sys, time
    from http.server import BaseHTTPRequestHandler, HTTPServer
    args = sys.argv[1:]
    port = int(args[args.index("--port") + 1])
    duur = float(os.environ["FILM_LLM_S"])
    verslag = open(os.environ["FILM_VERSLAG"], encoding="utf-8").read()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass
        def do_GET(self):
            self.send_response(200 if self.path == "/health" else 404)
            self.end_headers()
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            datum = re.search(r"Datum: (.*)", body["messages"][0]["content"]).group(1)
            tekst = verslag.replace("{datum}", datum)
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            stukken = [tekst[i:i + 6] for i in range(0, len(tekst), 6)]
            for stuk in stukken:
                data = {"choices": [{"delta": {"content": stuk}}]}
                self.wfile.write(("data: %s\\n\\n" % json.dumps(data)).encode())
                self.wfile.flush()
                time.sleep(duur / len(stukken))
            self.wfile.write(b"data: [DONE]\\n\\n")

    time.sleep(float(os.environ["FILM_LADEN_S"]))
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()
"""


class FilmStream:
    """Microfoon met een 'pratend' geluidsniveau, zodat de balk beweegt zoals bij spraak."""

    def __init__(self, hz, callback):
        self.hz, self.callback = hz, callback
        self._stop = threading.Event()

    def start(self):
        def loop():
            n, sterkte, doel = self.hz // 50, 0.2, 0.5
            while not self._stop.wait(0.02):
                if random.random() < 0.15:
                    doel = random.choice([0.03, 0.15, 0.35, 0.5, 0.7])
                sterkte += (doel - sterkte) * 0.35
                piek = int(32000 * sterkte * sterkte)
                self.callback(struct.pack("<%dh" % n, *[int(piek * math.sin(i * 0.3)) for i in range(n)]),
                              n, None, None)
        threading.Thread(target=loop, daemon=True).start()

    def stop(self):
        self._stop.set()
        time.sleep(0.05)

    def close(self):
        pass


class FilmSd:
    def query_devices(self, device=None, kind=None):
        return {"name": "Microfoon", "max_input_channels": 1, "default_samplerate": 48000.0}

    def RawInputStream(self, samplerate, channels, dtype, device, callback, finished_callback):
        return FilmStream(samplerate, callback)


# ---------------------------------------------------------- schermopnamen

class Opnemer:
    """Bedient de app en bewaart per scene de schermbeelden en de aanwijzingen (markeringen)."""

    def __init__(self, werk):
        self.werk = werk
        self.tmp = Path(tempfile.mkdtemp(prefix="film-"))
        env = nep.maak_omgeving(self.tmp)
        nep.schrijf_config(env)
        for submap, naam, code in (("whisper", "whisper-cli", FILM_WHISPER),
                                   ("llama", "llama-server", FILM_LLAMA)):
            pad = Path(env["GESPREKSTOOL_APP"]) / "bin" / submap / naam
            pad.write_text("#!%s\n%s" % (sys.executable, textwrap.dedent(code)), "utf-8")
            pad.chmod(pad.stat().st_mode | stat.S_IEXEC)
        (self.tmp / "verslag.txt").write_text(VERSLAG, "utf-8")
        (self.tmp / "transcript.txt").write_text(
            " Fijn dat jullie er zijn. We bespreken vandaag hoe het met Sam gaat.\n"
            " Wij maken ons vooral zorgen over wiskunde en over het plannen.\n", "utf-8")
        os.environ.update(env)
        os.environ.update(FILM_VERSLAG=str(self.tmp / "verslag.txt"),
                          FILM_TRANSCRIPT=str(self.tmp / "transcript.txt"))

        from gesprekstool import kern, venster
        self.kern = kern
        kern.laad_config()
        kern.controle = lambda sd=None, meld=None: list(CONTROLE)
        # Twee eerdere gesprekken, zodat de lijst op het startscherm gevuld is.
        for naam, soort in (("Noor Bakker", "leerlinggesprek"), ("Daan Jansen", "oudergesprek")):
            map_, _ = kern.nieuw_gesprek(soort, naam)
            nep.maak_wav(map_ / "opname.wav", 0.3)
            (map_ / "verslag.txt").write_text("Voorbeeld", "utf-8")
        self.app = venster.App(sd=FilmSd())
        self.app.geometry("900x740+60+40")
        self.wacht(lambda: self.app.controle is not None)
        self.meta = {}

    def wacht(self, voorwaarde, seconden=60):
        eind = time.time() + seconden
        while time.time() < eind:
            self.app.update()
            if voorwaarde():
                return
            time.sleep(0.02)
        raise SystemExit("time-out in scherm '%s'" % self.app.scherm)

    def vak(self, widget):
        """Plek van een widget binnen het venster dat wordt opgenomen."""
        top = widget.winfo_toplevel()
        x, y = widget.winfo_rootx() - top.winfo_rootx(), widget.winfo_rooty() - top.winfo_rooty()
        return [x, y, x + widget.winfo_width(), y + widget.winfo_height()]

    def scene(self, i, frames, acties, venster=None, tot=None):
        """Neem `frames` beelden op. acties: [(fractie, functie)] -> functie geeft evt. een widget
        terug die gemarkeerd wordt. tot: stop zodra deze voorwaarde waar is (na alle acties)."""
        map_ = self.werk / ("s%02d" % (i + 1))
        map_.mkdir(parents=True)
        acties = sorted(acties, key=lambda a: a[0])
        marks, markeer_tot, huidig = {}, -1, None
        start, n = time.time(), 0
        while True:
            while acties and n >= acties[0][0] * frames:
                widget = acties.pop(0)[1]()
                if widget is not None:
                    huidig, markeer_tot = self.vak(widget), n + int(FPS * 1.1)
            doel = venster() if venster else self.app
            for _ in range(3):
                self.app.update()
            x, y = doel.winfo_rootx(), doel.winfo_rooty()
            beeld = ImageGrab.grab(bbox=(x, y, x + doel.winfo_width(), y + doel.winfo_height()),
                                   xdisplay=os.environ["DISPLAY"])
            beeld.save(str(map_ / ("%05d.png" % n)), compress_level=1)
            if n <= markeer_tot and huidig:
                marks[n] = huidig
            n += 1
            if n >= frames and not acties and (tot is None or tot() or n > frames + FPS * 20):
                break
            wacht = start + n / float(FPS) - time.time()
            if wacht > 0:
                time.sleep(wacht)
        self.meta["s%02d" % (i + 1)] = {"frames": n, "marks": marks}

    # -- de vijf schermopnamen
    def start(self, i, frames):
        app = self.app

        def typ(tekst):
            return lambda: app.w["naam"].set(tekst)

        def radio():
            app.w["soort"].set("oudergesprek")
            return [k for k in app.w["start"].master.winfo_children()
                    if k.winfo_class() == "Frame"][0].winfo_children()[1]

        def vink():
            app.w["gemeld"].set(True)
            app._werk_start_bij()
            return [k for k in app.w["start"].master.winfo_children()
                    if k.winfo_class() == "TCheckbutton"][0]

        naam = "Sam de Vries"
        acties = [(0.26, radio)]
        acties += [(0.40 + 0.14 * k / len(naam), typ(naam[:k + 1])) for k in range(len(naam))]
        acties += [(0.66, vink), (0.90, lambda: app.w["start"])]
        self.scene(i, frames, acties)
        app.w["start"].invoke()
        app.opname._bytes += 24 * 60 * app.opname.hz * 2 + 17 * app.opname.hz * 2   # 'al 24 minuten bezig'

    def opname(self, i, frames):
        app = self.app

        def pauze():
            app.pauzeer()
            return app.w["pauze"]

        def stop():
            return [k for k in app.w["pauze"].master.winfo_children() if k is not app.w["pauze"]][0]

        self.scene(i, frames, [(0.50, pauze), (0.68, pauze), (0.90, stop)])
        app.stop_opname()

    def verwerk(self, i, frames):
        self.scene(i, frames, [], tot=lambda: self.app.scherm == "verslag")

    def verslag(self, i, frames):
        app = self.app

        def kopieer():
            knop = [k for k in app.w["melding"].master.winfo_children() if k.winfo_class() == "Frame"
                    and any(c.winfo_class() == "TButton" for c in k.winfo_children())][0].winfo_children()[0]
            app.after(900, app.kopieer)
            return knop

        self.scene(i, frames, [(0.70, kopieer)])
        app.terug()

    def controle(self, i, frames):
        app = self.app

        def open_controle():
            app.toon_controle()
            return None

        knop = [k for k in app.winfo_children()[0].winfo_children() if k.winfo_class() == "TButton"][0]
        deel = int(frames * 0.42)
        self.scene(i, deel, [(0.55, lambda: knop)])
        self.meta["s%02da" % (i + 1)] = self.meta.pop("s%02d" % (i + 1))
        os.rename(str(self.werk / ("s%02d" % (i + 1))), str(self.werk / ("s%02da" % (i + 1))))
        open_controle()
        self.wacht(lambda: app._controlevenster.winfo_viewable())
        self.scene(i, frames - deel, [], venster=lambda: app._controlevenster)
        self.meta["s%02db" % (i + 1)] = self.meta.pop("s%02d" % (i + 1))
        os.rename(str(self.werk / ("s%02d" % (i + 1))), str(self.werk / ("s%02db" % (i + 1))))
        app._controlevenster.destroy()

    def alles(self):
        # Het verwerken start zodra de opname stopt (einde van de vorige scene) en duurt
        # ongeveer zo lang als de scene 'verwerk'. Daarom vooraf instellen.
        duur = scene_duur([s["soort"] for s in SCENES].index("verwerk"))[0]
        os.environ.update(FILM_WHISPER_S="%.1f" % (duur * 0.36), FILM_LADEN_S="%.1f" % (duur * 0.07),
                          FILM_LLM_S="%.1f" % (duur * 0.44))
        for i, scene in enumerate(SCENES):
            if scene["soort"] in ("titel", "kaart"):
                continue
            frames = int(round(scene_duur(i)[0] * FPS))
            getattr(self, scene["soort"])(i, frames)
            print("opgenomen: scene %d (%s), %d beelden" % (i + 1, scene["soort"], frames), flush=True)
        (self.werk / "meta.json").write_text(json.dumps(self.meta), "utf-8")
        self.app.destroy()
        shutil.rmtree(str(self.tmp), ignore_errors=True)


# ------------------------------------------------------------------ montage

def tekst_in_breedte(draw, tekst, font, breedte):
    regels, huidig = [], ""
    for woord in tekst.split():
        proef = (huidig + " " + woord).strip()
        if draw.textlength(proef, font=font) <= breedte:
            huidig = proef
        else:
            regels.append(huidig)
            huidig = woord
    return regels + [huidig]


def punten_tekenen(draw, punten, x, y, breedte, zichtbaar, font, afstand):
    for k, punt in enumerate(punten):
        regels = tekst_in_breedte(draw, punt, font, breedte - 34)
        if k < zichtbaar:
            draw.ellipse([x, y + 11, x + 12, y + 23], fill=ACCENT)
            for r, regel in enumerate(regels):
                draw.text((x + 34, y + r * (font.size + 8)), regel, font=font, fill=WIT)
        y += len(regels) * (font.size + 8) + afstand
    return y


def basis_kaart(scene, zichtbaar):
    beeld = Image.new("RGB", (B, H), DONKER)
    d = ImageDraw.Draw(beeld)
    if scene["soort"] == "titel":
        d.ellipse([B // 2 - 26, 170, B // 2 + 26, 222], fill="#e0453a")
        kop = letter("Bold", 84)
        d.text(((B - d.textlength(scene["kop"], font=kop)) / 2, 250), scene["kop"], font=kop, fill=WIT)
        f = letter("Medium", 36)
        for k, regel in enumerate(scene["punten"]):
            d.text(((B - d.textlength(regel, font=f)) / 2, 380 + k * 50), regel, font=f, fill=ZACHT)
        if scene.get("voet"):
            f = letter("Regular", 20)
            d.text(((B - d.textlength(scene["voet"], font=f)) / 2, 560), scene["voet"], font=f, fill=ZACHT)
        return beeld
    d.rectangle([90, 96, 98, 152], fill=ACCENT)
    d.text((122, 92), scene["kop"], font=letter("Bold", 52), fill=WIT)
    punten_tekenen(d, scene["punten"], 124, 210, 1030, zichtbaar, letter("Medium", 32), 30)
    return beeld


def basis_demo(scene, zichtbaar):
    beeld = Image.new("RGB", (B, H), DONKER)
    d = ImageDraw.Draw(beeld)
    d.rectangle([836, 0, B, H], fill=PANEEL)
    d.text((868, 54), scene["stap"].upper(), font=letter("Bold", 20), fill=ACCENT)
    y = 86
    for regel in tekst_in_breedte(d, scene["kop"], letter("Bold", 36), 380):
        d.text((868, y), regel, font=letter("Bold", 36), fill=WIT)
        y += 46
    punten_tekenen(d, scene["punten"], 868, y + 26, 380, zichtbaar, letter("Medium", 23), 24)
    d.text((868, 600), "Fictief voorbeeld", font=letter("Regular", 17), fill=ZACHT)
    return beeld


def ondertitel_tekenen(beeld, tekst):
    d = ImageDraw.Draw(beeld, "RGBA")
    f = letter("Medium", 25)
    regels = tekst_in_breedte(d, tekst, f, 1120)
    hoogte = len(regels) * 34 + 20
    boven = H - hoogte - 14
    d.rounded_rectangle([60, boven, B - 60, boven + hoogte], radius=12, fill=(0, 0, 0, 185))
    for k, regel in enumerate(regels):
        d.text(((B - d.textlength(regel, font=f)) / 2, boven + 10 + k * 34), regel, font=f, fill=WIT)


def monteer(werk, uit):
    meta = json.loads((werk / "meta.json").read_text("utf-8"))
    heeft_audio = all(audio_pad(i).exists() for i in range(len(SCENES)))
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", "%dx%d" % (B, H), "-r", str(FPS), "-i", "-"]
    lengtes = []

    def beelden():
        for i, scene in enumerate(SCENES):
            lengte, stem = scene_duur(i)
            demo = scene["soort"] not in ("titel", "kaart")
            delen = [k for k in sorted(meta) if k.startswith("s%02d" % (i + 1))] if demo else []
            frames = sum(meta[k]["frames"] for k in delen) if demo else int(round(lengte * FPS))
            lengtes.append(frames / float(FPS))
            bron = [(k, n) for k in delen for n in range(meta[k]["frames"])]
            titels = ondertitels(scene["tekst"])
            aantal = len(scene["punten"])
            kaders = {}
            for n in range(frames):
                t = n / float(FPS)
                fractie = min(1.0, max(0.0, (t - AANLOOP) / stem))
                zichtbaar = aantal if scene["soort"] == "titel" else min(
                    aantal, int(fractie * (aantal + 0.6) + 0.35) + (1 if demo else 0))
                if zichtbaar not in kaders:
                    kaders[zichtbaar] = (basis_demo if demo else basis_kaart)(scene, zichtbaar)
                beeld = kaders[zichtbaar].copy()
                if demo:
                    deel, nr = bron[n]
                    scherm = Image.open(str(werk / deel / ("%05d.png" % nr))).convert("RGB")
                    schaal = min(760.0 / scherm.width, 610.0 / scherm.height)
                    klein = scherm.resize((int(scherm.width * schaal), int(scherm.height * schaal)),
                                          Image.LANCZOS)
                    x0, y0 = 38 + (760 - klein.width) // 2, 24
                    d = ImageDraw.Draw(beeld)
                    d.rectangle([x0 - 1, y0 - 1, x0 + klein.width, y0 + klein.height], outline="#33466b")
                    beeld.paste(klein, (x0, y0))
                    vak = meta[deel]["marks"].get(str(nr))
                    if vak:
                        v = [x0 + vak[0] * schaal - 7, y0 + vak[1] * schaal - 7,
                             x0 + vak[2] * schaal + 7, y0 + vak[3] * schaal + 7]
                        d.rounded_rectangle(v, radius=9, outline=GEEL, width=4)
                if AANLOOP <= t <= AANLOOP + stem + 0.3:
                    for begin, eind, zin in titels:
                        if begin <= fractie < eind or (fractie >= 1.0 and eind >= 0.999):
                            ondertitel_tekenen(beeld, zin)
                            break
                yield beeld.tobytes()

    with tempfile.TemporaryDirectory() as tmp:
        stil = Path(tmp) / "stil.mp4"
        proc = subprocess.Popen(cmd + ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt",
                                       "yuv420p", "-r", "24", str(stil)], stdin=subprocess.PIPE)
        for ruw in beelden():
            proc.stdin.write(ruw)
        proc.stdin.close()
        if proc.wait() != 0:
            raise SystemExit("ffmpeg (video) is mislukt")
        if not heeft_audio:
            shutil.copyfile(str(stil), str(uit))
            print("Geen voice-over gevonden in docs/film/audio: film zonder geluid gemaakt.")
        else:
            lijst = Path(tmp) / "audio.txt"
            with open(str(lijst), "w") as f:
                for i, lengte in enumerate(lengtes):
                    deel = Path(tmp) / ("a%02d.wav" % i)
                    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(audio_pad(i)), "-af",
                                    "adelay=%d:all=1,apad" % int(AANLOOP * 1000), "-t", "%.3f" % lengte,
                                    "-ar", "44100", "-ac", "2", str(deel)], check=True)
                    f.write("file '%s'\n" % deel)
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(stil), "-f", "concat", "-safe",
                            "0", "-i", str(lijst), "-c:v", "copy",
                            # De stemopnamen zijn zacht: breng ze op een gangbare luidheid.
                            "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-ar", "44100",
                            "-c:a", "aac", "-b:a", "128k",
                            "-shortest", "-movflags", "+faststart", str(uit)], check=True)
    print("Film: %s (%.0f s)" % (uit, sum(lengtes)))


def schrijf_script(pad):
    regels = ["# Instructiefilm Gesprekstool: tekst van de voice-over", "",
              "Het gesprek en het verslag in de film zijn een fictief voorbeeld.", ""]
    for i, scene in enumerate(SCENES):
        regels += ["## Scene %d: %s" % (i + 1, scene["kop"]), "", scene["tekst"], ""]
    pad.write_text("\n".join(regels), "utf-8")


if __name__ == "__main__":
    werk = Path(os.environ.get("FILM_WERK", tempfile.mkdtemp(prefix="filmbeelden-")))
    schrijf_script(ROOT / "docs" / "instructiefilm-script.md")
    if not (werk / "meta.json").exists():
        Opnemer(werk).alles()
    monteer(werk, ROOT / "docs" / "instructiefilm.mp4")
