#!/usr/bin/env bash
# Baut FanFicFare.zip, entfernt vorhandene FanFicFare-Plugins aus Calibre
# und installiert die frisch gebaute ZIP.
#
# Funktioniert mit einer normalen Calibre-Installation und mit Flatpak.
#
# Umgebungsvariablen:
#   CALIBRE_INSTALL=auto|native|flatpak   Welche Installation (Standard: auto,
#                                         native wird bevorzugt)
#   CALIBRE_CUSTOMIZE=/pfad/zu/calibre-customize
#                                         Expliziter Pfad (nur für native)
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ZIP="$REPO_DIR/FanFicFare.zip"
FLATPAK_APP="com.calibre_ebook.calibre"
CALIBRE_INSTALL="${CALIBRE_INSTALL:-auto}"
CALIBRE_CUSTOMIZE="${CALIBRE_CUSTOMIZE:-calibre-customize}"
# Aktueller Name und der alte Name des Plugins (vor der Umbenennung)
PLUGIN_NAMES=("FanFicFare" "FanFictionDownLoader")

die() { echo "Fehler: $*" >&2; exit 1; }

have_native()  { command -v "$CALIBRE_CUSTOMIZE" >/dev/null 2>&1; }
have_flatpak() { command -v flatpak >/dev/null 2>&1 &&
                 flatpak info "$FLATPAK_APP" >/dev/null 2>&1; }

case "$CALIBRE_INSTALL" in
    auto)
        if have_native; then MODE=native
        elif have_flatpak; then MODE=flatpak
        else die "Weder '$CALIBRE_CUSTOMIZE' noch Flatpak '$FLATPAK_APP' gefunden."
        fi ;;
    native)
        have_native || die "'$CALIBRE_CUSTOMIZE' nicht gefunden."
        MODE=native ;;
    flatpak)
        have_flatpak || die "Flatpak '$FLATPAK_APP' nicht installiert."
        MODE=flatpak ;;
    *)
        die "CALIBRE_INSTALL muss auto, native oder flatpak sein." ;;
esac

if [[ $MODE == flatpak ]]; then
    # Repo-Verzeichnis read-only freigeben, damit die Sandbox die ZIP sieht.
    CUSTOMIZE=(flatpak run --command=calibre-customize
               "--filesystem=$REPO_DIR:ro" "$FLATPAK_APP")
else
    CUSTOMIZE=("$CALIBRE_CUSTOMIZE")
fi
echo "==> Verwende Calibre-Installation: $MODE"

calibre_running() {
    pgrep -x calibre >/dev/null 2>&1 && return 0
    command -v flatpak >/dev/null 2>&1 &&
        flatpak ps --columns=application 2>/dev/null | grep -qx "$FLATPAK_APP"
}
calibre_running && die "Calibre läuft noch. Bitte zuerst beenden."

echo "==> Baue $ZIP"
cd "$REPO_DIR"
rm -f "$ZIP"
python3 makeplugin.py
[[ -s "$ZIP" ]] || die "ZIP wurde nicht erzeugt."

echo "==> Entferne vorhandene Plugins"
for name in "${PLUGIN_NAMES[@]}"; do
    # Gibt nur eine Meldung aus, wenn das Plugin nicht installiert ist
    "${CUSTOMIZE[@]}" -r "$name" || true
done

echo "==> Installiere $ZIP"
"${CUSTOMIZE[@]}" -a "$ZIP"

if [[ $MODE == flatpak ]]; then
    echo "==> Fertig. Start mit Debug-Ausgabe:"
    echo "    flatpak run --command=calibre-debug $FLATPAK_APP -g"
else
    echo "==> Fertig. Start mit Debug-Ausgabe: calibre-debug -g"
fi
