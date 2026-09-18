"""The event tap: turns right-button events into gestures.

The tap swallows rightMouseDown and rightMouseDragged before they reach the
frontmost app and decides on mouse up: run the gesture, or synthesise a plain
right click if the pointer barely moved. The side effect is that the context
menu opens on release rather than on press, matching Windows.
"""

import time
import traceback

from AppKit import NSWorkspace
from Foundation import NSUserDefaults
from Quartz import (
    CFMachPortCreateRunLoopSource,
    CFRunLoopAddSource,
    CFRunLoopGetCurrent,
    CGEventGetIntegerValueField,
    CGEventGetLocation,
    CGEventMaskBit,
    CGEventTapCreate,
    CGEventTapEnable,
    kCFRunLoopCommonModes,
    kCGEventRightMouseDown,
    kCGEventRightMouseDragged,
    kCGEventRightMouseUp,
    kCGEventScrollWheel,
    kCGEventSourceUserData,
    kCGEventTapDisabledByTimeout,
    kCGEventTapDisabledByUserInput,
    kCGEventTapOptionDefault,
    kCGHeadInsertEventTap,
    kCGScrollWheelEventDeltaAxis1,
    kCGSessionEventTap,
)

from .events import MAGIC, post_right_click
from .tracker import Tracker


def frontmost_bundle_id():
    app = NSWorkspace.sharedWorkspace().frontmostApplication()
    return app.bundleIdentifier() if app else None


class GestureTap:
    """One tap on the main run loop for the right button and the wheel.

    Do not call CGEventTapEnable from inside the callback while handling a
    real event (for instance to switch a second, wheel-only tap on and off):
    the call round-trips to the window server, which is itself waiting for
    the callback to return. Every right click then stalls for seconds until
    the system disables the tap by timeout.
    """

    def __init__(self, config, overlay, demo):
        self.config = config
        self.overlay = overlay
        self.demo = demo
        self.tracker = Tracker(config.step)
        self.enabled = True
        self._tap = None

    def install(self):
        """Create the tap. False if macOS refuses, i.e. no Accessibility."""
        mask = (CGEventMaskBit(kCGEventRightMouseDown)
                | CGEventMaskBit(kCGEventRightMouseUp)
                | CGEventMaskBit(kCGEventRightMouseDragged)
                | CGEventMaskBit(kCGEventScrollWheel))
        self._tap = CGEventTapCreate(
            kCGSessionEventTap, kCGHeadInsertEventTap,
            kCGEventTapOptionDefault, mask, self._callback, None)
        if self._tap is None:
            return False
        source = CFMachPortCreateRunLoopSource(None, self._tap, 0)
        CFRunLoopAddSource(CFRunLoopGetCurrent(), source, kCFRunLoopCommonModes)
        CGEventTapEnable(self._tap, self.enabled)
        return True

    def set_config(self, config):
        self._cancel()
        self.config = config
        self.tracker.step = config.step

    def set_enabled(self, enabled):
        self.enabled = enabled
        self._cancel()
        if self._tap is not None:
            CGEventTapEnable(self._tap, enabled)

    def _cancel(self):
        self.tracker.active = False
        self.overlay.end()

    def _perform(self, seq, action):
        if self.demo.visible:
            self.demo.action(seq, action.name)
        # An exception must not escape into the tap callback.
        try:
            action.run()
        except Exception:                                       # noqa: BLE001
            traceback.print_exc()

    def _callback(self, proxy, etype, event, refcon):
        if etype in (kCGEventTapDisabledByTimeout,
                     kCGEventTapDisabledByUserInput):
            if self.enabled:
                CGEventTapEnable(self._tap, True)
            return event
        if CGEventGetIntegerValueField(event, kCGEventSourceUserData) == MAGIC:
            return event

        tracker, overlay, demo = self.tracker, self.overlay, self.demo

        if etype == kCGEventScrollWheel:
            if not tracker.active and not demo.visible:
                return event
            delta = CGEventGetIntegerValueField(
                event, kCGScrollWheelEventDeltaAxis1)
            # Undo "natural scrolling" so WU always means the wheel
            # physically turned up.
            if delta and NSUserDefaults.standardUserDefaults().boolForKey_(
                    "com.apple.swipescrolldirection"):
                delta = -delta
            if delta and demo.visible:
                demo.wheel(delta > 0)
            if not tracker.active:
                return event
            # Wheel while the right button is held: the scroll never reaches
            # the app; instead each notch runs WU / WD, throttled so a
            # trackpad burst counts once.
            if delta:
                tracker.wheel_used = True
                now = time.monotonic()
                if now - tracker.last_wheel >= self.config.wheel_cooldown:
                    seq = "WU" if delta > 0 else "WD"
                    act = tracker.table.get(seq)
                    if act is not None:
                        tracker.last_wheel = now
                        self._perform(seq, act)
            return None

        if demo.visible:
            if etype == kCGEventRightMouseDown:
                demo.right(True)
            elif etype == kCGEventRightMouseUp:
                demo.right(False)

        loc = CGEventGetLocation(event)
        pos = (loc.x, loc.y)

        if etype == kCGEventRightMouseDown:
            bundle_id = frontmost_bundle_id()
            if bundle_id in self.config.passthrough:
                return event
            tracker.begin(pos, self.config.gestures_for(bundle_id))
            overlay.begin(pos)
            return None

        if not tracker.active:
            return event

        if etype == kCGEventRightMouseDragged:
            tracker.update(pos)
            overlay.update(pos, tracker.seq, tracker.table)
            return None

        if etype == kCGEventRightMouseUp:
            table = tracker.table
            wheel_used = tracker.wheel_used
            seq, dist = tracker.end(pos)
            overlay.end()
            if wheel_used:
                # The press was spent on wheel gestures; releasing it must
                # not also run a drag gesture or open the context menu.
                return None
            act = table.get(seq)
            if act is not None:
                self._perform(seq, act)
            elif not seq and dist < self.config.deadzone:
                post_right_click(pos)
                if demo.visible:
                    demo.action("", "Right Click")
            # An unrecognised gesture does nothing at all.
            return None

        return event
