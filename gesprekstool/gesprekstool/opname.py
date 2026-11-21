"""Opnemen via de microfoon naar een WAV-bestand (mono, 16 bit).

Het bestand wordt tijdens het opnemen steeds geldig gehouden: valt de laptop uit,
dan is de opname tot dat moment nog bruikbaar.
"""
import array
import math
import queue
import struct
import sys
import threading
import time

from .kern import Fout

DOEL_HZ = 16000        # wat de spraakherkenning verwacht
BIJWERKEN_S = 5        # zo vaak wordt de WAV-kop bijgewerkt
# Drempels voor de piek van de opname (0..1). Gemeten op een MacBook Air: gewone spraak
# vlak bij de laptop piekt rond 0,02 tot 0,09. Een microfoon zonder toegang levert exact 0.
GEEN_SIGNAAL = 0.0005  # daaronder komt er werkelijk niets binnen
ZACHT = 0.01           # daaronder is het geluid zacht: waarschuwen, maar gewoon opnemen


def _sounddevice():
    try:
        import sounddevice
        return sounddevice
    except Exception as e:      # ontbrekende module of ontbrekende PortAudio
        raise Fout("De audio-ondersteuning kon niet worden geladen (%s)." % e)


def ververs_apparaten(sd):
    """Laat de audiobibliotheek opnieuw kijken welke microfoons er zijn (bijv. na insteken)."""
    try:
        sd._terminate()
        sd._initialize()
    except Exception:
        pass


def controleer_microfoon(apparaat=None, sd=None):
    """Geeft de naam van de microfoon, of gooit Fout als er geen bruikbare is."""
    sd = sd or _sounddevice()
    ververs_apparaten(sd)
    try:
        info = sd.query_devices(apparaat, "input")
    except Exception as e:
        raise Fout("geen microfoon gevonden (%s)" % e)
    if not info or info.get("max_input_channels", 0) < 1:
        raise Fout("geen microfoon gevonden")
    return info.get("name", "microfoon")


def balk_fractie(niveau):
    """Uitslag van de geluidsbalk (0..1) op een decibelschaal van -54 tot -6 dB, zodat ook
    zachte spraak duidelijk zichtbaar is."""
    if niveau <= 0:
        return 0.0
    return min(1.0, max(0.0, (20 * math.log10(niveau) + 54.0) / 48.0))


def wav_kop(hz, databytes):
    return struct.pack("<4sI4s4sIHHIIHH4sI", b"RIFF", 36 + databytes, b"WAVE", b"fmt ", 16,
                       1, 1, hz, hz * 2, 2, 16, b"data", databytes)


class Opname:
    def __init__(self, pad, apparaat=None, sd=None):
        self.pad = pad
        self.apparaat = apparaat
        self.sd = sd or _sounddevice()
        self.hz = DOEL_HZ
        self.niveau = 0.0            # 0..1, recente piek (zakt geleidelijk terug)
        self.piek = 0.0              # hoogste niveau sinds de start
        self.fout = None             # melding als het apparaat wegvalt
        self.gepauzeerd = False
        self._bytes = 0
        self._wachtrij = queue.Queue()
        self._stream = None
        self._bestand = None
        self._schrijver = None

    # -- bediening
    def start(self):
        naam = controleer_microfoon(self.apparaat, self.sd)
        laatste = None
        for hz in self._frequenties():
            try:
                self._stream = self.sd.RawInputStream(
                    samplerate=hz, channels=1, dtype="int16", device=self.apparaat,
                    callback=self._blok, finished_callback=self._afgelopen)
                self.hz = hz
                break
            except Exception as e:
                laatste = e
        if not self._stream:
            raise Fout("De microfoon '%s' kan niet worden geopend (%s).\n\nControleer of de "
                       "gesprekstool toegang heeft tot de microfoon in de privacy-instellingen."
                       % (naam, laatste))
        try:
            self._bestand = open(str(self.pad), "wb")
            self._bestand.write(wav_kop(self.hz, 0))
            self._schrijver = threading.Thread(target=self._schrijf, daemon=True)
            self._schrijver.start()
            self._stream.start()
        except Exception as e:
            self._sluit_stream()
            raise Fout("De opname kon niet starten (%s)." % e)

    def pauzeer(self, aan):
        self.gepauzeerd = bool(aan)
        if aan:
            self.niveau = 0.0

    def stop(self):
        """Stopt de opname en geeft de opgenomen duur in seconden."""
        self._sluit_stream()
        self._wachtrij.put(None)
        if self._schrijver:
            self._schrijver.join(timeout=15)
        if self._bestand:
            self._werk_kop_bij()
            self._bestand.close()
            self._bestand = None
        return self.seconden

    @property
    def seconden(self):
        return self._bytes / float(self.hz * 2)

    @property
    def actief(self):
        return bool(self._stream) and self.fout is None

    # -- intern
    def _frequenties(self):
        kandidaten = [DOEL_HZ]
        try:
            eigen = int(self.sd.query_devices(self.apparaat, "input")["default_samplerate"])
            if eigen not in kandidaten:
                kandidaten.append(eigen)
        except Exception:
            pass
        return kandidaten

    def _blok(self, data, _frames, _tijd, status):     # draait in de audiothread
        if not self.gepauzeerd:
            self._wachtrij.put(bytes(data))

    def _afgelopen(self):                               # stream is gestopt of weggevallen
        if self._stream is not None and self.fout is None:
            self.fout = "De microfoon is weggevallen. De opname tot nu toe is bewaard."

    def _sluit_stream(self):
        stream, self._stream = self._stream, None
        if stream:
            for actie in (stream.stop, stream.close):
                try:
                    actie()
                except Exception:
                    pass

    def _schrijf(self):
        laatst = time.time()
        while True:
            blok = self._wachtrij.get()
            if blok is None:
                return
            try:
                self._bestand.write(blok)
            except (OSError, ValueError) as e:
                self.fout = "De opname kan niet worden opgeslagen (%s)." % e
                return
            self._bytes += len(blok)
            monsters = array.array("h")
            monsters.frombytes(blok[:len(blok) // 2 * 2])
            if sys.byteorder == "big":
                monsters.byteswap()
            if monsters:
                blokpiek = max(max(monsters), -min(monsters)) / 32768.0
                # Houd pieken even vast en laat ze zakken met 20 dB per 0,4 s: zo beweegt de
                # balk mee met de spraak in plaats van met een toevallig stil moment.
                afname = 0.1 ** (len(monsters) / float(self.hz) / 0.4)
                self.niveau = max(blokpiek, self.niveau * afname)
                self.piek = max(self.piek, blokpiek)
            if time.time() - laatst > BIJWERKEN_S:
                self._werk_kop_bij()
                laatst = time.time()

    def _werk_kop_bij(self):
        try:
            self._bestand.flush()
            self._bestand.seek(0)
            self._bestand.write(wav_kop(self.hz, self._bytes))
            self._bestand.seek(0, 2)
            self._bestand.flush()
        except (OSError, ValueError):
            pass
