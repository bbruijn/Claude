#!/bin/bash
# Installeert de Gesprekstool op deze Mac: de app in /Applications.
#
#   sudo ./mac-installeren.sh [map-met-modellen] [--gedeelde-map PAD]
#   sudo ./mac-installeren.sh --verwijderen
#
# Modellen. De app zoekt elk model eerst in de gedeelde map (standaard ~/AI-modellen, met de
# submappen whisper/ en llm/) en daarna op de oude plek /Library/Application Support/Gesprekstool/models.
# Voor elk model in [map-met-modellen] geldt:
#   - staat het al in de gedeelde map of op de oude plek: er wordt niets gekopieerd;
#   - staat het nog nergens: het komt in de gedeelde map;
#   - heeft het een andere naam dan de standaardmodellen (zie modellen.tsv): het gaat, zoals
#     voorheen, naar de oude plek, want de app leest uit de gedeelde map alleen de standaardnamen.
# Er worden nooit modelbestanden verwijderd, ook niet bij --verwijderen buiten de oude plek.
#
# --gedeelde-map PAD  gebruik een andere gedeelde map, bijvoorbeeld /Users/Shared/AI-modellen
#                     op een laptop met meerdere gebruikers. Wordt vastgelegd in
#                     /Library/Application Support/Gesprekstool/config.json.
set -euo pipefail

[[ $EUID -eq 0 ]] || { echo "Start dit script met sudo." >&2; exit 1; }
HIER="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRON="$HIER/../Gesprekstool.app"
APP="/Applications/Gesprekstool.app"
SYSTEEM="/Library/Application Support/Gesprekstool"

BRONMAP="" GEDEELD="" VERWIJDEREN=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --verwijderen) VERWIJDEREN=ja ;;
    --gedeelde-map) GEDEELD="${2:?geef een map na --gedeelde-map}"; shift ;;
    *) BRONMAP="$1" ;;
  esac
  shift
done

if [[ -n "$VERWIJDEREN" ]]; then
  rm -rf "$APP" "$SYSTEEM"
  echo "De Gesprekstool is verwijderd (app en $SYSTEEM)."
  echo "Niet aangeraakt: de gedeelde modelmap (~/AI-modellen) en de gesprekken in ~/GesprekkenLokaal."
  exit 0
fi

[[ -d "$BRON" ]] || { echo "Gesprekstool.app niet gevonden naast de map 'beheer'." >&2; exit 1; }

# De gedeelde map hoort bij de gebruiker die sudo startte, niet bij root.
GEBRUIKER="${SUDO_USER:-root}"
THUIS="$(dscl . -read "/Users/$GEBRUIKER" NFSHomeDirectory 2>/dev/null | awk '{print $2}')"
[[ -n "$THUIS" ]] || THUIS="$(eval echo "~$GEBRUIKER")"
EXPLICIET="$GEDEELD"
GEDEELD="${GEDEELD:-$THUIS/AI-modellen}"
GEDEELD="${GEDEELD/#\~/$THUIS}"

echo "1/3 App kopieren naar $APP"
rm -rf "$APP"
ditto "$BRON" "$APP"
xattr -dr com.apple.quarantine "$APP" 2>/dev/null || true

echo "2/3 Modellen (gedeelde map: $GEDEELD)"
mkdir -p "$SYSTEEM"
if [[ -n "$EXPLICIET" ]]; then
  CONFIG="$SYSTEEM/config.json"
  if [[ ! -f "$CONFIG" ]]; then
    printf '{\n  "gedeelde_modellen_map": "%s"\n}\n' "$GEDEELD" > "$CONFIG"
    echo "   Gedeelde map vastgelegd in $CONFIG"
  elif ! grep -q "\"gedeelde_modellen_map\": *\"$GEDEELD\"" "$CONFIG"; then
    echo "   LET OP: zet in $CONFIG zelf: \"gedeelde_modellen_map\": \"$GEDEELD\""
  fi
fi

STANDAARD="$(grep -v '^#' "$HIER/modellen.tsv" | cut -f2)"
plaats() {  # plaats <bronbestand>
  local bestand="$1" naam soort doel
  naam="$(basename "$bestand")"
  case "$naam" in
    ggml-*.bin) soort=whisper ;;
    *.gguf) soort=llm ;;
    *) return 0 ;;
  esac
  if ! grep -qxF "$naam" <<< "$STANDAARD"; then
    echo "   $naam: geen standaardmodel, naar $SYSTEEM/models"
    mkdir -p "$SYSTEEM/models"
    cp "$bestand" "$SYSTEEM/models/"
    return 0
  fi
  if [[ -f "$GEDEELD/$soort/$naam" ]]; then
    echo "   $naam: staat al in de gedeelde map, niet gekopieerd"
  elif [[ -f "$SYSTEEM/models/$naam" ]]; then
    echo "   $naam: staat al op de oude plek ($SYSTEEM/models), niet gekopieerd"
  else
    doel="$GEDEELD/$soort"
    echo "   $naam: naar $doel"
    mkdir -p "$doel"
    cp "$bestand" "$doel/$naam.deel"
    mv "$doel/$naam.deel" "$doel/$naam"
    chown "$GEBRUIKER" "$GEDEELD" "$doel" "$doel/$naam" 2>/dev/null || true
    chmod a+rX "$GEDEELD" "$doel"
    chmod a+r "$doel/$naam"
  fi
}
if [[ -n "$BRONMAP" ]]; then
  [[ -d "$BRONMAP" ]] || { echo "Map met modellen niet gevonden: $BRONMAP" >&2; exit 1; }
  while IFS= read -r -d '' bestand; do
    plaats "$bestand"
  done < <(find "$BRONMAP" -maxdepth 2 -type f \( -name 'ggml-*.bin' -o -name '*.gguf' \) -print0)
else
  echo "   Geen map met modellen opgegeven: er wordt niets gekopieerd."
fi
chmod -R a+rX "$SYSTEEM"

echo "3/3 Controle (de regels Spraakmodel en Taalmodel tonen waar de app de modellen vindt)"
sudo -u "$GEBRUIKER" "$APP/Contents/MacOS/Gesprekstool" --controle || true
