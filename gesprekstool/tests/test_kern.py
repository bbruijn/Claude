"""Test de keten (transcriberen -> samenvatten) met nagebootste whisper-cli en llama-server."""
import os
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import nep  # noqa: E402
from gesprekstool import kern  # noqa: E402


class Keten(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = nep.maak_omgeving(self.tmp.name)
        nep.schrijf_config(self.env)
        self.data = Path(self.env["GESPREKSTOOL_HOME"]) / "gesprekken"
        self.wav = Path(self.tmp.name) / "gesprek.wav"
        nep.maak_wav(self.wav)

    def tearDown(self):
        self.tmp.cleanup()

    def draai(self, *args, **extra):
        env = dict(os.environ, **self.env)
        env.update({k: str(v) for k, v in extra.items()})
        return subprocess.run([sys.executable, str(nep.ROOT / "start.py")] + list(args), env=env,
                              capture_output=True, text=True, timeout=120)

    def enige_map(self):
        mappen = list(self.data.iterdir())
        self.assertEqual(len(mappen), 1, mappen)
        return mappen[0]

    def test_wav_wordt_transcript_en_verslag(self):
        r = self.draai("--verwerk", str(self.wav), "--template", "oudergesprek", "--naam", "Sam de Vries")
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        map_ = self.enige_map()
        self.assertIn("oudergesprek_sam-de-vries", map_.name)
        if os.name != "nt":
            self.assertEqual(stat.S_IMODE(map_.stat().st_mode), 0o700)
        # Opmaaktekens van het model (``` ## **) zijn verwijderd.
        self.assertEqual((map_ / "verslag.txt").read_text("utf-8"), nep.VERSLAG + "\n")
        self.assertIn("Regel 2", (map_ / "transcript.txt").read_text("utf-8"))
        self.assertFalse((map_ / "transcript_bezig.txt").exists())
        prompt, = nep.prompts(self.env)
        self.assertIn("AFSPRAKEN (WAT, WIE, WANNEER)", prompt)
        self.assertIn("Leerling: Sam de Vries", prompt)
        self.assertIn("Regel 2: de mentor", prompt)
        self.assertNotIn("{naam}", prompt)

    def test_lang_gesprek_wordt_in_delen_verwerkt(self):
        nep.schrijf_config(self.env, context_tokens=4096)
        r = self.draai("--verwerk", str(self.wav), "--template", "oudergesprek", NEP_REGELS=500)
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        prompts = nep.prompts(self.env)
        self.assertGreater(len(prompts), 2)
        self.assertTrue(all("TRANSCRIPT (deel" in p for p in prompts[:-1]))
        self.assertIn("=== AANTEKENINGEN ===", prompts[-1])
        self.assertTrue(all(len(p) / 3 < 4096 for p in prompts), "prompt past niet in de context")
        alles = "".join(prompts[:-1])
        self.assertTrue(all("Regel %d:" % i in alles for i in range(500)), "regels kwijtgeraakt")

    def test_opnieuw_samenvatten_met_ander_template(self):
        self.draai("--verwerk", str(self.wav), "--template", "oudergesprek", "--naam", "Sam")
        r = self.draai("--samenvat", str(self.enige_map()), "--template", "leerlinggesprek")
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertIn("VERSLAG LEERLINGGESPREK", nep.prompts(self.env)[-1])
        self.assertIn("Leerling: Sam", nep.prompts(self.env)[-1])

    def test_valt_terug_op_processor_als_gpu_niet_werkt(self):
        r = self.draai("--verwerk", str(self.wav), "--template", "oudergesprek", NEP_GPU_KAPOT=1)
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertTrue((self.enige_map() / "verslag.txt").exists())
        logboek = (self.enige_map() / "verwerking.log").read_text("utf-8")
        self.assertIn("whisper-cli stopte met code 3 (gpu=True)", logboek)
        self.assertIn("llama-server startte niet (gpu=True)", logboek)

    def test_ontbrekend_model_geeft_duidelijke_melding(self):
        (Path(self.env["GESPREKSTOOL_SYSTEEM"]) / "models" / "nep.gguf").unlink()
        r = self.draai("--verwerk", str(self.wav), "--template", "oudergesprek")
        self.assertEqual(r.returncode, 1)
        self.assertIn("taalmodel ontbreekt", r.stderr)
        self.assertEqual(kern_status(self.enige_map()), "transcript")   # opname en transcript bewaard

    def test_controle_meldt_onderdelen(self):
        r = self.draai("--controle")
        self.assertIn("Spraakmodel: ggml-nep.bin", r.stdout)
        self.assertIn("Taalmodel: nep.gguf", r.stdout)
        self.assertIn("Templates: leerlinggesprek, oudergesprek", r.stdout)
        self.assertIn("(alleen op deze computer)", r.stdout)
        (Path(self.env["GESPREKSTOOL_APP"]) / "bin" / "llama" / "llama-server").unlink()
        r = self.draai("--controle", PATH="/nergens")
        self.assertEqual(r.returncode, 1)
        self.assertIn("llama-server): ontbreekt", r.stdout)

    def test_controle_waarschuwt_voor_cloudmap(self):
        nep.schrijf_config(self.env, data_map=str(Path(self.tmp.name) / "OneDrive - School" / "x"))
        r = self.draai("--controle")
        self.assertRegex(r.stdout, r"FOUT.*Opslagmap.*OneDrive")


def kern_status(map_):
    return kern.status_gesprek(map_)


class Opslag(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = nep.maak_omgeving(self.tmp.name)
        nep.schrijf_config(self.env, audio_bewaren_dagen=14)
        self._oud = {k: os.environ.get(k) for k in self.env}
        os.environ.update(self.env)
        kern.laad_config()

    def tearDown(self):
        for k, v in self._oud.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def gesprek(self, naam, verslag_dagen_oud=None):
        map_, _ = kern.nieuw_gesprek("oudergesprek", naam)
        nep.maak_wav(map_ / "opname.wav", 0.2)
        if verslag_dagen_oud is not None:
            (map_ / "verslag.txt").write_text("x", "utf-8")
            oud = time.time() - verslag_dagen_oud * 86400
            os.utime(str(map_ / "verslag.txt"), (oud, oud))
        return map_

    def test_oude_opnames_worden_gewist_maar_onverwerkte_nooit(self):
        oud, vers, onverwerkt = self.gesprek("a", 20), self.gesprek("b", 2), self.gesprek("c")
        self.assertEqual(kern.ruim_audio_op(), 1)
        self.assertFalse((oud / "opname.wav").exists())
        self.assertTrue((oud / "verslag.txt").exists())
        self.assertTrue((vers / "opname.wav").exists())
        self.assertTrue((onverwerkt / "opname.wav").exists())
        kern.CFG["audio_bewaren_dagen"] = 0
        self.assertEqual(kern.ruim_audio_op(), 0)

    def test_verwijderen_alleen_binnen_de_opslagmap(self):
        map_ = self.gesprek("a")
        vreemd = Path(self.tmp.name) / "anders"
        vreemd.mkdir()
        (vreemd / "meta.json").write_text("{}", "utf-8")
        with self.assertRaises(kern.Fout):
            kern.verwijder_gesprek(vreemd)
        with self.assertRaises(kern.Fout):
            kern.verwijder_gesprek(kern.data_map())
        self.assertTrue(vreemd.exists())
        kern.verwijder_gesprek(map_)
        self.assertFalse(map_.exists())

    def test_lijst_en_status(self):
        self.gesprek("a", 1)
        self.gesprek("b")
        statussen = sorted(s for _m, _meta, s in kern.lijst_gesprekken())
        self.assertEqual(statussen, ["klaar", "opname"])

    def test_eigen_template_gaat_voor(self):
        eigen = Path(self.env["GESPREKSTOOL_HOME"]) / "templates"
        eigen.mkdir()
        (eigen / "oudergesprek.txt").write_text("EIGEN", "utf-8")
        (eigen / "zorgoverleg.txt").write_text("ZORG", "utf-8")
        gevonden = kern.templates()
        self.assertEqual(list(gevonden), ["leerlinggesprek", "oudergesprek", "zorgoverleg"])
        self.assertEqual(gevonden["oudergesprek"].read_text("utf-8"), "EIGEN")

    def test_opmaak_schoonmaken_en_splitsen(self):
        self.assertEqual(kern.maak_schoon("```markdown\n# Kop\n**Vet** en\n* punt\n```"),
                         "Kop\nVet en\n- punt\n")
        stukken = kern.splits("\n".join("regel %d" % i for i in range(100)) + "\n" + "x" * 250, 100)
        self.assertTrue(all(len(s) <= 100 for s in stukken))
        self.assertEqual("".join(stukken).count("x"), 250)


if __name__ == "__main__":
    unittest.main()
