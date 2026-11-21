#!/bin/bash
# Haalt de AI-modellen op. Dit is de enige stap die internet nodig heeft.
#
#   ./modellen-ophalen.sh [12b|4b]             naar de gedeelde map ~/AI-modellen (whisper/ en llm/)
#   ./modellen-ophalen.sh <doelmap> [12b|4b]   alles in een losse map, bijvoorbeeld een USB-stick
#                                              om daarna op meerdere laptops te installeren
#
#   12b  groot taalmodel (ca. 7 GB)  - voor laptops met 16 GB werkgeheugen of meer
#   4b   klein taalmodel (ca. 2,5 GB) - voor laptops met 8 GB, of Windows zonder snelle processor
#
# Een model dat er al staat, wordt niet opnieuw opgehaald. Een andere gedeelde map kies je
# met de omgevingsvariabele GEDEELDE_MAP.
set -euo pipefail

HIER="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -z "${1:-}" || "${1:-}" == "12b" || "${1:-}" == "4b" ]]; then
  LLM="${1:-12b}"
  GEDEELD="${GEDEELDE_MAP:-$HOME/AI-modellen}"
  LOS=""
else
  LOS="$1"
  LLM="${2:-12b}"
fi
[[ "$LLM" == "12b" || "$LLM" == "4b" ]] || { echo "Kies 12b of 4b." >&2; exit 1; }

doelmap() {  # doelmap <sleutel>: losse map, of de juiste submap van de gedeelde map
  if [[ -n "$LOS" ]]; then echo "$LOS"
  elif [[ "$1" == "whisper" ]]; then echo "$GEDEELD/whisper"
  else echo "$GEDEELD/llm"
  fi
}

BEHANDELD=()
while IFS=$'\t' read -r sleutel bestand url; do
  [[ "$sleutel" == "whisper" || "$sleutel" == "llm-$LLM" ]] || continue
  doel="$(doelmap "$sleutel")"
  mkdir -p "$doel"
  BEHANDELD+=("$doel/$bestand")
  if [[ -s "$doel/$bestand" ]]; then
    echo "Staat er al: $doel/$bestand"
    continue
  fi
  echo "Ophalen: $bestand"
  gelukt=""
  for poging in 1 2 3 4 5; do     # bij een verbroken verbinding: hervatten waar we waren
    if curl -L --fail --progress-bar -C - -o "$doel/$bestand.deel" "$url" < /dev/null; then
      gelukt=ja
      break
    fi
    echo "Verbinding verbroken (poging $poging van 5); de download wordt hervat..."
  done
  [[ -n "$gelukt" ]] || { echo "Downloaden mislukt: $url" >&2; exit 1; }
  mv "$doel/$bestand.deel" "$doel/$bestand"
done < <(grep -v '^#' "$HIER/modellen.tsv")

# Controleer dat het echte modelbestanden zijn (en geen foutpagina).
for pad in "${BEHANDELD[@]}"; do
  if [[ "$pad" == *.gguf && "$(head -c 4 "$pad")" != "GGUF" ]]; then
    echo "Ongeldig modelbestand: $pad" >&2
    exit 1
  fi
done
echo
echo "Klaar. Modellen:"
ls -lh "${BEHANDELD[@]}"
