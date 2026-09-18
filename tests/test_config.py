import os
import tempfile
import unittest

from squiggle import config
from squiggle.events import KEYCODES, MODIFIERS, parse_keys


def load_text(text):
    with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False) as f:
        f.write(text)
    try:
        return config.load(f.name)
    finally:
        os.unlink(f.name)


class ParseKeysTest(unittest.TestCase):
    def test_plain_key(self):
        self.assertEqual(parse_keys("home"), (KEYCODES["home"], 0))

    def test_modifiers(self):
        self.assertEqual(
            parse_keys("Cmd+Shift+["),
            (KEYCODES["["], MODIFIERS["cmd"] | MODIFIERS["shift"]))

    def test_unknown(self):
        with self.assertRaises(ValueError):
            parse_keys("cmd+nope")
        with self.assertRaises(ValueError):
            parse_keys("hyper+a")


class ConfigTest(unittest.TestCase):
    def test_defaults_load(self):
        cfg = config.load(os.devnull)
        self.assertEqual(cfg.gestures["L"].name, "Back")
        self.assertIn("WU", cfg.gestures)
        self.assertIn("com.apple.finder", cfg.apps)

    def test_app_override_and_disable(self):
        cfg = load_text('''
            [gestures]
            L = { name = "Back", keys = "cmd+[" }
            DR = { name = "Close", keys = "cmd+w" }
            [apps."com.example"]
            DR = false
            L = { name = "Other", shell = "true" }
        ''')
        table = cfg.gestures_for("com.example")
        self.assertNotIn("DR", table)
        self.assertEqual(table["L"].name, "Other")
        self.assertEqual(cfg.gestures_for("com.unknown")["DR"].name, "Close")

    def test_settings_merge_with_defaults(self):
        cfg = load_text("[settings]\nstep = 40\n")
        self.assertEqual(cfg.step, 40)
        self.assertEqual(cfg.deadzone, 8)
        self.assertIn("L", cfg.gestures)

    def test_errors(self):
        bad = [
            "[gestures]\nLL = { keys = \"cmd+w\" }",
            "[gestures]\nX = { keys = \"cmd+w\" }",
            "[gestures]\nL = { keys = \"cmd+w\", shell = \"true\" }",
            "[gestures]\nL = { name = \"nothing\" }",
            "[gestures]\nL = { keys = \"cmd+nope\" }",
            "[gestures]\nL = { action = \"nope\" }",
            "[gestures]\nL = false",
            "[settings]\nstep = 0",
            "[settings]\nsteps = 3",
            "[settings]\ntrail_color = [1, 2, 3]",
            "passthrough = \"com.example\"",
            "[typo]\nx = 1",
            "not toml at all =",
        ]
        for text in bad:
            with self.subTest(text=text), self.assertRaises(config.ConfigError):
                load_text(text)


if __name__ == "__main__":
    unittest.main()
