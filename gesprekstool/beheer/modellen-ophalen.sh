#!/bin/bash
# Haalt de AI-modellen op. Dit is de enige stap die internet nodig heeft.
# Doe dit een keer op een beheercomputer en kopieer de map daarna naar de laptops.
#
#   ./modellen-ophalen.sh [doelmap] [12b|4b]
#
#   12b  groot taalmodel (ca. 7 GB)  - voor laptops met 16 GB werkgeheugen of meer
#   4b   klein taalmodel (ca. 2,5 GB) - voor laptops met 8 GB, of Windows zonder snelle processor
set -euo pipefail

HIER="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOEL="${1:-$PWD/modellen}"
LLM="${2:-12b}"
[[ "$LLM" == "12b" || "$LLM" == "4b" ]] || { echo "Kies 12b of 4b." >&2; exit 1; }
mkdir -p "$DOEL"

while IFS=$'\t' read -r sleutel bestand url; do
  [[ "$sleutel" == "whisper" || "$sleutel" == "llm-$LLM" ]] || continue
  if [[ -s "$DOEL/$bestand" ]]; then
    echo "Staat er al: $bestand"
    continue
  fi
  echo "Ophalen: $bestand"
  gelukt=""
  for poging in 1 2 3 4 5; do     # bij een verbroken verbinding: hervatten waar we waren
    if curl -L --fail --progress-bar -C - -o "$DOEL/$bestand.deel" "$url" < /dev/null; then
      gelukt=ja
      break
    fi
    echo "Verbinding verbroken (poging $poging van 5); de download wordt hervat..."
  done
  [[ -n "$gelukt" ]] || { echo "Downloaden mislukt: $url" >&2; exit 1; }
  mv "$DOEL/$bestand.deel" "$DOEL/$bestand"
done < <(grep -v '^#' "$HIER/modellen.tsv")

# Controleer dat het echte modelbestanden zijn (en geen foutpagina).
for gguf in "$DOEL"/*.gguf; do
  [[ "$(head -c 4 "$gguf")" == "GGUF" ]] || { echo "Ongeldig modelbestand: $gguf" >&2; exit 1; }
done
echo
echo "Klaar. Modellen staan in: $DOEL"
ls -lh "$DOEL"
