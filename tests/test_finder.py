import unittest

from squiggle import finder


class PathTest(unittest.TestCase):
    def test_parent_dir(self):
        self.assertEqual(finder.parent_dir("/a/b/c/"), "/a/b/")
        self.assertEqual(finder.parent_dir("/a/"), "/")
        self.assertEqual(finder.parent_dir("/"), "")

    def test_norm_dir(self):
        self.assertEqual(finder.norm_dir("/a"), "/a/")
        self.assertEqual(finder.norm_dir("/a/"), "/a/")


class ForwardStackTest(unittest.TestCase):
    def setUp(self):
        finder._forward_stacks.clear()

    def test_back_twice_forward_twice(self):
        finder.push_forward(1, "/a/b/c/")
        finder.push_forward(1, "/a/b/")
        self.assertEqual(finder.pop_forward(1, "/a/"), "/a/b/")
        self.assertEqual(finder.pop_forward(1, "/a/b/"), "/a/b/c/")
        self.assertIsNone(finder.pop_forward(1, "/a/b/c/"))

    def test_navigating_away_drops_the_record(self):
        finder.push_forward(1, "/a/b/")
        self.assertIsNone(finder.pop_forward(1, "/x/"))
        self.assertIsNone(finder.pop_forward(1, "/a/"))

    def test_windows_are_independent(self):
        finder.push_forward(1, "/a/b/")
        self.assertIsNone(finder.pop_forward(2, "/a/"))
        self.assertEqual(finder.pop_forward(1, "/a/"), "/a/b/")


if __name__ == "__main__":
    unittest.main()
