"""Trail overlay: a full-screen transparent click-through panel."""

from AppKit import (
    NSBackingStoreBuffered,
    NSBezierPath,
    NSColor,
    NSFont,
    NSFontAttributeName,
    NSForegroundColorAttributeName,
    NSLineCapStyleRound,
    NSLineJoinStyleRound,
    NSPanel,
    NSScreen,
    NSScreenSaverWindowLevel,
    NSView,
    NSWindowCollectionBehaviorCanJoinAllSpaces,
    NSWindowCollectionBehaviorFullScreenAuxiliary,
    NSWindowCollectionBehaviorIgnoresCycle,
    NSWindowCollectionBehaviorStationary,
    NSWindowStyleMaskBorderless,
    NSWindowStyleMaskNonactivatingPanel,
)
from Foundation import NSAttributedString

# Deliberately understated so it never competes with content.
TRAIL_WIDTH = 3.0
TRAIL_HALO = (0.0, 0.0, 0.0, 0.16)   # faint outer stroke, keeps the line
                                     # readable on light backgrounds
LABEL_FONT_SIZE = 12.0
LABEL_BG = (0.08, 0.08, 0.09, 0.80)
LABEL_PAD = (9.0, 5.0)               # text inset inside the bubble (x, y)
LABEL_OFFSET = (16.0, -26.0)         # bubble position relative to the cursor
LABEL_RADIUS = 6.0
MAX_TRAIL_POINTS = 2000

ARROWS = {"L": "←", "R": "→", "U": "↑", "D": "↓", "W": "⊙"}


def _screen_geometry():
    """(union of all screen frames, height of the primary screen), Cocoa."""
    screens = list(NSScreen.screens() or [])
    if not screens:
        return ((0.0, 0.0), (1440.0, 900.0)), 900.0
    frames = [s.frame() for s in screens]
    primary_h = frames[0].size.height
    x0 = min(f.origin.x for f in frames)
    y0 = min(f.origin.y for f in frames)
    x1 = max(f.origin.x + f.size.width for f in frames)
    y1 = max(f.origin.y + f.size.height for f in frames)
    return ((x0, y0), (x1 - x0, y1 - y0)), primary_h


def _rect_union(a, b):
    if a is None:
        return b
    if b is None:
        return a
    x0 = min(a[0][0], b[0][0])
    y0 = min(a[0][1], b[0][1])
    x1 = max(a[0][0] + a[1][0], b[0][0] + b[1][0])
    y1 = max(a[0][1] + a[1][1], b[0][1] + b[1][1])
    return ((x0, y0), (x1 - x0, y1 - y0))


def _inset(rect, d):
    (x, y), (w, h) = rect
    return ((x - d, y - d), (w + 2 * d, h + 2 * d))


def _point_rect(pt):
    return ((pt[0], pt[1]), (0.0, 0.0))


class _TrailView(NSView):
    """Renderer only; all state lives on the Overlay."""

    def isOpaque(self):
        return False

    def drawRect_(self, _dirty):
        controller = getattr(self, "controller", None)
        if controller is not None:
            controller.render()


class Overlay:
    """Full-screen transparent click-through panel showing the gesture."""

    def __init__(self, enabled=True, deadzone=8,
                 color=(0.28, 0.56, 1.00, 0.88)):
        self.window = None
        self.view = None
        self.enabled = enabled
        self.deadzone = deadzone    # stay hidden until travel exceeds this
        self.color = color
        self.points = []
        self.shown = False
        self._label = ""
        self._matched = False
        self._label_rect = None
        self._screen_rect = None
        self._org = (0.0, 0.0)
        self._flip = 0.0
        self._font = None

    def _ensure_window(self):
        if self.window is not None:
            return
        frame, _ = _screen_geometry()
        panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            frame,
            NSWindowStyleMaskBorderless | NSWindowStyleMaskNonactivatingPanel,
            NSBackingStoreBuffered,
            False,
        )
        panel.setOpaque_(False)
        panel.setBackgroundColor_(NSColor.clearColor())
        panel.setLevel_(NSScreenSaverWindowLevel)
        panel.setIgnoresMouseEvents_(True)
        panel.setHasShadow_(False)
        panel.setHidesOnDeactivate_(False)
        panel.setReleasedWhenClosed_(False)
        panel.setCollectionBehavior_(
            NSWindowCollectionBehaviorCanJoinAllSpaces
            | NSWindowCollectionBehaviorStationary
            | NSWindowCollectionBehaviorIgnoresCycle
            | NSWindowCollectionBehaviorFullScreenAuxiliary
        )
        view = _TrailView.alloc().initWithFrame_(((0.0, 0.0), frame[1]))
        view.controller = self
        panel.setContentView_(view)
        self.window, self.view = panel, view

    def prepare(self):
        """Build the panel up front so the first gesture is not delayed."""
        if self.enabled:
            self._ensure_window()

    def begin(self, pos):
        if not self.enabled:
            return
        self._ensure_window()
        frame, primary_h = _screen_geometry()
        self._org = (frame[0][0], frame[0][1])
        self._flip = primary_h
        if tuple(map(tuple, self.window.frame())) != tuple(map(tuple, frame)):
            self.window.setFrame_display_(frame, False)
            self.view.setFrameSize_(frame[1])
        self.points = [self._to_view(pos)]
        self._screen_rect = self._screen_rect_for(pos)
        self._label = ""
        self._matched = False
        self._label_rect = None
        self.shown = False

    def update(self, pos, seq, table):
        if not self.enabled or self.window is None:
            return
        pt = self._to_view(pos)
        prev = self.points[-1] if self.points else pt
        if self.points and abs(pt[0] - prev[0]) < 2.0 and abs(pt[1] - prev[1]) < 2.0:
            return
        if len(self.points) < MAX_TRAIL_POINTS:
            self.points.append(pt)
        else:
            self.points[-1] = pt

        if not self.shown:
            start = self.points[0]
            if max(abs(pt[0] - start[0]), abs(pt[1] - start[1])) < self.deadzone:
                return
            self.shown = True
            self.view.setNeedsDisplay_(True)
            self.window.orderFrontRegardless()

        dirty = _inset(_rect_union(_point_rect(prev), _point_rect(pt)),
                       TRAIL_WIDTH + 2.0)
        dirty = _rect_union(dirty, self._label_rect)
        self._set_label(seq, table, pt)
        dirty = _rect_union(dirty, self._label_rect)
        self.view.setNeedsDisplayInRect_(dirty)

    def end(self):
        self.points = []
        self._label = ""
        self._label_rect = None
        self.shown = False
        if self.window is not None:
            self.window.orderOut_(None)

    def _to_view(self, pos):
        """Global CG point (origin top left, y down) to view coordinates."""
        return (pos[0] - self._org[0], self._flip - pos[1] - self._org[1])

    def _screen_rect_for(self, pos):
        x, y = self._to_view(pos)
        for screen in (NSScreen.screens() or []):
            f = screen.frame()
            sx = f.origin.x - self._org[0]
            sy = f.origin.y - self._org[1]
            if sx <= x <= sx + f.size.width and sy <= y <= sy + f.size.height:
                return ((sx, sy), (f.size.width, f.size.height))
        return ((0.0, 0.0), tuple(self.view.frame()[1]))

    def _set_label(self, seq, table, pt):
        if not seq:
            self._label, self._matched, self._label_rect = "", False, None
            return
        arrows = "".join(ARROWS.get(c, c) for c in seq)
        act = table.get(seq)
        self._matched = act is not None
        self._label = "%s  %s" % (arrows, act.name) if act else arrows

        size = self._attributed(self._label, self._matched).size()
        w = size.width + 2 * LABEL_PAD[0]
        h = size.height + 2 * LABEL_PAD[1]
        x = pt[0] + LABEL_OFFSET[0]
        y = pt[1] + LABEL_OFFSET[1] - h
        if self._screen_rect:
            (sx, sy), (sw, sh) = self._screen_rect
            x = min(max(x, sx + 8.0), sx + sw - w - 8.0)
            y = min(max(y, sy + 8.0), sy + sh - h - 8.0)
        self._label_rect = ((round(x), round(y)), (round(w), round(h)))

    def _attributed(self, text, matched):
        if self._font is None:
            self._font = NSFont.systemFontOfSize_(LABEL_FONT_SIZE)
        attrs = {
            NSFontAttributeName: self._font,
            NSForegroundColorAttributeName:
                NSColor.colorWithCalibratedWhite_alpha_(
                    1.0, 0.96 if matched else 0.62),
        }
        return NSAttributedString.alloc().initWithString_attributes_(text, attrs)

    def render(self):
        if not self.shown:
            return
        if len(self.points) > 1:
            path = NSBezierPath.bezierPath()
            path.setLineJoinStyle_(NSLineJoinStyleRound)
            path.setLineCapStyle_(NSLineCapStyleRound)
            path.moveToPoint_(self.points[0])
            for pt in self.points[1:]:
                path.lineToPoint_(pt)

            path.setLineWidth_(TRAIL_WIDTH + 2.0)
            NSColor.colorWithCalibratedRed_green_blue_alpha_(*TRAIL_HALO).set()
            path.stroke()

            path.setLineWidth_(TRAIL_WIDTH)
            NSColor.colorWithCalibratedRed_green_blue_alpha_(*self.color).set()
            path.stroke()

        if self._label and self._label_rect is not None:
            bubble = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
                self._label_rect, LABEL_RADIUS, LABEL_RADIUS)
            NSColor.colorWithCalibratedRed_green_blue_alpha_(*LABEL_BG).set()
            bubble.fill()
            (x, y), _ = self._label_rect
            self._attributed(self._label, self._matched).drawAtPoint_(
                (x + LABEL_PAD[0], y + LABEL_PAD[1]))
