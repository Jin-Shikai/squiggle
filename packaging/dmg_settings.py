"""dmgbuild settings: the drag-to-Applications window.

Called by install.sh --build-only. dmgbuild writes the window layout straight
into the image's .DS_Store, so no Finder scripting or permission is involved.
"""

import os

app = defines["app"]                                # noqa: F821

format = "UDZO"
files = [app]
symlinks = {"Applications": "/Applications"}
icon = "packaging/Squiggle.icns"            # relative to the repo root

background = "builtin-arrow"
window_rect = ((200, 200), (600, 380))
default_view = "icon-view"
show_status_bar = False
show_tab_view = False
show_toolbar = False
show_pathbar = False
show_sidebar = False
icon_size = 110
text_size = 13
icon_locations = {
    os.path.basename(app): (150, 170),
    "Applications": (450, 170),
}
