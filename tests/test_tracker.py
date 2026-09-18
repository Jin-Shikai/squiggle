import unittest

from squiggle.tracker import Tracker


def draw(points, step=25):
    t = Tracker(step)
    t.begin(points[0], {})
    for p in points[1:]:
        t.update(p)
    return t.end(points[-1])


class TrackerTest(unittest.TestCase):
    def test_click_has_no_sequence(self):
        seq, dist = draw([(100, 100), (103, 98)])
        self.assertEqual(seq, "")
        self.assertEqual(dist, 3)

    def test_single_direction(self):
        self.assertEqual(draw([(0, 0), (-30, 2)])[0], "L")
        self.assertEqual(draw([(0, 0), (2, -30)])[0], "U")

    def test_repeated_direction_collapses(self):
        self.assertEqual(draw([(0, 0), (30, 0), (60, 0), (90, 5)])[0], "R")

    def test_down_then_right(self):
        self.assertEqual(draw([(0, 0), (0, 30), (0, 60), (30, 60)])[0], "DR")

    def test_up_then_down(self):
        self.assertEqual(draw([(0, 0), (0, -40), (0, 0)])[0], "UD")

    def test_step_is_configurable(self):
        self.assertEqual(draw([(0, 0), (30, 0)], step=50)[0], "")


if __name__ == "__main__":
    unittest.main()
