"""Test de keten (transcriberen -> samenvatten) met nagebootste whisper-cli en llama-server."""
import os
import shutil
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
        self.assertRegex(r.stdout, r"Spraakmodel: \S*ggml-nep\.bin \(eigen map\)")
        self.assertRegex(r.stdout, r"Taalmodel: \S*nep\.gguf \(eigen map\)")
        self.assertIn("Templates: leerlinggesprek, oudergesprek, teamvergadering", r.stdout)
        self.assertIn("(alleen op deze computer)", r.stdout)
        (Path(self.env["GESPREKSTOOL_APP"]) / "bin" / "llama" / "llama-server").unlink()
        r = self.draai("--controle", PATH="/nergens")
        self.assertEqual(r.returncode, 1)
        self.assertIn("llama-server): ontbreekt", r.stdout)

    def test_controle_waarschuwt_voor_cloudmap(self):
        nep.schrijf_config(self.env, data_map=str(Path(self.tmp.name) / "OneDrive - School" / "x"))
        r = self.draai("--controle")
        self.assertRegex(r.stdout, r"FOUT.*Opslagmap.*OneDrive")


    def test_modellen_uit_de_gedeelde_map(self):
        gedeeld = Path(self.tmp.name) / "gedeeld"
        (gedeeld / "whisper").mkdir(parents=True)
        (gedeeld / "llm").mkdir()
        (gedeeld / "whisper" / "ggml-large-v3-turbo.bin").write_bytes(b"x")
        (gedeeld / "llm" / "gemma-3-12b-it-Q4_K_M.gguf").write_bytes(b"x")
        (gedeeld / "llm" / "gemma-3-4b-it-Q4_K_M.gguf").write_bytes(b"x")
        r = self.draai("--controle")
        self.assertIn("Spraakmodel: %s (gedeelde map)" % (gedeeld / "whisper" / "ggml-large-v3-turbo.bin"),
                      r.stdout)
        self.assertRegex(r.stdout, r"Taalmodel: \S*gedeeld\S*gemma-3-\d+b-it-Q4_K_M\.gguf \(gedeelde map\)")
        r = self.draai("--verwerk", str(self.wav), "--template", "oudergesprek")
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        verwacht = "Spraakmodel geladen uit: %s (gedeelde map)" % (gedeeld / "whisper" / "ggml-large-v3-turbo.bin")
        self.assertIn(verwacht, r.stdout)                       # getoond op de opdrachtregel
        logboek = (self.enige_map() / "verwerking.log").read_text("utf-8")
        self.assertIn(verwacht, logboek)                        # en vastgelegd in het logboek
        self.assertRegex(logboek, r"Taalmodel geladen uit: \S*gedeeld\S*gemma-3-\d+b-it-Q4_K_M\.gguf \(gedeelde map\)")
        self.assertIn("-m %s" % (gedeeld / "whisper" / "ggml-large-v3-turbo.bin"), logboek)


    def test_aanwijzingen_van_het_template_gaan_mee_naar_het_taalmodel(self):
        r = self.draai("--verwerk", str(self.wav), "--template", "teamvergadering", "--naam", "Bovenbouw")
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        prompt, = nep.prompts(self.env)
        self.assertIn("Aanwijzingen voor dit soort gesprek", prompt)
        self.assertIn("de regels hierboven gelden altijd en gaan voor", prompt)
        self.assertIn('schrijf dan "geen besluit"', prompt)
        self.assertIn("VERSLAG TEAMVERGADERING", prompt)
        self.assertIn("Team of onderwerp: Bovenbouw", prompt)
        # De kop van het templatebestand hoort niet in het verslag.
        template = prompt.split("=== TEMPLATE ===")[1].split("=== TRANSCRIPT ===")[0]
        self.assertNotIn("instructie:", template)
        self.assertNotIn("veld:", template)
        self.assertNotIn("---", template)
        # De vaste regels staan er nog steeds, voor de aanwijzingen.
        self.assertLess(prompt.index("Verzin niets"), prompt.index("Aanwijzingen voor dit soort gesprek"))

    def test_template_zonder_kop_werkt_zoals_vroeger(self):
        eigen = Path(self.env["GESPREKSTOOL_HOME"]) / "templates"
        eigen.mkdir()
        (eigen / "intake.txt").write_text("VERSLAG INTAKE\n\nDatum: {datum}\nNaam: {naam}\n\nAFSPRAKEN\n", "utf-8")
        r = self.draai("--verwerk", str(self.wav), "--template", "intake", "--naam", "Noor")
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        prompt, = nep.prompts(self.env)
        self.assertNotIn("Aanwijzingen voor dit soort gesprek", prompt)
        self.assertIn("VERSLAG INTAKE\n\nDatum: ", prompt)
        self.assertIn("Naam: Noor", prompt)

    def test_aanwijzingen_ook_bij_lange_gesprekken(self):
        nep.schrijf_config(self.env, context_tokens=4096)
        r = self.draai("--verwerk", str(self.wav), "--template", "teamvergadering", NEP_REGELS=500)
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        prompts = nep.prompts(self.env)
        self.assertGreater(len(prompts), 2)
        self.assertTrue(all("Aanwijzingen voor dit soort gesprek" in p for p in prompts))
        self.assertTrue(all(len(p) / 3 < 4096 for p in prompts), "prompt past niet in de context")

    def test_controle_waarschuwt_voor_een_kapot_template(self):
        eigen = Path(self.env["GESPREKSTOOL_HOME"]) / "templates"
        eigen.mkdir()
        (eigen / "kapot.txt").write_text("instructie:\n- iets\nVERSLAG\n", "utf-8")
        r = self.draai("--controle")
        self.assertRegex(r.stdout, r"LET OP.*Template kapot .*zonder afsluitende regel '---'")


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
        self.assertEqual(list(gevonden), ["leerlinggesprek", "oudergesprek", "teamvergadering", "zorgoverleg"])
        self.assertEqual(gevonden["oudergesprek"].read_text("utf-8"), "EIGEN")

    def test_opmaak_schoonmaken_en_splitsen(self):
        self.assertEqual(kern.maak_schoon("```markdown\n# Kop\n**Vet** en\n* punt\n```"),
                         "Kop\nVet en\n- punt\n")
        stukken = kern.splits("\n".join("regel %d" % i for i in range(100)) + "\n" + "x" * 250, 100)
        self.assertTrue(all(len(s) <= 100 for s in stukken))
        self.assertEqual("".join(stukken).count("x"), 250)


class Templates(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.map = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def lees(self, tekst):
        pad = self.map / "t.txt"
        pad.write_text(tekst, "utf-8")
        return kern.lees_template(pad)

    def test_zonder_kop(self):
        t = self.lees("VERSLAG\n\nDatum: {datum}\n")
        self.assertEqual(t, {"verslag": "VERSLAG\n\nDatum: {datum}\n", "instructie": "",
                             "veld": "Naam leerling", "waarschuwing": ""})

    def test_met_kop(self):
        t = self.lees("instructie:\n- Let op besluiten.\n- Geen namen.\n\nveld: Team\n---\nVERSLAG\nDatum: {datum}\n")
        self.assertEqual(t["instructie"], "- Let op besluiten.\n- Geen namen.")
        self.assertEqual(t["veld"], "Team")
        self.assertEqual(t["verslag"], "VERSLAG\nDatum: {datum}\n")
        self.assertEqual(t["waarschuwing"], "")

    def test_instructie_op_dezelfde_regel_en_alleen_veld(self):
        self.assertEqual(self.lees("instructie: Kort houden.\n---\nV\n")["instructie"], "Kort houden.")
        t = self.lees("veld: Klas\n---\nV\n")
        self.assertEqual((t["veld"], t["instructie"], t["verslag"]), ("Klas", "", "V\n"))

    def test_streepjes_in_een_gewoon_template_zijn_geen_kop(self):
        tekst = "VERSLAG\n---\nAFSPRAKEN\n"
        self.assertEqual(self.lees(tekst)["verslag"], tekst)

    def test_kop_zonder_afsluiting_geeft_waarschuwing(self):
        t = self.lees("instructie:\n- iets\nVERSLAG\n")
        self.assertIn("zonder afsluitende regel '---'", t["waarschuwing"])
        self.assertEqual(t["instructie"], "")

    def test_meegeleverde_templates_zijn_compleet(self):
        for pad in sorted((nep.ROOT / "templates").glob("*.txt")):
            t = kern.lees_template(pad)
            self.assertEqual(t["waarschuwing"], "", pad.name)
            self.assertTrue(t["instructie"].startswith("- "), pad.name)
            self.assertNotEqual(t["veld"], "", pad.name)
            self.assertIn("{datum}", t["verslag"], pad.name)
            self.assertIn("{naam}", t["verslag"], pad.name)


class ModelZoeken(unittest.TestCase):
    """Volgorde: gedeelde map eerst, daarna de eigen mappen van eerdere installaties."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = nep.maak_omgeving(self.tmp.name)
        nep.schrijf_config(self.env)
        self._oud = {k: os.environ.get(k) for k in list(self.env) + ["GESPREKSTOOL_MODELLEN", "HOME"]}
        os.environ.update(self.env)
        os.environ.pop("GESPREKSTOOL_MODELLEN", None)
        kern.laad_config()
        self.gedeeld = kern.gedeelde_map()
        self.eigen = Path(self.env["GESPREKSTOOL_SYSTEEM"]) / "models"
        self._ram = kern.werkgeheugen_gb

    def tearDown(self):
        kern.werkgeheugen_gb = self._ram
        for k, v in self._oud.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def leg_neer(self, soort, naam):
        pad = self.gedeeld / soort / naam
        pad.parent.mkdir(parents=True, exist_ok=True)
        pad.write_bytes(b"x")
        return pad

    def test_gedeelde_map_gaat_voor_de_eigen_map(self):
        whisper = self.leg_neer("whisper", "ggml-large-v3-turbo.bin")
        llm = self.leg_neer("llm", "gemma-3-12b-it-Q4_K_M.gguf")
        kern.werkgeheugen_gb = lambda: 32
        self.assertEqual(kern.zoek_model_met_bron("whisper"), (whisper, "gedeelde map"))
        self.assertEqual(kern.zoek_model_met_bron("llm"), (llm, "gedeelde map"))

    def test_terugvallen_op_een_bestaande_installatie(self):
        # Alleen het spraakmodel staat in de gedeelde map; het taalmodel nog op de oude plek.
        self.leg_neer("whisper", "ggml-large-v3-turbo.bin")
        self.assertEqual(kern.zoek_model_met_bron("llm"), (self.eigen / "nep.gguf", "eigen map"))
        # Zonder gedeelde map werkt alles zoals voorheen.
        shutil.rmtree(str(self.gedeeld))
        self.assertEqual(kern.zoek_model_met_bron("whisper"), (self.eigen / "ggml-nep.bin", "eigen map"))

    def test_modellen_van_andere_apps_worden_genegeerd(self):
        self.leg_neer("whisper", "ggml-base.bin")
        self.leg_neer("llm", "llama-3-8b-ander-model.gguf")
        self.assertEqual(kern.zoek_model_met_bron("whisper")[1], "eigen map")
        self.assertEqual(kern.zoek_model_met_bron("llm")[1], "eigen map")

    def test_klein_taalmodel_eerst_bij_weinig_werkgeheugen(self):
        groot = self.leg_neer("llm", "gemma-3-12b-it-Q4_K_M.gguf")
        klein = self.leg_neer("llm", "gemma-3-4b-it-Q4_K_M.gguf")
        kern.werkgeheugen_gb = lambda: 8
        self.assertEqual(kern.zoek_model("llm"), klein)
        kern.werkgeheugen_gb = lambda: 16
        self.assertEqual(kern.zoek_model("llm"), groot)

    def test_map_is_instelbaar_en_uit_te_zetten(self):
        ander = Path(self.tmp.name) / "elders"
        (ander / "whisper").mkdir(parents=True)
        (ander / "whisper" / "ggml-large-v3-turbo.bin").write_bytes(b"x")
        nep.schrijf_config(self.env, gedeelde_modellen_map=str(ander))
        kern.laad_config()
        self.assertEqual(kern.zoek_model_met_bron("whisper"),
                         (ander / "whisper" / "ggml-large-v3-turbo.bin", "gedeelde map"))
        nep.schrijf_config(self.env, gedeelde_modellen_map="")
        kern.laad_config()
        self.assertIsNone(kern.gedeelde_map())
        self.assertEqual(kern.zoek_model_met_bron("whisper")[1], "eigen map")

    @unittest.skipIf(os.name == "nt", "thuismap via HOME is Unix")
    def test_standaard_is_ai_modellen_in_de_thuismap(self):
        os.environ["HOME"] = self.tmp.name
        (Path(self.env["GESPREKSTOOL_HOME"]) / "config.json").write_text("{}", "utf-8")
        kern.laad_config()
        self.assertEqual(kern.gedeelde_map(), Path(self.tmp.name) / "AI-modellen")

    def test_vast_pad_in_de_instellingen_gaat_voor(self):
        self.leg_neer("whisper", "ggml-large-v3-turbo.bin")
        nep.schrijf_config(self.env, whisper_model=str(self.eigen / "ggml-nep.bin"))
        kern.laad_config()
        self.assertEqual(kern.zoek_model_met_bron("whisper"),
                         (self.eigen / "ggml-nep.bin", "instelling whisper_model"))

    def test_namen_gelijk_aan_beheer_modellen_tsv(self):
        tsv = (nep.ROOT / "beheer" / "modellen.tsv").read_text("utf-8")
        namen = {r.split("\t")[0]: r.split("\t")[1] for r in tsv.splitlines() if r and not r.startswith("#")}
        self.assertEqual(kern.GEDEELDE_MODELLEN["whisper"], [namen["whisper"]])
        self.assertEqual(kern.GEDEELDE_MODELLEN["llm"], [namen["llm-12b"], namen["llm-4b"]])


if __name__ == "__main__":
    unittest.main()
