#!/bin/bash
# Installatie van de gesprekstool op macOS.
# Dit is de ENIGE stap die internet gebruikt (programma's en modellen downloaden).
# Daarna werkt alles zonder netwerk.
#
# Opties (omgevingsvariabelen):
#   LLM=4b ./install.sh     kies het kleine taalmodel (standaard: 12b bij >= 16 GB RAM)
#   LLM=12b ./install.sh    kies het grote taalmodel
set -euo pipefail

HIER="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_HOME="${GESPREKSTOOL_HOME:-$HOME/.gesprekstool}"
DATA="$HOME/GesprekkenLokaal"
HF="https://huggingface.co"

stap() { printf '\n==> %s\n' "$1"; }
stop() { printf '\nFOUT: %s\n' "$1" >&2; exit 1; }

[[ "$(uname -s)" == "Darwin" ]] || stop "Dit script werkt alleen op macOS."
command -v brew >/dev/null 2>&1 || stop "Homebrew ontbreekt. Installeer het via https://brew.sh en draai dit script opnieuw."
command -v python3 >/dev/null 2>&1 || stop "python3 ontbreekt. Installeer het met: brew install python"
[[ "$(uname -m)" == "arm64" ]] || echo "LET OP: dit is geen Apple Silicon-Mac; transcriberen en samenvatten zijn dan traag."

stap "1/5 Programma's installeren (ffmpeg, whisper.cpp, llama.cpp)"
export HOMEBREW_NO_ANALYTICS=1
brew install ffmpeg whisper-cpp llama.cpp

stap "2/5 Modellen downloaden (eenmalig, enkele GB)"
RAM_GB=$(( $(sysctl -n hw.memsize) / 1073741824 ))
LLM="${LLM:-$([[ $RAM_GB -ge 16 ]] && echo 12b || echo 4b)}"
case "$LLM" in
  12b) CONTEXT=16384 ;;
  4b)  CONTEXT=8192 ;;
  *)   stop "Onbekende waarde LLM=$LLM (kies 4b of 12b)." ;;
esac
echo "   Werkgeheugen: ${RAM_GB} GB -> taalmodel gemma-3-${LLM}"
mkdir -p "$APP_HOME/models"
WHISPER="$APP_HOME/models/ggml-large-v3-turbo.bin"
LLM_FILE="$APP_HOME/models/gemma-3-${LLM}-it-Q4_K_M.gguf"

download() {  # download <doel> <url> [<terugval-url> ...]
  local doel="$1" i=0 url
  shift
  if [[ -s "$doel" ]]; then echo "   staat er al: $doel"; return 0; fi
  for url in "$@"; do
    i=$((i + 1))
    echo "   $url"
    if curl -L --fail --progress-bar -C - -o "$doel.part$i" "$url"; then
      mv "$doel.part$i" "$doel"
      return 0
    fi
  done
  return 1
}

download "$WHISPER" \
  "$HF/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo.bin" \
  || stop "Whisper-model downloaden mislukt. Controleer de internetverbinding en draai het script opnieuw."
download "$LLM_FILE" \
  "$HF/ggml-org/gemma-3-${LLM}-it-GGUF/resolve/main/gemma-3-${LLM}-it-Q4_K_M.gguf" \
  "$HF/bartowski/google_gemma-3-${LLM}-it-GGUF/resolve/main/google_gemma-3-${LLM}-it-Q4_K_M.gguf" \
  || stop "Taalmodel downloaden mislukt. Controleer de internetverbinding en draai het script opnieuw."

# Controleer dat het echte modelbestanden zijn (geen foutpagina).
[[ "$(head -c 4 "$LLM_FILE")" == "GGUF" ]] || stop "$LLM_FILE is geen geldig model. Verwijder het en draai opnieuw."
[[ $(stat -f %z "$WHISPER") -gt 100000000 ]] || stop "$WHISPER is te klein. Verwijder het en draai opnieuw."

stap "3/5 Tool installeren in $APP_HOME"
mkdir -p "$APP_HOME/app" "$APP_HOME/templates"
cp "$HIER/gesprek.py" "$APP_HOME/app/gesprek.py"
chmod +x "$APP_HOME/app/gesprek.py"
cp -n "$HIER"/templates/*.md "$APP_HOME/templates/" || true   # eigen templates blijven staan
ln -sf "$APP_HOME/app/gesprek.py" "$(brew --prefix)/bin/gesprek"

# Instellingen: bestaande keuzes blijven staan, modelpaden worden bijgewerkt.
python3 - "$APP_HOME/config.json" "$WHISPER" "$LLM_FILE" "$CONTEXT" "$DATA" <<'PY'
import json, os, sys
pad, whisper, llm, context, data = sys.argv[1:6]
cfg = {}
if os.path.exists(pad):
    with open(pad, encoding="utf-8") as f:
        cfg = json.load(f)
cfg.update({"whisper_model": whisper, "llm_model": llm, "context_tokens": int(context)})
cfg.setdefault("data_map", data)
cfg.setdefault("microfoon", ":default")
cfg.setdefault("sandbox", True)
cfg.setdefault("verwijder_audio_na_verwerking", False)
with open(pad, "w", encoding="utf-8") as f:
    json.dump(cfg, f, ensure_ascii=False, indent=2)
PY

stap "4/5 Opslagmap beveiligen ($DATA)"
mkdir -p "$DATA"
chmod 700 "$DATA" "$APP_HOME"
tmutil addexclusion "$DATA" 2>/dev/null \
  && echo "   Uitgesloten van Time Machine-back-ups." \
  || echo "   LET OP: kon de map niet uitsluiten van Time Machine."

stap "5/5 Controle"
"$APP_HOME/app/gesprek.py" controle || true

cat <<EOF

Installatie klaar. Vanaf nu is er geen internet meer nodig.
Start een gesprek met:   gesprek
Templates aanpassen:     $APP_HOME/templates
Gesprekken staan in:     $DATA
EOF
