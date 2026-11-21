"""Het venster van de gesprekstool (Tkinter). Eén scherm tegelijk, grote knoppen.

Start -> Opname -> Verwerken -> Verslag
"""
import queue
import threading
import tkinter as tk
import traceback
from tkinter import font as tkfont
from tkinter import messagebox, ttk

from . import VERSIE, kern
from .opname import GEEN_SIGNAAL, ZACHT as ZACHT_GELUID, Opname, balk_fractie

BG, KAART, TEKST, ZACHT = "#f3f4f6", "#ffffff", "#1c2430", "#5b6675"
ACCENT, ROOD, GROEN, ORANJE, RAND = "#1f5fbf", "#c62828", "#1b7f3b", "#b25e00", "#d5d9e0"

STATUS_TEKST = {"klaar": "Verslag klaar", "transcript": "Verslag nog maken",
                "opname": "Nog niet verwerkt", "leeg": "Leeg"}
TEKENS = {"ok": "✓", "let_op": "!", "fout": "✗"}
KLEUREN = {"ok": GROEN, "let_op": ORANJE, "fout": ROOD}


def mooie_naam(template):
    return template.replace("_", " ").replace("-", " ").capitalize()


def _controle_taak(wachtrij, sd):
    """Draait in een achtergrondthread: oude opnames wissen en de computer controleren."""
    try:
        gewist = kern.ruim_audio_op()
        resultaten = kern.controle(sd=sd)
    except Exception as e:
        gewist, resultaten = 0, [("fout", "De controle is mislukt (%s)" % e)]
    wachtrij.put(("controle", (resultaten, gewist)))


class App(tk.Tk):
    def __init__(self, sd=None):
        super().__init__()
        self.sd = sd                      # alleen voor tests: nagebootste audio
        self.title("Gesprekstool")
        self.geometry("900x740")
        self.minsize(780, 640)
        self.configure(bg=BG)
        self._stijl()

        self.gebeurtenissen = queue.Queue()
        self.controle = None              # None = nog bezig
        self.opname = None
        self.verwerking = None
        self.map = None
        self.meta = None
        self.scherm = ""
        self.w = {}                       # widgets van het huidige scherm
        self._controle_bezig = True
        self._controlevenster = None

        kop = tk.Frame(self, bg=BG)
        kop.pack(fill="x", padx=24, pady=(18, 6))
        tk.Label(kop, text="Gesprekstool", font=self.f["kop"], bg=BG, fg=TEKST).pack(side="left")
        ttk.Button(kop, text="Controle", command=self.controleer_opnieuw).pack(side="right")
        self.status = tk.Label(self, text="Bezig met controleren...", font=self.f["klein"],
                               bg=BG, fg=ZACHT, anchor="w", justify="left", wraplength=840)
        self.status.pack(side="bottom", fill="x", padx=24, pady=(4, 12))
        self.inhoud = tk.Frame(self, bg=BG)
        self.inhoud.pack(fill="both", expand=True, padx=24, pady=6)

        self.protocol("WM_DELETE_WINDOW", self.sluiten)
        self.toon_start()
        self._timers = {}
        self._timers["pomp"] = self.after(100, self._pomp)
        self._start_controle()

    # ------------------------------------------------------------- opmaak
    def _stijl(self):
        basis = tkfont.nametofont("TkDefaultFont")
        basis.configure(size=12)
        tkfont.nametofont("TkTextFont").configure(size=12)
        familie = basis.actual("family")
        self.f = {"norm": (familie, 12), "klein": (familie, 10), "kop": (familie, 22, "bold"),
                  "sub": (familie, 15, "bold"), "tijd": (familie, 56, "bold"),
                  "knop": (familie, 14, "bold")}
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure(".", background=BG, foreground=TEKST, font=self.f["norm"])
        s.configure("TButton", padding=(14, 8), background="#e7eaef", bordercolor=RAND,
                    lightcolor="#e7eaef", darkcolor="#e7eaef")
        s.map("TButton", background=[("disabled", "#eef0f3"), ("active", "#d9dde4")],
              foreground=[("disabled", "#9aa3af")])
        for naam, kleur, donker, licht in (("Start", ROOD, "#a31f1f", "#dcaeae"),
                                           ("Accent", ACCENT, "#184c99", "#a9bfe0")):
            s.configure(naam + ".TButton", font=self.f["knop"], padding=(26, 14), background=kleur,
                        foreground="white", bordercolor=kleur, lightcolor=kleur, darkcolor=kleur)
            s.map(naam + ".TButton", background=[("disabled", licht), ("active", donker)],
                  foreground=[("disabled", "white")])
        s.configure("TRadiobutton", background=KAART, padding=(4, 4))
        s.configure("TCheckbutton", background=KAART, padding=(4, 4))
        s.map("TRadiobutton", background=[("active", KAART)])
        s.map("TCheckbutton", background=[("active", KAART)])
        s.configure("TEntry", padding=6)
        s.configure("Treeview", rowheight=30, background=KAART, fieldbackground=KAART,
                    bordercolor=RAND)
        s.configure("Treeview.Heading", font=(familie, 11, "bold"), padding=(6, 6))
        s.configure("Horizontal.TProgressbar", troughcolor="#e1e5ea", background=ACCENT,
                    bordercolor=RAND, thickness=16)

    def _kaart(self, titel=None, **pack):
        kaart = tk.Frame(self.inhoud, bg=KAART, highlightthickness=1, highlightbackground=RAND)
        kaart.pack(**(pack or {"fill": "x", "pady": 8}))
        binnen = tk.Frame(kaart, bg=KAART)
        binnen.pack(fill="both", expand=True, padx=20, pady=16)
        if titel:
            tk.Label(binnen, text=titel, font=self.f["sub"], bg=KAART, fg=TEKST).pack(anchor="w")
        return binnen

    def _label(self, ouder, tekst, kleur=TEKST, lettertype="norm", **kw):
        label = tk.Label(ouder, text=tekst, bg=ouder["bg"], fg=kleur, font=self.f[lettertype],
                         justify="left", anchor="w", **kw)
        return label

    def _wissel(self, naam):
        for kind in self.inhoud.winfo_children():
            kind.destroy()
        self.scherm = naam
        self.w = {}

    # -------------------------------------------------------- startscherm
    def toon_start(self):
        self._wissel("start")
        namen = list(kern.templates())
        kaart = self._kaart("Nieuw gesprek")

        self._label(kaart, "Soort gesprek", ZACHT).pack(anchor="w", pady=(12, 2))
        self.w["soort"] = tk.StringVar(value=namen[0] if namen else "")
        rij = tk.Frame(kaart, bg=KAART)
        rij.pack(anchor="w")
        for naam in namen:
            ttk.Radiobutton(rij, text=mooie_naam(naam), value=naam,
                            variable=self.w["soort"]).pack(side="left", padx=(0, 18))

        self._label(kaart, "Naam leerling (mag leeg blijven)", ZACHT).pack(anchor="w", pady=(12, 2))
        self.w["naam"] = tk.StringVar()
        ttk.Entry(kaart, textvariable=self.w["naam"], width=40, font=self.f["norm"]).pack(anchor="w")

        self.w["gemeld"] = tk.BooleanVar(value=not kern.CFG["toestemming_vragen"])
        if kern.CFG["toestemming_vragen"]:
            ttk.Checkbutton(kaart, text="Ik heb gemeld dat dit gesprek wordt opgenomen",
                            variable=self.w["gemeld"], command=self._werk_start_bij).pack(
                                anchor="w", pady=(14, 0))
        self.w["start"] = ttk.Button(kaart, text="●  Start opname", style="Start.TButton",
                                     command=self.start_opname)
        self.w["start"].pack(anchor="w", pady=(14, 0))

        lijst = self._kaart("Eerdere gesprekken", fill="both", expand=True, pady=8)
        knoppen = tk.Frame(lijst, bg=KAART)
        knoppen.pack(side="bottom", fill="x", pady=(10, 0))
        ttk.Button(knoppen, text="Openen", command=self.open_gesprek).pack(side="left")
        ttk.Button(knoppen, text="Map openen", command=self.open_map).pack(side="left", padx=8)
        ttk.Button(knoppen, text="Verwijderen", command=self.verwijder_gesprek).pack(side="right")
        kader = tk.Frame(lijst, bg=KAART)
        kader.pack(fill="both", expand=True, pady=(10, 0))
        boom = ttk.Treeview(kader, columns=("datum", "soort", "naam", "status"), show="headings",
                            height=5, selectmode="browse")
        for kolom, titel, breedte in (("datum", "Datum", 150), ("soort", "Soort gesprek", 180),
                                      ("naam", "Leerling", 220), ("status", "Status", 170)):
            boom.heading(kolom, text=titel, anchor="w")
            boom.column(kolom, width=breedte, anchor="w")
        schuif = ttk.Scrollbar(kader, orient="vertical", command=boom.yview)
        boom.configure(yscrollcommand=schuif.set)
        schuif.pack(side="right", fill="y")
        boom.pack(side="left", fill="both", expand=True)
        boom.bind("<Double-1>", lambda _e: self.open_gesprek())
        self.w["boom"] = boom
        self.w["mappen"] = {}
        try:
            gesprekken = kern.lijst_gesprekken()
        except OSError:
            gesprekken = []
        for map_, meta, status in gesprekken:
            iid = boom.insert("", "end", values=(meta["datum"], mooie_naam(meta["template"]),
                                                 meta["naam"] or "-", STATUS_TEKST[status]))
            self.w["mappen"][iid] = map_
        self._werk_start_bij()

    def _werk_start_bij(self):
        if self.scherm != "start":
            return
        gereed = self.controle is not None and kern.is_gereed(self.controle)
        aan = gereed and self.w["gemeld"].get() and self.w["soort"].get()
        self.w["start"].configure(state="normal" if aan else "disabled")

    def _gekozen_map(self):
        keuze = self.w["boom"].selection()
        if not keuze:
            messagebox.showinfo("Gesprekstool", "Kies eerst een gesprek in de lijst.", parent=self)
            return None
        return self.w["mappen"][keuze[0]]

    def open_gesprek(self):
        map_ = self._gekozen_map()
        if not map_:
            return
        status = kern.status_gesprek(map_)
        if status == "klaar":
            self.toon_verslag(map_)
        elif status == "leeg":
            messagebox.showinfo("Gesprekstool", "Dit gesprek bevat geen opname.", parent=self)
        elif self.controle is None or not kern.is_gereed(self.controle):
            messagebox.showwarning("Gesprekstool", "De gesprekstool is nog niet klaar voor gebruik. "
                                   "Klik op 'Controle' voor details.", parent=self)
        else:
            self.start_verwerking(map_, kern.lees_meta(map_))

    def open_map(self):
        try:
            kern.beveilig_map(kern.data_map())
            kern.open_map(kern.data_map())
        except OSError as e:
            messagebox.showerror("Gesprekstool", "De map kan niet worden geopend (%s)." % e, parent=self)

    def verwijder_gesprek(self):
        map_ = self._gekozen_map()
        if not map_:
            return
        meta = kern.lees_meta(map_)
        if messagebox.askyesno("Gesprek verwijderen", "Het gesprek van %s (%s) wordt definitief "
                               "verwijderd: opname, transcript en verslag.\n\nDoorgaan?"
                               % (meta["datum"], meta["naam"] or "geen naam"), parent=self):
            try:
                kern.verwijder_gesprek(map_)
            except (kern.Fout, OSError) as e:
                messagebox.showerror("Gesprekstool", str(e), parent=self)
            self.toon_start()

    # ------------------------------------------------------- opnamescherm
    def start_opname(self):
        self.map = None
        try:
            self.map, self.meta = kern.nieuw_gesprek(self.w["soort"].get(), self.w["naam"].get())
            self.opname = Opname(self.map / "opname.wav", kern.CFG["microfoon"], sd=self.sd)
            self.opname.start()
        except (kern.Fout, OSError) as e:
            self.opname = None
            self._gooi_weg(self.map)
            messagebox.showerror("Opname starten", str(e), parent=self)
            return
        kern.houd_wakker(True)
        self.toon_opname()

    def toon_opname(self):
        self._wissel("opname")
        kaart = self._kaart(fill="both", expand=True, pady=8)
        self.w["kop"] = self._label(kaart, "●  Opname loopt", ROOD, "sub")
        self.w["kop"].pack(pady=(30, 0))
        self.w["tijd"] = tk.Label(kaart, text="00:00:00", font=self.f["tijd"], bg=KAART, fg=TEKST)
        self.w["tijd"].pack(pady=(10, 10))
        self._label(kaart, "%s  -  %s" % (mooie_naam(self.meta["template"]),
                                         self.meta["naam"] or "geen naam"), ZACHT).pack()
        self.w["meter"] = tk.Canvas(kaart, width=420, height=18, bg="#e1e5ea",
                                    highlightthickness=0)
        self.w["meter"].pack(pady=(26, 4))
        self.w["balk"] = self.w["meter"].create_rectangle(0, 0, 0, 18, fill=GROEN, width=0)
        self._label(kaart, "Geluidsniveau van de microfoon", ZACHT, "klein").pack()
        self.w["hint"] = tk.Label(kaart, text="", bg=KAART, fg=ORANJE, font=self.f["norm"],
                                  wraplength=600, justify="center")
        self.w["hint"].pack(pady=(14, 0))
        knoppen = tk.Frame(kaart, bg=KAART)
        knoppen.pack(pady=(24, 8))
        self.w["pauze"] = ttk.Button(knoppen, text="Pauze", command=self.pauzeer)
        self.w["pauze"].pack(side="left", padx=8, ipady=6)
        ttk.Button(knoppen, text="■  Stop en maak verslag", style="Accent.TButton",
                   command=self.stop_opname).pack(side="left", padx=8)
        ttk.Button(kaart, text="Opname weggooien", command=self.gooi_opname_weg).pack(pady=(10, 20))
        self._tik()

    def _tik(self):
        if self.scherm != "opname" or not self.opname:
            return
        o = self.opname
        self.w["tijd"].configure(text=kern.duur_tekst(o.seconden))
        breedte = 0 if o.gepauzeerd else int(420 * balk_fractie(o.niveau))
        self.w["meter"].coords(self.w["balk"], 0, 0, breedte, 18)
        if o.fout:
            messagebox.showwarning("Opname", o.fout, parent=self)
            self.stop_opname()
            return
        if o.gepauzeerd:
            pass
        elif o.seconden > 4 and o.piek < GEEN_SIGNAAL:
            self.w["hint"].configure(text="Er komt geen geluid binnen. Controleer of de microfoon "
                                     "aan staat en of de gesprekstool toegang heeft tot de microfoon.")
        elif o.seconden > 8 and o.piek < ZACHT_GELUID:
            self.w["hint"].configure(text="De microfoon vangt weinig geluid op. Zet de laptop dichter "
                                     "bij de sprekers of zet het invoervolume van de microfoon "
                                     "hoger. De opname loopt gewoon door.")
        else:
            self.w["hint"].configure(text="")
        self._timers["tik"] = self.after(100, self._tik)

    def pauzeer(self):
        aan = not self.opname.gepauzeerd
        self.opname.pauzeer(aan)
        self.w["pauze"].configure(text="Hervat opname" if aan else "Pauze")
        self.w["kop"].configure(text="Gepauzeerd" if aan else "●  Opname loopt",
                                fg=ORANJE if aan else ROOD)
        self.w["hint"].configure(text="De opname is gepauzeerd: er wordt nu niets opgenomen."
                                 if aan else "")

    def _eindig_opname(self):
        opname, self.opname = self.opname, None
        seconden = opname.stop()
        return seconden, opname.piek

    def stop_opname(self):
        if not self.opname:
            return
        seconden, piek = self._eindig_opname()
        # Alleen afkeuren als er werkelijk niets is binnengekomen: een zachte opname van een
        # echt gesprek mag nooit worden weggegooid.
        if seconden < 1 or piek < GEEN_SIGNAAL:
            kern.houd_wakker(False)
            self._gooi_weg(self.map)
            messagebox.showwarning("Opname", "Er is geen geluid opgenomen, dus er is niets bewaard."
                                   "\n\nControleer de microfoon en probeer het opnieuw.", parent=self)
            self.toon_start()
            return
        kern.log(self.map, "Opname gestopt na %s." % kern.duur_tekst(seconden))
        self.start_verwerking(self.map, self.meta)

    def gooi_opname_weg(self):
        if messagebox.askyesno("Opname weggooien", "De opname wordt gestopt en definitief "
                               "verwijderd.\n\nDoorgaan?", parent=self):
            self._eindig_opname()
            kern.houd_wakker(False)
            self._gooi_weg(self.map)
            self.toon_start()

    def _gooi_weg(self, map_):
        try:
            if map_:
                kern.verwijder_gesprek(map_)
        except (kern.Fout, OSError):
            pass

    # ------------------------------------------------------ verwerkscherm
    def start_verwerking(self, map_, meta):
        self.map, self.meta = map_, meta
        self._wissel("verwerk")
        kaart = self._kaart("Het verslag wordt gemaakt", fill="both", expand=True, pady=8)
        self.w["status"] = self._label(kaart, "Voorbereiden...")
        self.w["status"].pack(anchor="w", pady=(14, 6))
        self.w["balk"] = ttk.Progressbar(kaart, mode="indeterminate", maximum=1000)
        self.w["balk"].pack(fill="x")
        self.w["balk"].start(20)
        self._label(kaart, "Dit duurt enkele minuten. Laat de laptop aan staan en sluit de klep "
                    "niet. De opname is al veilig opgeslagen.", ZACHT, "klein",
                    wraplength=780).pack(anchor="w", pady=(8, 10))
        ttk.Button(kaart, text="Annuleren", command=self.annuleer_verwerking).pack(
            side="bottom", anchor="e", pady=(10, 0))
        self.w["tekst"] = self._tekstvak(kaart)
        self.w["tekst"].configure(state="disabled")

        q = self.gebeurtenissen
        verwerking = kern.Verwerking(
            map_, meta, status=lambda t: q.put(("status", t)),
            voortgang=lambda f: q.put(("voortgang", f)), tekst=lambda s: q.put(("tekst", s)))
        self.verwerking = verwerking
        kern.houd_wakker(True)

        def werk():
            try:
                q.put(("klaar", verwerking.uitvoeren()))
            except kern.Geannuleerd:
                q.put(("geannuleerd", None))
            except kern.Fout as e:
                q.put(("fout", str(e)))
            except Exception as e:      # onverwacht: vastleggen en netjes melden
                kern.log(map_, traceback.format_exc())
                q.put(("fout", "Er ging iets onverwachts mis (%s).\nDetails staan in "
                       "verwerking.log in de map van het gesprek." % e))

        threading.Thread(target=werk, daemon=True).start()

    def annuleer_verwerking(self):
        if self.verwerking and messagebox.askyesno(
                "Annuleren", "Het maken van het verslag wordt afgebroken.\n\nDe opname blijft "
                "bewaard: je kunt het verslag later alsnog maken via 'Eerdere gesprekken'.",
                parent=self):
            if self.verwerking:
                self.w["status"].configure(text="Bezig met afbreken...")
                self.verwerking.annuleer()

    def _tekstvak(self, ouder):
        kader = tk.Frame(ouder, bg=KAART, highlightthickness=1, highlightbackground=RAND)
        kader.pack(fill="both", expand=True)
        tekst = tk.Text(kader, wrap="word", font=self.f["norm"], bg="white", fg=TEKST, relief="flat",
                        padx=12, pady=10, undo=True, height=8)
        schuif = ttk.Scrollbar(kader, orient="vertical", command=tekst.yview)
        tekst.configure(yscrollcommand=schuif.set)
        schuif.pack(side="right", fill="y")
        tekst.pack(side="left", fill="both", expand=True)
        return tekst

    # ------------------------------------------------------ verslagscherm
    def toon_verslag(self, map_):
        self.map, self.meta = map_, kern.lees_meta(map_)
        self._wissel("verslag")
        kaart = self._kaart("Verslag: %s, %s (%s)" % (
            mooie_naam(self.meta["template"]), self.meta["naam"] or "geen naam",
            self.meta["datum"]), fill="both", expand=True, pady=8)
        self._label(kaart, "Lees het verslag na en pas het zo nodig aan: een automatisch verslag "
                    "kan fouten bevatten.", ORANJE, wraplength=780).pack(anchor="w", pady=(8, 10))
        knoppen = tk.Frame(kaart, bg=KAART)
        knoppen.pack(side="bottom", fill="x", pady=(12, 0))
        ttk.Button(knoppen, text="Kopieer verslag", style="Accent.TButton",
                   command=self.kopieer).pack(side="left")
        ttk.Button(knoppen, text="Transcript", command=self.toon_transcript).pack(
            side="left", padx=(12, 0), ipady=5)
        ttk.Button(knoppen, text="Map openen", command=lambda: kern.open_map(self.map)).pack(
            side="left", padx=8, ipady=5)
        ttk.Button(knoppen, text="Terug naar start", command=self.terug).pack(side="right", ipady=5)
        self.w["melding"] = self._label(kaart, "", GROEN, "klein")
        self.w["melding"].pack(side="bottom", anchor="w", pady=(6, 0))
        tekst = self._tekstvak(kaart)
        try:
            tekst.insert("1.0", (map_ / "verslag.txt").read_text("utf-8", errors="replace"))
        except OSError as e:
            tekst.insert("1.0", "Het verslag kan niet worden gelezen (%s)." % e)
        tekst.edit_modified(False)
        tekst.edit_reset()
        self.w["verslag"] = tekst

    def _bewaar_verslag(self):
        tekst = self.w.get("verslag")
        if self.scherm != "verslag" or not tekst or not tekst.edit_modified():
            return
        try:
            (self.map / "verslag.txt").write_text(tekst.get("1.0", "end-1c").rstrip() + "\n", "utf-8")
            tekst.edit_modified(False)
        except OSError as e:
            messagebox.showerror("Opslaan", "Het verslag kan niet worden opgeslagen (%s)." % e,
                                 parent=self)

    def kopieer(self):
        self._bewaar_verslag()
        self.clipboard_clear()
        self.clipboard_append(self.w["verslag"].get("1.0", "end-1c"))
        self.update()
        self.w["melding"].configure(text="✓ Verslag gekopieerd. Plak het in het leerlingvolgsysteem.")

    def toon_transcript(self):
        venster = tk.Toplevel(self)
        venster.title("Transcript")
        venster.geometry("760x600")
        venster.configure(bg=KAART)
        tekst = tk.Text(venster, wrap="word", font=self.f["norm"], bg="white", fg=TEKST,
                        relief="flat", padx=14, pady=12)
        schuif = ttk.Scrollbar(venster, orient="vertical", command=tekst.yview)
        tekst.configure(yscrollcommand=schuif.set)
        schuif.pack(side="right", fill="y")
        tekst.pack(fill="both", expand=True)
        try:
            tekst.insert("1.0", (self.map / "transcript.txt").read_text("utf-8", errors="replace"))
        except OSError:
            tekst.insert("1.0", "Er is geen transcript.")
        tekst.configure(state="disabled")

    def terug(self):
        self._bewaar_verslag()
        self.toon_start()

    # ----------------------------------------------------------- controle
    def _start_controle(self):
        # De thread krijgt alleen de wachtrij mee, geen verwijzing naar het venster: Tk mag
        # uitsluitend vanuit de hoofdthread worden gebruikt en opgeruimd.
        threading.Thread(target=_controle_taak, args=(self.gebeurtenissen, self.sd),
                         daemon=True).start()

    def _toon_status(self, gewist=0):
        fouten = [t for n, t in self.controle if n == "fout"]
        if fouten:
            self.status.configure(fg=ROOD, text="✗ Niet klaar voor gebruik: %s. "
                                  "Neem contact op met ICT." % fouten[0])
            return
        tekst = "✓ Klaar voor gebruik. Opname, transcript en verslag blijven op deze laptop."
        dagen = kern.CFG["audio_bewaren_dagen"]
        if dagen:
            tekst += " Opnames worden %s dagen na het verslag automatisch gewist." % dagen
        if gewist:
            tekst += " (%d oude opname(s) gewist.)" % gewist
        self.status.configure(fg=GROEN, text=tekst)

    def controleer_opnieuw(self):
        """Controle-knop: toont het venster en controleert opnieuw (niet tijdens een opname)."""
        if not self.opname and not self.verwerking and not self._controle_bezig:
            self._controle_bezig = True
            self.controle = None
            self.status.configure(fg=ZACHT, text="Bezig met controleren...")
            self._werk_start_bij()
            self._start_controle()
        self.toon_controle()

    def toon_controle(self):
        venster = self._controlevenster
        if venster is None or not venster.winfo_exists():
            venster = self._controlevenster = tk.Toplevel(self)
            venster.title("Controle")
            venster.configure(bg=KAART)
            venster.geometry("760x540")
        for kind in venster.winfo_children():
            kind.destroy()
        tk.Label(venster, text="Controle van deze computer", font=self.f["sub"], bg=KAART,
                 fg=TEKST).pack(anchor="w", padx=20, pady=(16, 8))
        if self.controle is None:
            tk.Label(venster, text="Bezig met controleren...", bg=KAART,
                     fg=ZACHT, font=self.f["norm"]).pack(anchor="w", padx=20)
        for niveau, tekst in self.controle or []:
            rij = tk.Frame(venster, bg=KAART)
            rij.pack(fill="x", padx=20, pady=3)
            tk.Label(rij, text=TEKENS[niveau], fg=KLEUREN[niveau], bg=KAART, width=2,
                     font=self.f["knop"]).pack(side="left", anchor="n")
            tk.Label(rij, text=tekst, bg=KAART, fg=TEKST, font=self.f["norm"], justify="left",
                     anchor="w", wraplength=680).pack(side="left", fill="x")
        tk.Label(venster, text="Gesprekstool %s" % VERSIE, bg=KAART, fg=ZACHT,
                 font=self.f["klein"]).pack(side="bottom", anchor="e", padx=20, pady=12)

    # ------------------------------------------------------- gebeurtenissen
    def _pomp(self):
        try:
            while True:
                soort, waarde = self.gebeurtenissen.get_nowait()
                self._verwerk_gebeurtenis(soort, waarde)
        except queue.Empty:
            pass
        self._timers["pomp"] = self.after(100, self._pomp)

    def _verwerk_gebeurtenis(self, soort, waarde):
        if soort == "controle":
            self.controle, gewist = waarde
            self._controle_bezig = False
            self._toon_status(gewist)
            self._werk_start_bij()
            if self._controlevenster is not None and self._controlevenster.winfo_exists():
                self.toon_controle()
            return
        if self.scherm != "verwerk":
            return
        if soort == "status":
            self.w["status"].configure(text=waarde)
        elif soort == "voortgang":
            balk = self.w["balk"]
            if waarde is None:
                if str(balk["mode"]) != "indeterminate":
                    balk.configure(mode="indeterminate")
                    balk.start(20)
            else:
                balk.stop()
                balk.configure(mode="determinate", value=int(waarde * 1000))
        elif soort == "tekst":
            tekst = self.w["tekst"]
            tekst.configure(state="normal")
            tekst.insert("end", waarde)
            tekst.see("end")
            tekst.configure(state="disabled")
        else:
            self.verwerking = None
            kern.houd_wakker(False)
            if soort == "klaar":
                self.toon_verslag(self.map)
            else:
                if soort == "fout":
                    messagebox.showerror("Verslag maken", waarde + "\n\nDe opname is bewaard. "
                                         "Je kunt het later opnieuw proberen via 'Eerdere "
                                         "gesprekken'.", parent=self)
                self.toon_start()

    def report_callback_exception(self, soort, fout, spoor):
        """Onverwachte fout in het venster: vastleggen en melden in plaats van stil vastlopen."""
        details = "".join(traceback.format_exception(soort, fout, spoor))
        try:
            kern.gebruikers_map().mkdir(parents=True, exist_ok=True)
            with open(str(kern.gebruikers_map() / "fouten.log"), "a", encoding="utf-8") as f:
                f.write(details + "\n")
        except OSError:
            pass
        messagebox.showerror("Gesprekstool", "Er ging iets onverwachts mis (%s).\n\nEen lopende "
                             "opname gaat gewoon door. Meld dit bij ICT als het vaker gebeurt."
                             % fout, parent=self)

    def destroy(self):
        for timer in self._timers.values():
            try:
                self.after_cancel(timer)
            except tk.TclError:
                pass
        super().destroy()

    def sluiten(self):
        if self.opname:
            if not messagebox.askyesno("Gesprekstool sluiten", "De opname loopt nog.\n\nStoppen en "
                                       "de opname bewaren? Je kunt het verslag later maken.",
                                       parent=self):
                return
            self._eindig_opname()
        if self.verwerking:
            if not messagebox.askyesno("Gesprekstool sluiten", "Het verslag wordt nog gemaakt.\n\n"
                                       "Afbreken en sluiten? De opname blijft bewaard.", parent=self):
                return
            self.verwerking.annuleer()
        self._bewaar_verslag()
        kern.houd_wakker(False)
        self.destroy()


def main():
    if kern.WINDOWS:
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    try:
        kern.laad_config()
    except kern.Fout as e:
        wortel = tk.Tk()
        wortel.withdraw()
        messagebox.showerror("Gesprekstool", str(e))
        return
    App().mainloop()
