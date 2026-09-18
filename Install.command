#!/bin/bash
#
# Double-click entry point for Finder. Runs install.sh and keeps the window
# open afterwards, so the output stays readable whether the build succeeded
# or failed. From a terminal, run ./install.sh directly.
cd "$(dirname "$0")"

./install.sh "$@"
STATUS=$?

echo
if [ ${STATUS} -eq 0 ]; then
    echo "==> Done."
else
    echo "==> Install failed with exit code ${STATUS}." >&2
fi
read -n 1 -s -r -p "Press any key to close this window."
echo
exit ${STATUS}
