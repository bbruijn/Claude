# PyInstaller-definitie: maakt van de Python-code een zelfstandig programma.
#   macOS   -> dist/Gesprekstool.app
#   Windows -> dist/Gesprekstool/Gesprekstool.exe (venster) en gesprekstool-cli.exe (opdrachtregel)
import os
import sys

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
sys.path.insert(0, ROOT)
from gesprekstool import VERSIE  # noqa: E402

a = Analysis([os.path.join(ROOT, "start.py")], pathex=[ROOT])
pyz = PYZ(a.pure)

programmas = [EXE(pyz, a.scripts, [], exclude_binaries=True, name="Gesprekstool",
                  console=False, upx=False)]
if sys.platform == "win32":
    programmas.append(EXE(pyz, a.scripts, [], exclude_binaries=True, name="gesprekstool-cli",
                          console=True, upx=False))

map_ = COLLECT(*programmas, a.binaries, a.datas, name="Gesprekstool", upx=False)

if sys.platform == "darwin":
    BUNDLE(map_, name="Gesprekstool.app", bundle_identifier="nl.gesprekstool.app", version=VERSIE,
           info_plist={
               "CFBundleDisplayName": "Gesprekstool",
               "NSHighResolutionCapable": True,
               "LSMinimumSystemVersion": "13.3",
               "NSMicrophoneUsageDescription":
                   "De gesprekstool neemt het gesprek op met de microfoon. "
                   "De opname blijft op deze Mac.",
           })
