"""Gesture recognition. Pure Python, no macOS imports."""


class Tracker:
    """Reduces the pointer path to a direction sequence such as 'DR'."""

    def __init__(self, step=25):
        self.step = step        # pixels of travel needed for one direction
        self.active = False
        self.origin = (0.0, 0.0)
        self.anchor = (0.0, 0.0)
        self.seq = ""
        self.table = {}
        self.wheel_used = False
        self.last_wheel = 0.0

    def begin(self, pos, table):
        self.active = True
        self.origin = pos
        self.anchor = pos
        self.seq = ""
        self.table = table
        self.wheel_used = False
        self.last_wheel = 0.0

    def update(self, pos):
        dx = pos[0] - self.anchor[0]
        dy = pos[1] - self.anchor[1]
        if abs(dx) < self.step and abs(dy) < self.step:
            return
        if abs(dx) >= abs(dy):
            d = "R" if dx > 0 else "L"
        else:
            d = "D" if dy > 0 else "U"      # screen y grows downwards
        if not self.seq or self.seq[-1] != d:
            self.seq += d
        self.anchor = pos

    def end(self, pos):
        """(sequence, distance from the press point)."""
        self.active = False
        dist = max(abs(pos[0] - self.origin[0]), abs(pos[1] - self.origin[1]))
        return self.seq, dist
