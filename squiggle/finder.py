"""Finder: hierarchy-based back / forward.

Finder's own Cmd-[ / Cmd-] follow the browsing history, which is not the
folder hierarchy. These walk the hierarchy instead: back goes to the parent
(never above `root`), forward returns to the subfolder back came from.

Each Finder window keeps its own path stack. Forward checks that the parent
of the stack top is the current folder; if not, you navigated somewhere else
in between and the whole record is dropped, like a browser greying out its
forward button.
"""

import os
import queue
import sys
import threading
import traceback

from Foundation import NSAppleScript

from .events import KEYCODES, MODIFIERS, post_key

ERR_NOT_AUTHORIZED = -1743      # errAEEventNotPermitted

MAX_FORWARD_DEPTH = 64
MAX_FORWARD_WINDOWS = 32

# Ceiling for "parent folder": never navigate above this. Set from the config.
root = os.path.expanduser("~") + "/"

_forward_stacks = {}                # window id -> paths, deepest last
_forward_lock = threading.Lock()

_jobs = queue.Queue(maxsize=1)
_worker_lock = threading.Lock()
_worker_started = False


def set_root(path):
    global root
    root = norm_dir(os.path.expanduser(path))


# ---------------------------------------------------------------------------
# AppleScript
# ---------------------------------------------------------------------------

class AppleScriptError(Exception):
    def __init__(self, info):
        self.number = 0
        message = "unknown error"
        if info is not None:
            self.number = int(info.get("NSAppleScriptErrorNumber", 0) or 0)
            message = info.get("NSAppleScriptErrorMessage", message)
        super().__init__("AppleScript error %d: %s" % (self.number, message))

    @property
    def not_authorized(self):
        return self.number == ERR_NOT_AUTHORIZED


def run_applescript(source):
    """Run a script in-process and return its result as text.

    NSAppleScript rather than the osascript binary: spawning osascript costs
    about 21 ms per call, compiling and running in-process costs about 0.1 ms.
    """
    script = NSAppleScript.alloc().initWithSource_(source)
    result, error = script.executeAndReturnError_(None)
    if result is None:
        raise AppleScriptError(error)
    return result.stringValue() or ""


def _as_applescript_string(text):
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


# Do not iterate with `repeat with w in Finder windows` and then ask for
# `id of w`: those are unresolved object specifiers and Finder answers -1731
# Unknown object type. `front Finder window` is the form that works.
_QUERY_SCRIPT = """
tell application "Finder"
    if (count of Finder windows) < 1 then return "none"
    set w to front Finder window
    try
        set p to POSIX path of ((target of w) as alias)
    on error
        return "none"
    end try
    return ((id of w) as text) & tab & p
end tell
"""

# Re-checking the window id also closes the race: if the front window changed
# since the query, this reports "gone" rather than navigating the wrong one.
_NAVIGATE_SCRIPT = """
set wid to %(wid)s
set dest to %(dest)s
try
    set d to (POSIX file dest) as alias
on error
    return "missing"
end try
tell application "Finder"
    if (count of Finder windows) < 1 then return "gone"
    set w to front Finder window
    if ((id of w) as integer) is not wid then return "gone"
    set target of w to d
    return "ok"
end tell
"""


# ---------------------------------------------------------------------------
# Paths and the forward stacks
# ---------------------------------------------------------------------------

def norm_dir(path):
    """Normalise to a trailing slash, the form Finder reports."""
    if not path:
        return ""
    return path if path.endswith("/") else path + "/"


def parent_dir(path):
    """'/a/b/c/' -> '/a/b/'. Returns '' at '/', meaning there is no parent."""
    stripped = path.rstrip("/")
    if not stripped:
        return ""
    return norm_dir(os.path.dirname(stripped))


def _posix_arg(path):
    """Drop the trailing slash for POSIX file; keep it for the root."""
    return path.rstrip("/") or "/"


def push_forward(wid, path):
    with _forward_lock:
        if len(_forward_stacks) > MAX_FORWARD_WINDOWS:
            _forward_stacks.clear()
        stack = _forward_stacks.setdefault(wid, [])
        if not stack or stack[-1] != path:
            stack.append(path)
            del stack[:-MAX_FORWARD_DEPTH]


def pop_forward(wid, current):
    """Next folder down from `current`, or None.

    A stack top that no longer descends from `current` means the user
    navigated away, so the record for that window is discarded.
    """
    with _forward_lock:
        stack = _forward_stacks.get(wid)
        if not stack:
            return None
        if parent_dir(stack[-1]) != current:
            _forward_stacks.pop(wid, None)
            return None
        dest = stack.pop()
        if not stack:
            _forward_stacks.pop(wid, None)
        return dest


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------

def _query():
    """(window id, folder) of the front Finder window, or (None, None)."""
    out = run_applescript(_QUERY_SCRIPT)
    if not out or out == "none":
        return None, None
    wid, _, path = out.partition("\t")
    try:
        return int(wid), norm_dir(path)
    except ValueError:
        return None, None


def _navigate(wid, path):
    return run_applescript(_NAVIGATE_SCRIPT % {
        "wid": int(wid),
        "dest": _as_applescript_string(_posix_arg(path)),
    })


def _back_job():
    wid, current = _query()
    if wid is None or current == root:
        return
    parent = parent_dir(current)
    if not parent:
        return
    if current.startswith(root) and not parent.startswith(root):
        return
    if _navigate(wid, parent) == "ok":
        push_forward(wid, current)


def _forward_job():
    wid, current = _query()
    if wid is None:
        return
    dest = pop_forward(wid, current)
    if dest is None:
        return
    result = _navigate(wid, dest)
    if result not in ("ok", "missing"):
        push_forward(wid, dest)         # transient failure, keep the record


def _worker_loop():
    while True:
        job, fallback = _jobs.get()
        try:
            job()
        except AppleScriptError as exc:
            if exc.not_authorized:
                # No Automation permission for Finder: fall back to the
                # system shortcut. Loses the hierarchy semantics but works.
                post_key(*fallback)
            else:
                print(exc, file=sys.stderr)
        except Exception:                                       # noqa: BLE001
            traceback.print_exc()


def _submit(job, fallback):
    """Queue Finder work off the event tap thread.

    One worker thread keeps NSAppleScript calls serialised. The queue is
    bounded so a slow or hung Finder cannot pile up gestures.
    """
    global _worker_started
    with _worker_lock:
        if not _worker_started:
            threading.Thread(target=_worker_loop, daemon=True).start()
            _worker_started = True
    try:
        _jobs.put_nowait((job, fallback))
    except queue.Full:
        pass


def back():
    _submit(_back_job, (KEYCODES["up"], MODIFIERS["cmd"]))


def forward():
    _submit(_forward_job, (KEYCODES["]"], MODIFIERS["cmd"]))
