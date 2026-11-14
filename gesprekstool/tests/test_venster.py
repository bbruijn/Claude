"""Bedient het echte venster met nagebootste microfoon, spraakherkenning en taalmodel.

Heeft een beeldscherm nodig (op Linux: xvfb-run). Wordt overgeslagen als dat ontbreekt.
"""
import gc
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import nep  # noqa: E402

try:
    import tkinter
    tkinter.Tk().destroy()
    from gesprekstool import kern, venster
    SCHERM = True
except Exception:
    SCHERM = False


class NepMeldingen:
    """Vervangt de dialoogvensters: onthoudt wat er gemeld is en antwoordt 'ja'."""

    def __init__(self):
        self.gemeld = []

    def __getattr__(self, soort):
        def toon(titel, tekst="", **_kw):
            self.gemeld.append((soort, tekst))
            return True
        return toon


@unittest.skipUnless(SCHERM, "geen beeldscherm of tkinter beschikbaar")
class Venster(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = nep.maak_omgeving(self.tmp.name)
        nep.schrijf_config(self.env)
        self._oud = {k: os.environ.get(k) for k in self.env}
        os.environ.update(self.env)
        kern.laad_config()
        self.meldingen = venster.messagebox = NepMeldingen()
        self.sd = nep.NepSd()
        self.app = None

    def tearDown(self):
        if self.app:
            self.app.destroy()
            self.app = None
            gc.collect()        # ruim het venster op in de hoofdthread
        for k, v in self._oud.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def start(self):
        self.app = venster.App(sd=self.sd)
        self.wacht(lambda: self.app.controle is not None)
        return self.app

    def wacht(self, voorwaarde, seconden=20):
        eind = time.time() + seconden
        while time.time() < eind:
            self.app.update()
            if voorwaarde():
                return
            time.sleep(0.02)
        self.fail("time-out; scherm=%s meldingen=%s" % (self.app.scherm, self.meldingen.gemeld))

    def neem_op(self, naam="Sam", seconden=1.6):
        app = self.app
        app.w["naam"].set(naam)
        app.w["gemeld"].set(True)
        app._werk_start_bij()
        app.w["start"].invoke()
        self.assertEqual(app.scherm, "opname", self.meldingen.gemeld)
        eind = time.time() + seconden
        self.wacht(lambda: time.time() > eind)

    def test_van_opname_tot_verslag(self):
        app = self.start()
        self.assertIn("Klaar voor gebruik", app.status["text"])
        self.assertEqual(str(app.w["start"]["state"]), "disabled", "eerst melden dat er wordt opgenomen")
        self.neem_op("Sam de Vries")
        self.assertNotEqual(app.w["tijd"]["text"], "00:00:00" if app.opname.seconden >= 1 else "x")
        app.stop_opname()
        self.assertEqual(app.scherm, "verwerk")
        self.wacht(lambda: app.scherm == "verslag")
        self.assertEqual(app.w["verslag"].get("1.0", "end-1c"), nep.VERSLAG + "\n")
        self.assertIn("Leerling: Sam de Vries", nep.prompts(self.env)[0])

        # Aanpassen, kopieren en teruggaan bewaart de wijziging.
        app.w["verslag"].insert("end", "Extra afspraak")
        app.kopieer()
        self.assertIn("Extra afspraak", app.clipboard_get())
        app.terug()
        self.assertEqual(app.scherm, "start")
        (map_, meta, status), = kern.lijst_gesprekken()
        self.assertEqual((meta["naam"], status), ("Sam de Vries", "klaar"))
        self.assertIn("Extra afspraak", (map_ / "verslag.txt").read_text("utf-8"))
        rij, = app.w["boom"].get_children()
        self.assertEqual(app.w["boom"].item(rij)["values"][2:], ["Sam de Vries", "Verslag klaar"])
        self.assertEqual(self.meldingen.gemeld, [])

    def test_stille_opname_wordt_niet_bewaard(self):
        self.sd.stil = True
        app = self.start()
        self.neem_op()
        app.stop_opname()
        self.assertEqual(app.scherm, "start")
        self.assertIn("geen geluid", self.meldingen.gemeld[-1][1])
        self.assertEqual(kern.lijst_gesprekken(), [])

    def test_annuleren_bewaart_de_opname_en_later_afmaken_werkt(self):
        os.environ["NEP_TRAAG"] = "2"
        try:
            app = self.start()
            self.neem_op()
            app.stop_opname()
            self.wacht(lambda: app.verwerking and app.verwerking._proc is not None)
            app.annuleer_verwerking()
            self.wacht(lambda: app.scherm == "start")
        finally:
            del os.environ["NEP_TRAAG"]
        (map_, _meta, status), = kern.lijst_gesprekken()
        self.assertEqual(status, "opname")
        self.assertFalse((map_ / "verslag.txt").exists())
        boom = app.w["boom"]
        boom.selection_set(boom.get_children()[0])
        app.open_gesprek()
        self.wacht(lambda: app.scherm == "verslag")
        self.assertEqual(kern.status_gesprek(map_), "klaar")

    def test_fout_bij_verwerken_bewaart_de_opname(self):
        app = self.start()
        (Path(self.env["GESPREKSTOOL_APP"]) / "bin" / "llama" / "llama-server").write_text(
            "#!/bin/sh\nexit 1\n")
        self.neem_op()
        app.stop_opname()
        self.wacht(lambda: app.scherm == "start")
        soort, tekst = self.meldingen.gemeld[-1]
        self.assertEqual(soort, "showerror")
        self.assertIn("taalmodel kon niet starten", tekst)
        self.assertIn("De opname is bewaard", tekst)
        self.assertEqual(kern.lijst_gesprekken()[0][2], "transcript")

    def test_zonder_microfoon_kan_niet_worden_gestart(self):
        self.sd.geen_microfoon = True
        app = self.start()
        self.assertIn("Niet klaar voor gebruik", app.status["text"])
        self.assertIn("Microfoon", app.status["text"])
        app.w["gemeld"].set(True)
        app._werk_start_bij()
        self.assertEqual(str(app.w["start"]["state"]), "disabled")

    def test_microfoon_later_aansluiten_en_opnieuw_controleren(self):
        self.sd.geen_microfoon = True
        app = self.start()
        self.assertIn("Niet klaar voor gebruik", app.status["text"])
        self.sd.geen_microfoon = False            # docent sluit een microfoon aan
        app.controleer_opnieuw()
        self.assertIsNone(app.controle)
        self.wacht(lambda: app.controle is not None)
        self.assertIn("Klaar voor gebruik", app.status["text"])
        teksten = [k["text"] for rij in app._controlevenster.winfo_children()
                   for k in rij.winfo_children() if k.winfo_class() == "Label"]
        self.assertIn("Microfoon gevonden", teksten)
        self.neem_op()
        self.assertEqual(app.scherm, "opname")
        app.gooi_opname_weg()

    def test_onverwachte_fout_wordt_gemeld(self):
        app = self.start()
        app.after(0, lambda: 1 / 0)
        self.wacht(lambda: self.meldingen.gemeld)
        self.assertIn("onverwachts", self.meldingen.gemeld[-1][1])
        self.assertIn("ZeroDivisionError", (kern.gebruikers_map() / "fouten.log").read_text("utf-8"))

    def test_verwijderen_en_weggooien(self):
        app = self.start()
        self.neem_op()
        app.gooi_opname_weg()
        self.assertEqual(app.scherm, "start")
        self.assertEqual(kern.lijst_gesprekken(), [])
        self.neem_op()
        app.stop_opname()
        self.wacht(lambda: app.scherm == "verslag")
        app.terug()
        boom = app.w["boom"]
        boom.selection_set(boom.get_children()[0])
        app.verwijder_gesprek()
        self.assertEqual(kern.lijst_gesprekken(), [])


if __name__ == "__main__":
    unittest.main()
