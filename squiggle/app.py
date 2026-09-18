"""Menu bar app and entry point."""

import ctypes
import os
import subprocess
import sys

import rumps
from Foundation import NSBundle

from . import __version__, config, finder
from .overlay import ARROWS, Overlay
from .tap import GestureTap


def has_accessibility(prompt=False):
    from ApplicationServices import AXIsProcessTrustedWithOptions
    return bool(AXIsProcessTrustedWithOptions(
        {"AXTrustedCheckOptionPrompt": bool(prompt)}))


def _process_image():
    """Mach-O path of this process.

    When running from source, Accessibility permission is recorded against
    this, which is neither sys.executable nor the script path.
    """
    try:
        buf = ctypes.create_string_buffer(4096)
        size = ctypes.c_uint32(4096)
        ctypes.CDLL(None)._NSGetExecutablePath(buf, ctypes.byref(size))
        return buf.value.decode()
    except Exception as exc:                                    # noqa: BLE001
        return "<unavailable: %s>" % exc


def _permission_target():
    bundle = NSBundle.mainBundle().bundlePath()
    if bundle and bundle.endswith(".app"):
        return bundle
    return _process_image()


class SquiggleApp(rumps.App):
    ON, OFF, WAITING = "◉", "◎", "◌"

    def __init__(self):
        super().__init__(self.WAITING, quit_button=None)

        config.ensure_user_config()
        self._startup_error = None
        try:
            cfg = config.load()
        except config.ConfigError as exc:
            self._startup_error = str(exc)
            cfg = config.load(path=os.devnull)      # defaults only
        finder.set_root(cfg.finder_root)

        self.overlay = Overlay(cfg.show_trail, cfg.deadzone, cfg.trail_color)
        self.tap = GestureTap(cfg, self.overlay)
        self._tap_installed = False

        self.toggle_item = rumps.MenuItem("Enable Gestures", callback=self.toggle)
        self.toggle_item.state = 1
        self.trail_item = rumps.MenuItem("Show Trail", callback=self.toggle_trail)
        self.trail_item.state = 1 if cfg.show_trail else 0

        self.menu = [
            self.toggle_item,
            self.trail_item,
            None,
            rumps.MenuItem("Edit Config...", callback=self.edit_config),
            rumps.MenuItem("Reload Config", callback=self.reload_config),
            rumps.MenuItem("Gesture Reference...", callback=self.show_help),
            rumps.MenuItem("Accessibility Permission...", callback=self.show_perm),
            None,
            rumps.MenuItem("Quit Squiggle", callback=rumps.quit_application),
        ]

        # The rest needs a running NSApplication.
        self._startup = rumps.Timer(self._on_started, 1)
        self._startup.start()
        self._perm_poll = rumps.Timer(self._try_install_tap, 2)

    def _on_started(self, timer):
        timer.stop()
        # Build the panel up front so the first gesture is not delayed.
        self.overlay.prepare()
        if self._startup_error:
            rumps.alert("Squiggle: config error",
                        "%s\n\nUsing the defaults until it is fixed."
                        % self._startup_error)
        # Shows the system prompt once if permission is missing; after that
        # poll quietly until the user has granted it.
        has_accessibility(prompt=True)
        self._try_install_tap()
        if not self._tap_installed:
            self._perm_poll.start()

    def _try_install_tap(self, _timer=None):
        if self._tap_installed or not has_accessibility():
            return
        if self.tap.install():
            self._tap_installed = True
            self._perm_poll.stop()
            self.title = self.ON if self.tap.enabled else self.OFF

    def toggle(self, sender):
        enabled = not self.tap.enabled
        self.tap.set_enabled(enabled)
        sender.state = 1 if enabled else 0
        if self._tap_installed:
            self.title = self.ON if enabled else self.OFF

    def toggle_trail(self, sender):
        self.overlay.enabled = not self.overlay.enabled
        sender.state = 1 if self.overlay.enabled else 0
        if not self.overlay.enabled:
            self.overlay.end()

    def edit_config(self, _):
        subprocess.Popen(["/usr/bin/open", "-t", config.ensure_user_config()])

    def reload_config(self, _):
        try:
            cfg = config.load()
        except config.ConfigError as exc:
            rumps.alert("Squiggle: config error",
                        "%s\n\nThe previous configuration stays active." % exc)
            return
        finder.set_root(cfg.finder_root)
        self.tap.set_config(cfg)
        self.overlay.enabled = cfg.show_trail
        self.overlay.deadzone = cfg.deadzone
        self.overlay.color = cfg.trail_color
        self.trail_item.state = 1 if cfg.show_trail else 0

    def show_help(self, _):
        lines = ["".join(ARROWS[c] for c in seq).ljust(6) + act.name
                 for seq, act in self.tap.config.gestures.items()]
        lines.append("\nHold the right button and drag. ⊙ is the wheel.")
        rumps.alert("Squiggle %s" % __version__, "\n".join(lines))

    def show_perm(self, _):
        ok = has_accessibility(prompt=True)
        rumps.alert(
            "Accessibility Permission",
            "Granted." if ok else
            "Not granted. Open System Settings > Privacy & Security > "
            "Accessibility and enable:\n\n%s\n\nGestures start working as "
            "soon as it is granted." % _permission_target(),
        )


def _fix_stream_encoding():
    """A .app launched from Finder has no LANG, so the streams default to
    ASCII and any non-ASCII log line raises UnicodeEncodeError."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:                                       # noqa: BLE001
            pass


def _print_diagnostics():
    print("version          : %s" % __version__)
    print("executable image : %s" % _process_image())
    print("bundle           : %s" % (NSBundle.mainBundle().bundlePath() or "-"))
    print("accessibility    : %s"
          % ("granted" if has_accessibility() else "not granted"))
    print("config           : %s" % config.CONFIG_PATH)
    try:
        cfg = config.load()
        print("config status    : ok, %d gestures, %d app overrides"
              % (len(cfg.gestures), len(cfg.apps)))
    except config.ConfigError as exc:
        print("config status    : ERROR %s" % exc)


def main():
    _fix_stream_encoding()
    if "--check" in sys.argv:
        _print_diagnostics()
        return
    SquiggleApp().run()
