#!/bin/bash
# Installeert de Gesprekstool voor alle gebruikers van deze Mac:
# de app in /Applications en de modellen in /Library/Application Support/Gesprekstool.
#
#   sudo ./mac-installeren.sh [map-met-modellen]
#   sudo ./mac-installeren.sh --verwijderen
set -euo pipefail

[[ $EUID -eq 0 ]] || { echo "Start dit script met sudo." >&2; exit 1; }
HIER="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRON="$HIER/../Gesprekstool.app"
APP="/Applications/Gesprekstool.app"
SYSTEEM="/Library/Application Support/Gesprekstool"

if [[ "${1:-}" == "--verwijderen" ]]; then
  rm -rf "$APP" "$SYSTEEM"
  echo "De Gesprekstool is verwijderd."
  echo "Gesprekken van gebruikers staan nog in hun eigen map: ~/GesprekkenLokaal"
  exit 0
fi

[[ -d "$BRON" ]] || { echo "Gesprekstool.app niet gevonden naast de map 'beheer'." >&2; exit 1; }

echo "1/3 App kopieren naar $APP"
rm -rf "$APP"
ditto "$BRON" "$APP"
xattr -dr com.apple.quarantine "$APP" 2>/dev/null || true

echo "2/3 Modellen plaatsen in $SYSTEEM/models"
mkdir -p "$SYSTEEM/models"
if [[ -n "${1:-}" ]]; then
  cp "$1"/* "$SYSTEEM/models/"
fi
chmod -R a+rX "$SYSTEEM"

echo "3/3 Controle"
sudo -u "${SUDO_USER:-root}" "$APP/Contents/MacOS/Gesprekstool" --controle || true
