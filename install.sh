#!/bin/bash
#
# Build Squiggle.app, sign it and install it to /Applications.
#
#   ./install.sh                build, sign, install
#   ./install.sh --build-only   build, sign, make dist/Squiggle-x.y.z.dmg for
#                               a release
#
# To run it from Finder, double-click Install.command instead: a terminal
# that opens this file directly closes the window as soon as it exits.
#
# Signs with the identity in SQUIGGLE_SIGN_ID, default "-" (ad hoc). With an
# ad-hoc signature every rebuild invalidates the Accessibility grant, which
# then has to be removed and re-added by hand. A Developer ID keeps it.
#
# Every expansion is written ${VAR}: under a UTF-8 locale bash 3.2 folds a
# following multi-byte character into the variable name, and $VAR then fails
# with "unbound variable".
set -euo pipefail
cd "$(dirname "$0")"

APP="dist/Squiggle.app"
DEST="${SQUIGGLE_DEST:-/Applications/Squiggle.app}"
SIGN_ID="${SQUIGGLE_SIGN_ID:--}"
LOG="${TMPDIR:-/tmp}/squiggle-build.log"

echo "==> Building, log at ${LOG}"
rm -rf build dist
if ! .venv/bin/python setup.py py2app > "${LOG}" 2>&1; then
    echo "Build failed:" >&2
    tail -20 "${LOG}" >&2
    exit 1
fi

echo "==> Signing with ${SIGN_ID}"
codesign --force --deep --sign "${SIGN_ID}" "${APP}"
codesign --verify --deep --strict "${APP}"

if [ "${1:-}" = "--build-only" ]; then
    VERSION="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "${APP}/Contents/Info.plist")"
    DMG="dist/Squiggle-${VERSION}.dmg"
    .venv/bin/dmgbuild -s packaging/dmg_settings.py -D app="${APP}" \
        "Squiggle" "${DMG}" > /dev/null
    echo "==> ${DMG}"
    exit 0
fi

echo "==> Stopping any running instance"
pkill -f "Squiggle.app/Contents/MacOS/Squiggle" 2>/dev/null || true
sleep 1

echo "==> Installing to ${DEST}"
rm -rf "${DEST}"
cp -R "${APP}" "${DEST}"

echo "==> Self check"
"${DEST}/Contents/MacOS/Squiggle" --check

cat <<'TIP'

Launch Squiggle. On first launch macOS asks for Accessibility permission;
gestures start as soon as it is granted.

If this replaced an earlier ad-hoc signed build, the old grant is stale:
  1. System Settings > Privacy & Security > Accessibility
  2. Select the Squiggle entry and remove it with "-".
     Toggling it off and on is not enough.
  3. Launch Squiggle again and grant the permission when asked.
TIP
