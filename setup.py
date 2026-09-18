"""Build Squiggle.app with py2app. Use ./install.sh rather than calling this.

argv_emulation must stay False; it conflicts with Accessibility permission.
"""

import re

from setuptools import setup

# Change to your own reverse-DNS id before distributing. macOS keys the
# Accessibility grant to it, so pick it once and keep it.
BUNDLE_ID = "io.github.Jin-Shikai.Squiggle"

with open("squiggle/__init__.py") as f:
    VERSION = re.search(r'__version__ = "(.+?)"', f.read()).group(1)

OPTIONS = {
    "argv_emulation": False,
    "iconfile": "packaging/Squiggle.icns",
    # As directories rather than inside the zip: squiggle ships a data file.
    "packages": ["rumps", "squiggle"],
    "plist": {
        "CFBundleName": "Squiggle",
        "CFBundleDisplayName": "Squiggle",
        "CFBundleIdentifier": BUNDLE_ID,
        "CFBundleVersion": VERSION,
        "CFBundleShortVersionString": VERSION,
        "LSUIElement": True,          # menu bar only, no Dock icon
        "LSMinimumSystemVersion": "11.0",
        # Finder's parent-folder gesture drives Finder over Apple Events.
        "NSAppleEventsUsageDescription":
            "Squiggle controls Finder to navigate folders.",
    },
}

setup(
    name="Squiggle",
    version=VERSION,
    app=["Squiggle.py"],
    options={"py2app": OPTIONS},
)
