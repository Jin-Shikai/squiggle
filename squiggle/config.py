"""User configuration, read from a TOML file.

The file lives outside the app bundle so that editing it never touches the
code signature (and with it the Accessibility grant). default_config.toml is
copied there on first launch and documents every option.
"""

import os
import re
import shutil
import subprocess
import tomllib

from . import finder
from .events import parse_keys, post_key

CONFIG_DIR = os.path.expanduser("~/Library/Application Support/Squiggle")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.toml")
DEFAULT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "default_config.toml")

# Drag sequences never repeat a direction back to back; wheel gestures are
# the two fixed names.
_SEQ_RE = re.compile(r"^(?:WU|WD|(?:([LRUD])(?!\1))+)$")

BUILTIN_ACTIONS = {
    "finder_parent": finder.back,
    "finder_forward": finder.forward,
}


class ConfigError(ValueError):
    pass


class Action:
    """What a gesture does: a label for the bubble and a callable."""

    __slots__ = ("name", "run")

    def __init__(self, name, run):
        self.name = name
        self.run = run


def _run_shell(command):
    subprocess.Popen(command, shell=True, start_new_session=True,
                     stdin=subprocess.DEVNULL)


def _build_action(seq, spec):
    if not isinstance(spec, dict):
        raise ConfigError("gesture %s: expected a table like "
                          '{ name = "Back", keys = "cmd+[" }' % seq)
    kinds = [k for k in ("keys", "action", "shell") if k in spec]
    if len(kinds) != 1:
        raise ConfigError("gesture %s: give exactly one of keys, action, "
                          "shell" % seq)
    kind, value = kinds[0], spec[kinds[0]]
    if not isinstance(value, str) or not value:
        raise ConfigError("gesture %s: %s must be a string" % (seq, kind))

    if kind == "keys":
        try:
            keycode, flags = parse_keys(value)
        except ValueError as exc:
            raise ConfigError("gesture %s: %s" % (seq, exc)) from None
        run = lambda: post_key(keycode, flags)                  # noqa: E731
    elif kind == "action":
        if value not in BUILTIN_ACTIONS:
            raise ConfigError("gesture %s: unknown action %r (available: %s)"
                              % (seq, value, ", ".join(BUILTIN_ACTIONS)))
        run = BUILTIN_ACTIONS[value]
    else:
        run = lambda: _run_shell(value)                         # noqa: E731
    return Action(str(spec.get("name", value)), run)


def _build_table(raw, where, allow_disable=False):
    if not isinstance(raw, dict):
        raise ConfigError("%s must be a table" % where)
    table = {}
    for seq, spec in raw.items():
        if not _SEQ_RE.match(seq):
            raise ConfigError(
                "%s: %r is not a gesture. Use L R U D in drag order "
                "(no direction twice in a row), or WU / WD for the wheel."
                % (where, seq))
        if allow_disable and spec is False:
            table[seq] = None
        else:
            table[seq] = _build_action(seq, spec)
    return table


def _number(settings, key, minimum):
    value = settings[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)) \
            or value < minimum:
        raise ConfigError("settings.%s must be a number >= %s" % (key, minimum))
    return value


class Config:
    def __init__(self, data):
        settings = data["settings"]
        self.step = _number(settings, "step", 1)
        self.deadzone = _number(settings, "deadzone", 0)
        self.wheel_cooldown = _number(settings, "wheel_cooldown", 0)
        self.show_trail = bool(settings["show_trail"])
        self.finder_root = str(settings["finder_root"])

        color = settings["trail_color"]
        if not (isinstance(color, list) and len(color) == 4
                and all(isinstance(c, (int, float)) and 0 <= c <= 1
                        for c in color)):
            raise ConfigError("settings.trail_color must be [r, g, b, a] "
                              "with values from 0 to 1")
        self.trail_color = tuple(float(c) for c in color)

        passthrough = data["passthrough"]
        if not (isinstance(passthrough, list)
                and all(isinstance(b, str) for b in passthrough)):
            raise ConfigError("passthrough must be a list of bundle ids")
        self.passthrough = frozenset(passthrough)

        self.gestures = _build_table(data["gestures"], "[gestures]")
        if not isinstance(data["apps"], dict):
            raise ConfigError("[apps] must be a table")
        self.apps = {
            bundle_id: _build_table(raw, '[apps."%s"]' % bundle_id,
                                    allow_disable=True)
            for bundle_id, raw in data["apps"].items()
        }

    def gestures_for(self, bundle_id):
        """Effective gesture table for an app: globals plus its overrides."""
        table = dict(self.gestures)
        table.update(self.apps.get(bundle_id, {}))
        return {seq: act for seq, act in table.items() if act is not None}


def _read(path):
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError("%s: %s" % (os.path.basename(path), exc)) from None


def load(path=CONFIG_PATH):
    """Defaults overlaid with the user's file.

    [settings] merges key by key. gestures, apps and passthrough replace the
    defaults wholesale when present, so that defaults can be removed.
    """
    data = _read(DEFAULT_PATH)
    if os.path.exists(path):
        user = _read(path)
        unknown = set(user) - set(data)
        if unknown:
            raise ConfigError("unknown section: %s" % ", ".join(sorted(unknown)))
        settings = user.pop("settings", {})
        if not isinstance(settings, dict):
            raise ConfigError("[settings] must be a table")
        unknown = set(settings) - set(data["settings"])
        if unknown:
            raise ConfigError("unknown setting: %s" % ", ".join(sorted(unknown)))
        data["settings"].update(settings)
        data.update(user)
    return Config(data)


def ensure_user_config():
    """Create the user's config from the default on first launch."""
    if not os.path.exists(CONFIG_PATH):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        shutil.copyfile(DEFAULT_PATH, CONFIG_PATH)
    return CONFIG_PATH
