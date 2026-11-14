"""Test het opnemen met een nagebootste microfoon."""
import sys
import tempfile
import time
import unittest
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import nep  # noqa: E402
from gesprekstool import kern, opname  # noqa: E402


class Opnemen(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.pad = Path(self.tmp.name) / "opname.wav"

    def tearDown(self):
        self.tmp.cleanup()

    def lees(self):
        with wave.open(str(self.pad)) as w:
            return w.getframerate(), w.getnchannels(), w.getsampwidth(), w.getnframes()

    def test_opname_wordt_geldige_wav(self):
        o = opname.Opname(self.pad, sd=nep.NepSd())
        o.start()
        time.sleep(0.4)
        seconden = o.stop()
        hz, kanalen, breedte, frames = self.lees()
        self.assertEqual((hz, kanalen, breedte), (16000, 1, 2))
        self.assertGreater(frames, 1600)
        self.assertAlmostEqual(seconden, frames / 16000.0, places=3)
        self.assertAlmostEqual(kern.wav_duur(self.pad), seconden, places=3)
        self.assertGreater(o.piek, 0.2)

    def test_geluidsbalk_toont_zachte_spraak_en_houdt_pieken_vast(self):
        # Niveaus gemeten op een MacBook Air: spraak piekt tussen 0,02 en 0,09.
        self.assertEqual(opname.balk_fractie(0), 0.0)
        self.assertEqual(opname.balk_fractie(0.001), 0.0)             # ruis: geen uitslag
        self.assertGreater(opname.balk_fractie(0.02), 0.35)           # zachte spraak: goed zichtbaar
        self.assertGreater(opname.balk_fractie(0.09), 0.6)
        self.assertEqual(opname.balk_fractie(1.0), 1.0)
        sd = nep.NepSd()
        o = opname.Opname(self.pad, sd=sd)
        o.start()
        time.sleep(0.2)
        luid = o.niveau
        sd.stil = True                                                # de spreker valt even stil
        time.sleep(0.1)
        self.assertGreater(o.niveau, luid * 0.3, "de balk moet niet direct terugvallen")
        time.sleep(0.9)
        self.assertLess(o.niveau, luid * 0.05, "na een seconde stilte is de balk terug")
        o.stop()

    def test_bestand_is_ook_tijdens_opnemen_geldig(self):
        o = opname.Opname(self.pad, sd=nep.NepSd())
        o.start()
        time.sleep(0.2)
        o._werk_kop_bij()                 # gebeurt normaal elke paar seconden
        tussentijds = self.lees()[3]      # leesbaar zonder dat de opname is gestopt
        self.assertGreater(tussentijds, 0)
        time.sleep(0.2)
        o.stop()
        self.assertGreater(self.lees()[3], tussentijds)

    def test_pauze_neemt_niets_op(self):
        o = opname.Opname(self.pad, sd=nep.NepSd())
        o.start()
        time.sleep(0.2)
        o.pauzeer(True)
        time.sleep(0.1)
        voor = o.seconden
        time.sleep(0.3)
        self.assertAlmostEqual(o.seconden, voor, places=2)
        o.pauzeer(False)
        time.sleep(0.2)
        self.assertGreater(o.stop(), voor)

    def test_valt_terug_op_eigen_frequentie_van_de_microfoon(self):
        o = opname.Opname(self.pad, sd=nep.NepSd(weiger=[16000]))
        o.start()
        time.sleep(0.2)
        o.stop()
        self.assertEqual(self.lees()[0], 48000)

    def test_geen_microfoon_geeft_duidelijke_melding(self):
        with self.assertRaises(kern.Fout) as fout:
            opname.Opname(self.pad, sd=nep.NepSd(geen_microfoon=True)).start()
        self.assertIn("geen microfoon", str(fout.exception))
        self.assertFalse(self.pad.exists())

    def test_wegvallende_microfoon_bewaart_de_opname(self):
        sd = nep.NepSd()
        o = opname.Opname(self.pad, sd=sd)
        o.start()
        time.sleep(0.2)
        sd.valt_weg = True
        time.sleep(0.1)
        self.assertIn("weggevallen", o.fout)
        self.assertFalse(o.actief)
        o.stop()
        self.assertGreater(self.lees()[3], 0)


if __name__ == "__main__":
    unittest.main()
