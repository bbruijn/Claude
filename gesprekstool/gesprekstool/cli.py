"""Opdrachtregel voor ICT en voor geautomatiseerde tests. Docenten gebruiken het venster."""
import argparse
import shutil
import sys
from pathlib import Path

from . import VERSIE, kern

TEKENS = {"ok": "OK    ", "let_op": "LET OP", "fout": "FOUT  "}


def _verwerk(map_, meta):
    def status(tekst):
        print("\n" + tekst, flush=True)

    def tekst(stuk):
        print(stuk, end="", flush=True)

    pad = kern.Verwerking(map_, meta, status=status, tekst=tekst).uitvoeren()
    print("\n\nKlaar: %s" % pad)


def _venstertest():
    """Opent het venster kort en sluit het weer: bewijst dat het pakket compleet is."""
    import time
    from . import venster
    app = venster.App()
    eind = time.time() + 90
    while app.controle is None and time.time() < eind:
        app.update()
        time.sleep(0.05)
    gelukt = app.controle is not None and app.scherm == "start"
    app.destroy()
    print("Venstertest %s." % ("geslaagd" if gelukt else "MISLUKT"))
    return 0 if gelukt else 1


def main(argv=None):
    parser = argparse.ArgumentParser(prog="gesprekstool", description="Gesprekstool %s" % VERSIE)
    parser.add_argument("--controle", action="store_true",
                        help="controleer of deze computer klaar is voor gebruik")
    parser.add_argument("--verwerk", metavar="WAV", help="verwerk een bestaand WAV-bestand")
    parser.add_argument("--samenvat", metavar="MAP", help="maak het verslag van een gesprek opnieuw")
    parser.add_argument("--template", help="naam van het template")
    parser.add_argument("--naam", default="", help="naam van de leerling")
    parser.add_argument("--versie", action="store_true")
    parser.add_argument("--netwerkproef", choices=["extern", "lus"], help=argparse.SUPPRESS)
    parser.add_argument("--venstertest", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if args.netwerkproef:
        return kern.netwerkproef(args.netwerkproef)
    if args.versie:
        print(VERSIE)
        return 0
    try:
        kern.laad_config()
        if args.venstertest:
            return _venstertest()
        if args.controle:
            resultaten = kern.controle()
            for niveau, tekst in resultaten:
                print("[%s] %s" % (TEKENS[niveau], tekst))
            gereed = kern.is_gereed(resultaten)
            print("\nKlaar voor gebruik." if gereed else "\nNiet klaar voor gebruik (zie FOUT).")
            return 0 if gereed else 1

        beschikbaar = list(kern.templates())
        if args.template and args.template not in beschikbaar:
            raise kern.Fout("Template '%s' bestaat niet. Beschikbaar: %s"
                            % (args.template, ", ".join(beschikbaar)))
        if args.verwerk:
            bron = Path(args.verwerk).expanduser()
            if not bron.is_file():
                raise kern.Fout("Bestand niet gevonden: %s" % bron)
            if not beschikbaar:
                raise kern.Fout("Er zijn geen templates gevonden.")
            map_, meta = kern.nieuw_gesprek(args.template or beschikbaar[0], args.naam)
            shutil.copyfile(str(bron), str(map_ / "opname.wav"))
            _verwerk(map_, meta)
            return 0
        if args.samenvat:
            map_ = Path(args.samenvat).expanduser()
            if not (map_ / "transcript.txt").is_file():
                raise kern.Fout("Geen transcript.txt gevonden in %s" % map_)
            meta = kern.lees_meta(map_)
            if args.template:
                meta["template"] = args.template
            _verwerk(map_, meta)
            return 0
    except kern.Fout as e:
        print("\nFOUT: %s" % e, file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nAfgebroken.", file=sys.stderr)
        return 130
    parser.print_help()
    return 2
