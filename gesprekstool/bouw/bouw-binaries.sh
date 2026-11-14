#!/bin/bash
# Bouwt whisper-cli (spraakherkenning) en llama-server (taalmodel) uit broncode.
#
# - Statisch gelinkt: elk programma is een los bestand zonder extra DLL's of bibliotheken.
# - llama-server zonder HTTPS-ondersteuning: het programma kan zelf niets downloaden.
# - Vaste versies (WHISPER_TAG en LLAMA_TAG), zodat elk pakket hetzelfde gedrag heeft.
#
# Gebruik:  WHISPER_TAG=v1.9.5 LLAMA_TAG=v1.0.0 bouw/bouw-binaries.sh
# Uitvoer:  bin/whisper/whisper-cli  en  bin/llama/llama-server  (.exe op Windows)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WERK="${WERK:-$ROOT/build/native}"
: "${WHISPER_TAG:?zet WHISPER_TAG}" "${LLAMA_TAG:?zet LLAMA_TAG}"

ALGEMEEN=(-DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF -DGGML_NATIVE=OFF -DGGML_OPENMP=OFF)
EXE=""
case "$(uname -s)" in
  Darwin)
    PLATFORM=(-DCMAKE_OSX_ARCHITECTURES=arm64 -DCMAKE_OSX_DEPLOYMENT_TARGET=13.3
              -DGGML_METAL=ON -DGGML_METAL_EMBED_LIBRARY=ON) ;;
  MINGW*|MSYS*|CYGWIN*)
    # Statische C-runtime (geen Visual C++-installatie nodig) en AVX2 als ondergrens.
    PLATFORM=(-A x64 -DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreaded -DCMAKE_POLICY_DEFAULT_CMP0091=NEW
              -DGGML_SSE42=ON -DGGML_AVX=ON -DGGML_AVX2=ON -DGGML_BMI2=ON)
    EXE=".exe" ;;
  *)
    PLATFORM=() ;;
esac

bouw() {  # bouw <naam> <repo> <tag> <doel> <submap> [extra cmake-opties...]
  local naam="$1" repo="$2" tag="$3" doel="$4" submap="$5"
  shift 5
  local bron="$WERK/$naam"
  rm -rf "$bron"
  git clone --quiet --depth 1 --branch "$tag" "https://github.com/$repo.git" "$bron"
  cmake -S "$bron" -B "$bron/build" "${ALGEMEEN[@]}" ${PLATFORM[@]+"${PLATFORM[@]}"} "$@"
  cmake --build "$bron/build" --config Release --target "$doel" -j 4
  local binair
  binair="$(find "$bron/build" -type f -name "$doel$EXE" | head -1)"
  [[ -n "$binair" ]] || { echo "Bouwen mislukt: $doel$EXE niet gevonden" >&2; exit 1; }
  mkdir -p "$ROOT/bin/$submap"
  cp "$binair" "$ROOT/bin/$submap/"
  echo "Gebouwd: bin/$submap/$doel$EXE ($repo $tag)"
}

mkdir -p "$WERK"
bouw whisper ggml-org/whisper.cpp "$WHISPER_TAG" whisper-cli whisper \
  -DWHISPER_BUILD_TESTS=OFF -DWHISPER_BUILD_SERVER=OFF -DWHISPER_SDL2=OFF
bouw llama ggml-org/llama.cpp "$LLAMA_TAG" llama-server llama \
  -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_EXAMPLES=OFF -DLLAMA_OPENSSL=OFF \
  -DLLAMA_BUILD_UI=OFF -DLLAMA_USE_PREBUILT_UI=OFF

printf 'whisper.cpp %s\nllama.cpp %s\n' "$WHISPER_TAG" "$LLAMA_TAG" > "$ROOT/bin/VERSIES.txt"
if [[ "$(uname -s)" == "Darwin" ]]; then      # toon van welke bibliotheken de programma's afhangen
  otool -L "$ROOT/bin/whisper/whisper-cli" "$ROOT/bin/llama/llama-server"
fi
