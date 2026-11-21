#!/bin/bash
# Stelt het pakket samen dat ICT uitrolt: programma + hulpprogramma's + templates + beheerscripts.
# De modellen zitten er niet in (te groot); die haalt ICT een keer op met beheer/modellen-ophalen.
#
# Gebruik:  bouw/maak-pakket.sh <naam>      bijvoorbeeld macos-arm64 of windows-x64
# Uitvoer:  pakket/Gesprekstool-<naam>/
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NAAM="${1:?geef een pakketnaam}"
UIT="$ROOT/pakket/Gesprekstool-$NAAM"
rm -rf "$UIT"
mkdir -p "$UIT"

if [[ "$(uname -s)" == "Darwin" ]]; then
  APP="$ROOT/dist/Gesprekstool.app"
  RES="$APP/Contents/Resources"
  mkdir -p "$RES/bin"
  cp -R "$ROOT/bin/." "$RES/bin/"
  cp -R "$ROOT/templates" "$RES/templates"
  # Onderteken opnieuw (ad hoc) nu de inhoud is gewijzigd; zonder geldige handtekening
  # start macOS een programma op Apple Silicon niet.
  codesign --force --sign - "$RES/bin/whisper/whisper-cli" "$RES/bin/llama/llama-server"
  codesign --force --deep --sign - "$APP"
  codesign --verify --deep "$APP" || echo "WAARSCHUWING: codesign --verify meldt een probleem"
  ditto "$APP" "$UIT/Gesprekstool.app"
else
  cp -R "$ROOT/dist/Gesprekstool/." "$UIT/"
  mkdir -p "$UIT/bin"
  cp -R "$ROOT/bin/." "$UIT/bin/"
  cp -R "$ROOT/templates" "$UIT/templates"
fi

cp -R "$ROOT/beheer" "$UIT/beheer"
cp "$ROOT/README.md" "$ROOT/BEHEER.md" "$UIT/"
echo "Pakket staat in: $UIT"
ls -la "$UIT"
