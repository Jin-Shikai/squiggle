"""Synthetic keyboard and mouse events."""

from Quartz import (
    CGEventCreateKeyboardEvent,
    CGEventCreateMouseEvent,
    CGEventPost,
    CGEventSetFlags,
    CGEventSetIntegerValueField,
    CGEventSourceCreate,
    kCGEventFlagMaskAlternate,
    kCGEventFlagMaskCommand,
    kCGEventFlagMaskControl,
    kCGEventFlagMaskShift,
    kCGEventRightMouseDown,
    kCGEventRightMouseUp,
    kCGEventSourceStateHIDSystemState,
    kCGEventSourceUserData,
    kCGHIDEventTap,
    kCGMouseButtonRight,
    kCGMouseEventClickState,
)

MAGIC = 0x4D47   # marks our own synthetic events so the tap ignores them

MODIFIERS = {
    "cmd": kCGEventFlagMaskCommand, "command": kCGEventFlagMaskCommand,
    "shift": kCGEventFlagMaskShift,
    "alt": kCGEventFlagMaskAlternate, "opt": kCGEventFlagMaskAlternate,
    "option": kCGEventFlagMaskAlternate,
    "ctrl": kCGEventFlagMaskControl, "control": kCGEventFlagMaskControl,
}

# Virtual keycodes of the ANSI layout. They name physical keys, so "[" on a
# layout without a dedicated bracket key sends whatever sits in that position.
KEYCODES = {
    "a": 0, "s": 1, "d": 2, "f": 3, "h": 4, "g": 5, "z": 6, "x": 7, "c": 8,
    "v": 9, "b": 11, "q": 12, "w": 13, "e": 14, "r": 15, "y": 16, "t": 17,
    "1": 18, "2": 19, "3": 20, "4": 21, "6": 22, "5": 23, "=": 24, "9": 25,
    "7": 26, "-": 27, "8": 28, "0": 29, "]": 30, "o": 31, "u": 32, "[": 33,
    "i": 34, "p": 35, "return": 36, "l": 37, "j": 38, "'": 39, "k": 40,
    ";": 41, "\\": 42, ",": 43, "/": 44, "n": 45, "m": 46, ".": 47,
    "tab": 48, "space": 49, "`": 50, "delete": 51, "escape": 53,
    "f1": 122, "f2": 120, "f3": 99, "f4": 118, "f5": 96, "f6": 97,
    "f7": 98, "f8": 100, "f9": 101, "f10": 109, "f11": 103, "f12": 111,
    "home": 115, "pageup": 116, "forwarddelete": 117, "end": 119,
    "pagedown": 121, "left": 123, "right": 124, "down": 125, "up": 126,
}


def parse_keys(spec):
    """'cmd+shift+[' -> (keycode, flags). Raises ValueError."""
    *mods, key = [p.strip().lower() for p in spec.split("+")]
    if key not in KEYCODES:
        raise ValueError("unknown key %r in %r" % (key, spec))
    flags = 0
    for mod in mods:
        if mod not in MODIFIERS:
            raise ValueError("unknown modifier %r in %r" % (mod, spec))
        flags |= MODIFIERS[mod]
    return KEYCODES[key], flags


def _source():
    return CGEventSourceCreate(kCGEventSourceStateHIDSystemState)


def post_key(keycode, flags=0):
    src = _source()
    for is_down in (True, False):
        ev = CGEventCreateKeyboardEvent(src, keycode, is_down)
        CGEventSetFlags(ev, flags)
        CGEventPost(kCGHIDEventTap, ev)


def post_right_click(pos):
    """Replay the right click that was swallowed on mouse down."""
    src = _source()
    for etype in (kCGEventRightMouseDown, kCGEventRightMouseUp):
        ev = CGEventCreateMouseEvent(src, etype, pos, kCGMouseButtonRight)
        CGEventSetIntegerValueField(ev, kCGEventSourceUserData, MAGIC)
        CGEventSetIntegerValueField(ev, kCGMouseEventClickState, 1)
        CGEventPost(kCGHIDEventTap, ev)
