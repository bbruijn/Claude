#!/bin/bash
# Rooktest: draait het echte pakket op deze machine met kleine testmodellen.
# Bewijst dat het pakket start, dat de netwerkblokkade werkt, dat een opname een transcript
# en een verslag oplevert, en dat de installatie door ICT (beheer/*-installeren) werkt.
#
# Gebruik:  bouw/rooktest.sh <naam>     (na bouw/maak-pakket.sh <naam>)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NAAM="${1:?geef een pakketnaam}"
HF="https://huggingface.co"

if command -v cygpath >/dev/null 2>&1; then   # Windows: maak er paden als D:/a/b van
  pad() { cygpath -m "$1"; }
  WINDOWS=1
  PAKKET="$(pad "$ROOT")/pakket/Gesprekstool-$NAAM"
  CLI="$PAKKET/gesprekstool-cli.exe"
else
  pad() { echo "$1"; }
  WINDOWS=""
  PAKKET="$ROOT/pakket/Gesprekstool-$NAAM"
  CLI="$PAKKET/Gesprekstool.app/Contents/MacOS/Gesprekstool"
fi

TMP="$(pad "${RUNNER_TEMP:-/tmp}")/rooktest"
MODELLEN="$TMP/modellen"
DATA="$TMP/gesprekken"
rm -rf "$TMP/home" "$DATA"
mkdir -p "$MODELLEN" "$TMP/home"

kop() { printf '\n=== %s ===\n' "$1"; }
haal() {  # haal <doel> <url> [<terugval-url> ...]
  local doel="$1" url
  shift
  [[ -s "$doel" ]] && return 0
  for url in "$@"; do
    echo "Ophalen: $url"
    if curl -L --fail -sS -o "$doel.deel" "$url"; then
      mv "$doel.deel" "$doel"
      return 0
    fi
  done
  echo "Testbestand ophalen mislukt: $doel" >&2
  return 1
}

kop "Testmodellen en testopname ophalen"
haal "$MODELLEN/ggml-tiny.bin" "$HF/ggerganov/whisper.cpp/resolve/main/ggml-tiny.bin"
haal "$MODELLEN/test-klein.gguf" \
  "$HF/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf" \
  "$HF/ggml-org/gemma-3-1b-it-GGUF/resolve/main/gemma-3-1b-it-Q4_K_M.gguf" \
  "$HF/bartowski/SmolLM2-360M-Instruct-GGUF/resolve/main/SmolLM2-360M-Instruct-Q4_K_M.gguf"
haal "$TMP/jfk.wav" "https://raw.githubusercontent.com/ggml-org/whisper.cpp/master/samples/jfk.wav"

export GESPREKSTOOL_HOME="$TMP/home" GESPREKSTOOL_MODELLEN="$MODELLEN"
printf '{"taal": "en", "data_map": "%s"}\n' "$DATA" > "$TMP/home/config.json"

controleer() {  # controleer <programma>: alleen een ontbrekende microfoon mag een fout zijn
  "$1" --controle | tee "$TMP/controle.txt" || true
  if grep '^\[FOUT' "$TMP/controle.txt" | grep -v 'Microfoon'; then
    echo "De controle meldt fouten." >&2
    return 1
  fi
}

verwerk() {  # verwerk <programma> <wav> <naam>: verwacht de bekende zin uit de testopname
  "$1" --verwerk "$2" --template oudergesprek --naam "$3"
  local map
  map="$(ls -d "$DATA"/*"$3"* | head -1)"
  echo "--- transcript"; cat "$map/transcript.txt"
  echo "--- logboek (snelheid en gebruikte rekenkern)"
  grep -E -i 'gpu=|opgeslagen|system_info|time =|eval time|backend|metal|using device' \
    "$map/verwerking.log" | cut -c 1-240 || true
  grep -qi 'country' "$map/transcript.txt" || { echo "Transcript klopt niet." >&2; return 1; }
  [[ -s "$map/verslag.txt" ]] || { echo "Geen verslag gemaakt." >&2; return 1; }
}

kop "Versie"
"$CLI" --versie

kop "Controle van het pakket"
controleer "$CLI"
if [[ -z "$WINDOWS" ]]; then
  aantal="$(grep -E -c '^\[OK.*(Netwerkblokkade:|Interne verbinding)' "$TMP/controle.txt" || true)"
  [[ "$aantal" == "3" ]] || { echo "De netwerkblokkade (sandbox) werkt niet: $aantal/3." >&2; exit 1; }
fi

kop "Opname -> transcript -> verslag"
verwerk "$CLI" "$TMP/jfk.wav" rooktest

if [[ -z "$WINDOWS" ]]; then
  kop "Opname op 48 kHz (microfoon die geen 16 kHz levert)"
  afconvert -f WAVE -d LEI16@48000 -c 1 "$TMP/jfk.wav" "$TMP/jfk48.wav"
  verwerk "$CLI" "$TMP/jfk48.wav" rooktest48
fi

kop "Venster openen en sluiten"
"$CLI" --venstertest

kop "Installatie door ICT"
unset GESPREKSTOOL_MODELLEN       # vanaf nu moeten de modellen op de systeemplek gevonden worden
EERSTE="$(ls -d "$DATA"/*rooktest | head -1)"
if [[ -n "$WINDOWS" ]]; then
  powershell -NoProfile -ExecutionPolicy Bypass -File "$PAKKET/beheer/windows-installeren.ps1" \
    -Modellen "$MODELLEN"
  GEINSTALLEERD="$(pad "$PROGRAMFILES")/Gesprekstool/gesprekstool-cli.exe"
  controleer "$GEINSTALLEERD"
  grep -q '^\[OK.*firewallregel' "$TMP/controle.txt" || { echo "Firewallregel ontbreekt." >&2; exit 1; }
else
  sudo "$PAKKET/beheer/mac-installeren.sh" "$MODELLEN"
  GEINSTALLEERD="/Applications/Gesprekstool.app/Contents/MacOS/Gesprekstool"
  controleer "$GEINSTALLEERD"
fi

kop "Verslag maken met de geinstalleerde versie (met netwerkblokkade actief)"
rm -f "$EERSTE/verslag.txt"
"$GEINSTALLEERD" --samenvat "$EERSTE"
[[ -s "$EERSTE/verslag.txt" ]] || { echo "Geen verslag na installatie." >&2; exit 1; }

kop "Rooktest geslaagd"
