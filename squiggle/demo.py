"""Demo mode: an on-screen mouse that mirrors the right button and the wheel.

For screen recordings. A small floating panel draws a mouse; its right button
lights up while the real one is held, the wheel lights up with an arrow when
it turns, and the action that ran is named underneath for a moment. Drag the
panel anywhere; macOS remembers the position.
"""

import time

from AppKit import (
    NSBackingStoreBuffered,
    NSBezierPath,
    NSColor,
    NSFont,
    NSFontAttributeName,
    NSForegroundColorAttributeName,
    NSGraphicsContext,
    NSPanel,
    NSScreen,
    NSStatusWindowLevel,
    NSView,
    NSWindowCollectionBehaviorCanJoinAllSpaces,
    NSWindowCollectionBehaviorFullScreenAuxiliary,
    NSWindowCollectionBehaviorIgnoresCycle,
    NSWindowCollectionBehaviorStationary,
    NSWindowStyleMaskBorderless,
    NSWindowStyleMaskNonactivatingPanel,
)
from Foundation import NSAttributedString

from .overlay import ARROWS

PANEL_SIZE = (190.0, 220.0)
MOUSE_RECT = ((55.0, 62.0), (80.0, 130.0))      # body, in view coordinates
BUTTON_HEIGHT = 56.0                            # buttons take the top of it
WHEEL_SIZE = (14.0, 32.0)

WHEEL_HOLD = 0.30       # seconds the wheel stays lit after the last notch
LABEL_HOLD = 1.60       # seconds the action name stays up

BACKDROP = (0.08, 0.08, 0.09, 0.80)
BODY = (0.93, 0.93, 0.95, 1.0)
OUTLINE = (0.0, 0.0, 0.0, 0.55)
WHEEL_IDLE = (0.62, 0.63, 0.67, 1.0)


def _color(rgba):
    return NSColor.colorWithCalibratedRed_green_blue_alpha_(*rgba)


class _DemoView(NSView):
    """Renderer only; all state lives on the DemoPanel."""

    def isOpaque(self):
        return False

    def mouseDownCanMoveWindow(self):
        return True

    def drawRect_(self, _dirty):
        controller = getattr(self, "controller", None)
        if controller is not None:
            controller.render()

    def expire_(self, _arg):
        controller = getattr(self, "controller", None)
        if controller is not None:
            controller.expire()


class DemoPanel:
    def __init__(self, accent=(0.28, 0.56, 1.00, 1.0)):
        self.window = None
        self.view = None
        self.visible = False
        self.accent = accent
        self._right_down = False
        self._wheel_up = True
        self._wheel_until = 0.0
        self._label = ""
        self._label_until = 0.0

    # -- window -------------------------------------------------------------

    def _ensure_window(self):
        if self.window is not None:
            return
        w, h = PANEL_SIZE
        screen = NSScreen.mainScreen()
        visible = screen.visibleFrame() if screen else ((0, 0), (1440, 900))
        origin = (visible[0][0] + visible[1][0] - w - 40.0,
                  visible[0][1] + 40.0)
        panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            (origin, PANEL_SIZE),
            NSWindowStyleMaskBorderless | NSWindowStyleMaskNonactivatingPanel,
            NSBackingStoreBuffered,
            False,
        )
        panel.setOpaque_(False)
        panel.setBackgroundColor_(NSColor.clearColor())
        panel.setLevel_(NSStatusWindowLevel)
        panel.setHasShadow_(False)
        panel.setHidesOnDeactivate_(False)
        panel.setReleasedWhenClosed_(False)
        panel.setMovableByWindowBackground_(True)
        panel.setCollectionBehavior_(
            NSWindowCollectionBehaviorCanJoinAllSpaces
            | NSWindowCollectionBehaviorStationary
            | NSWindowCollectionBehaviorIgnoresCycle
            | NSWindowCollectionBehaviorFullScreenAuxiliary
        )
        view = _DemoView.alloc().initWithFrame_(((0.0, 0.0), PANEL_SIZE))
        view.controller = self
        panel.setContentView_(view)
        # Restores the position from the last session, if there is one.
        panel.setFrameAutosaveName_("SquiggleDemoPanel")
        self.window, self.view = panel, view

    def set_visible(self, visible):
        self.visible = visible
        if visible:
            self._ensure_window()
            self._right_down = False
            self._wheel_until = self._label_until = 0.0
            self.view.setNeedsDisplay_(True)
            self.window.orderFrontRegardless()
        elif self.window is not None:
            self.window.orderOut_(None)

    # -- input, called from the event tap -----------------------------------

    def right(self, down):
        self._right_down = down
        self.view.setNeedsDisplay_(True)

    def wheel(self, up):
        self._wheel_up = up
        self._wheel_until = time.monotonic() + WHEEL_HOLD
        self._redraw_after(WHEEL_HOLD)

    def action(self, seq, name):
        arrows = "".join(ARROWS.get(c, c) for c in seq)
        self._label = ("%s  %s" % (arrows, name)).strip()
        self._label_until = time.monotonic() + LABEL_HOLD
        self._redraw_after(LABEL_HOLD)

    def _redraw_after(self, delay):
        self.view.setNeedsDisplay_(True)
        self.view.performSelector_withObject_afterDelay_(
            "expire:", None, delay + 0.02)

    def expire(self):
        if self.visible:
            self.view.setNeedsDisplay_(True)

    # -- drawing ------------------------------------------------------------

    def render(self):
        now = time.monotonic()
        (w, h) = PANEL_SIZE
        backdrop = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
            ((0.0, 0.0), (w, h)), 18.0, 18.0)
        _color(BACKDROP).set()
        backdrop.fill()

        (mx, my), (mw, mh) = MOUSE_RECT
        body = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
            MOUSE_RECT, mw / 2.0, mw / 2.0)
        _color(BODY).set()
        body.fill()

        split_y = my + mh - BUTTON_HEIGHT
        if self._right_down:
            NSGraphicsContext.saveGraphicsState()
            body.addClip()
            _color(self.accent).set()
            NSBezierPath.fillRect_(
                ((mx + mw / 2.0, split_y), (mw / 2.0, BUTTON_HEIGHT)))
            NSGraphicsContext.restoreGraphicsState()

        lines = NSBezierPath.bezierPath()
        lines.moveToPoint_((mx, split_y))
        lines.lineToPoint_((mx + mw, split_y))
        lines.moveToPoint_((mx + mw / 2.0, split_y))
        lines.lineToPoint_((mx + mw / 2.0, my + mh))
        lines.setLineWidth_(1.5)
        _color(OUTLINE).set()
        lines.stroke()
        body.setLineWidth_(1.5)
        body.stroke()

        wheel_lit = now < self._wheel_until
        ww, wh = WHEEL_SIZE
        wx = mx + (mw - ww) / 2.0
        wy = split_y + (BUTTON_HEIGHT - wh) / 2.0 + 4.0
        wheel = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
            ((wx, wy), (ww, wh)), ww / 2.0, ww / 2.0)
        _color(self.accent if wheel_lit else WHEEL_IDLE).set()
        wheel.fill()
        _color(OUTLINE).set()
        wheel.setLineWidth_(1.5)
        wheel.stroke()

        if wheel_lit:
            # Arrow beside the mouse, pointing the way the wheel turned.
            cx = mx + mw + 22.0
            cy = wy + wh / 2.0
            d = 9.0 if self._wheel_up else -9.0
            arrow = NSBezierPath.bezierPath()
            arrow.moveToPoint_((cx, cy - d))
            arrow.lineToPoint_((cx, cy + d))
            arrow.moveToPoint_((cx - 7.0, cy + d - (7.0 if d > 0 else -7.0)))
            arrow.lineToPoint_((cx, cy + d))
            arrow.lineToPoint_((cx + 7.0, cy + d - (7.0 if d > 0 else -7.0)))
            arrow.setLineWidth_(3.0)
            arrow.setLineCapStyle_(1)       # round
            arrow.setLineJoinStyle_(1)
            _color(self.accent).set()
            arrow.stroke()

        if self._label and now < self._label_until:
            text = NSAttributedString.alloc().initWithString_attributes_(
                self._label, {
                    NSFontAttributeName: NSFont.systemFontOfSize_(13.0),
                    NSForegroundColorAttributeName:
                        NSColor.colorWithCalibratedWhite_alpha_(1.0, 0.96),
                })
            size = text.size()
            text.drawAtPoint_(((w - size.width) / 2.0,
                               (my - size.height) / 2.0))
