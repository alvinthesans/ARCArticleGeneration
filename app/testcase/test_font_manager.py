"""
python -m unittest discover -s app/testcase -p test_font_manager.py -v
"""

import sys
import unittest
from pathlib import Path

from PyQt6.QtGui import QGuiApplication
from app.typographyEngine.FontManager import FontManager


FONT_DIR = (Path(__file__).resolve().parents[1] / "typographyEngine" / "custom_fonts")

class FontManagerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication(sys.argv)
        cls.manager = FontManager(FONT_DIR)
        cls.fonts = cls.manager.register_directory()
        if not cls.fonts:
            raise AssertionError(f"No fonts found in {FONT_DIR}")
        cls.record = cls.fonts[12]

    def test_metadata(self):
        info = self.manager.inspect_font(self.record.path)
        self.assertTrue(info.family)
        self.assertGreater(info.unicode_codepoint_count, 0)

    def test_register_is_idempotent(self):
        again = self.manager.register_font(self.record.path)
        self.assertEqual(again.font_id, self.record.font_id)

    def test_coverage(self):
        self.assertTrue(self.manager.supports_text(self.record.font_id, ""))
        self.assertTrue(self.manager.supports_text(self.record.font_id, "\n"))
        self.assertFalse(self.manager.supports_text(self.record.font_id, "\U0010ffff"))
        print("Traditional Chinese missing characters:",
              self.manager.missing_characters(self.record.font_id, "自然的呼吸"))

    def test_qfont(self):
        family = self.record.families[0]
        font = self.manager.resolve_font(
            family=family, weight=700, pixel_size=72, language="zh-HK"
        )
        self.assertEqual(font.family(), family)
        self.assertEqual(font.pixelSize(), 72)

    def test_missing_family(self):
        with self.assertRaises(ValueError):
            self.manager.resolve_font("ARC_NONEXISTENT_FONT_123456")


if __name__ == "__main__":
    unittest.main()
