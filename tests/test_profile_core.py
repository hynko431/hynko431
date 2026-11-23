"""Unit tests for scripts.profile_core."""

from __future__ import annotations

import copy
import datetime as dt
import json
import pathlib
import tempfile
import unittest

from scripts.profile_core import (
    DIWALI_DATES,
    IST,
    get_theme_palette,
    load_profile,
    resolve_active_theme,
    validate_all_palettes_wcag,
    validate_svg_document,
    xml_attr,
    xml_escape,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


class TestProfileCore(unittest.TestCase):
    def test_load_profile_happy_path(self) -> None:
        profile = load_profile(REPO_ROOT / "profile.json")
        self.assertEqual(profile["handle"], "hynko431")
        self.assertEqual(len(profile["projects"]), 6)
        self.assertEqual(profile["education"]["degree"], "B.Tech in Computer Science & Engineering")
        self.assertEqual(profile["education"]["period"], "2022 – 2026")
        all_highlights = [
            h
            for exp in profile["experience"]
            for role in exp["roles"]
            for h in role["highlights"]
        ]
        joined = "\n".join(all_highlights)
        self.assertIn("90%", joined)
        self.assertIn("EXT-APSCHE_AIML-50038", joined)

    def _write_mutated_profile(self, mutator) -> pathlib.Path:
        data = json.loads((REPO_ROOT / "profile.json").read_text(encoding="utf-8"))
        mutator(data)
        tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
        json.dump(data, tmp)
        tmp.close()
        p = pathlib.Path(tmp.name)
        self.addCleanup(p.unlink, missing_ok=True)
        return p

    def test_load_profile_rejects_invalid_repo_slug(self) -> None:
        p = self._write_mutated_profile(lambda d: d["projects"][0].update({"repo": "bad/slug"}))
        with self.assertRaises(ValueError):
            load_profile(p)

    def test_load_profile_rejects_javascript_url(self) -> None:
        p = self._write_mutated_profile(
            lambda d: d["projects"][0]["links"].update({"docs": "javascript:alert(1)"})
        )
        with self.assertRaises(ValueError):
            load_profile(p)

    def test_load_profile_rejects_mailto_outside_contact(self) -> None:
        p = self._write_mutated_profile(
            lambda d: d["projects"][0]["links"].update({"code": "mailto:test@example.com"})
        )
        with self.assertRaises(ValueError):
            load_profile(p)

    def test_load_profile_rejects_unknown_tier_id(self) -> None:
        p = self._write_mutated_profile(lambda d: d["projects"][0].update({"tier_ids": ["nonexistent"]}))
        with self.assertRaises(ValueError):
            load_profile(p)

    def test_load_profile_rejects_overlong_hero_subtitle(self) -> None:
        p = self._write_mutated_profile(
            lambda d: d["hero_subtitle_lines"].__setitem__(0, "x" * 65)
        )
        with self.assertRaises(ValueError):
            load_profile(p)

    def test_seasonal_precedence_and_boundaries(self) -> None:
        self.assertEqual(IST.utcoffset(None), dt.timedelta(hours=5, minutes=30))
        self.assertEqual(len(DIWALI_DATES), 10)

        # 2026 Diwali (Nov 8): Nov 7..9
        self.assertEqual(resolve_active_theme(dt.date(2026, 11, 6)), "baseline")
        self.assertEqual(resolve_active_theme(dt.date(2026, 11, 7)), "diwali")
        self.assertEqual(resolve_active_theme(dt.date(2026, 11, 8)), "diwali")
        self.assertEqual(resolve_active_theme(dt.date(2026, 11, 9)), "diwali")
        self.assertEqual(resolve_active_theme(dt.date(2026, 11, 10)), "baseline")

        # Diwali > Halloween collisions (2027-10-29 -> Oct 28..30; 2035-10-30 -> Oct 29..31)
        self.assertEqual(resolve_active_theme(dt.date(2027, 10, 30)), "diwali")
        self.assertEqual(resolve_active_theme(dt.date(2027, 10, 31)), "halloween")
        self.assertEqual(resolve_active_theme(dt.date(2035, 10, 30)), "diwali")
        self.assertEqual(resolve_active_theme(dt.date(2035, 10, 31)), "diwali")

        # Fixed windows & post-2035 fallback
        self.assertEqual(resolve_active_theme(dt.date(2026, 12, 31)), "new_year")
        self.assertEqual(resolve_active_theme(dt.date(2027, 1, 1)), "new_year")
        self.assertEqual(resolve_active_theme(dt.date(2027, 1, 2)), "new_year")
        self.assertEqual(resolve_active_theme(dt.date(2027, 1, 3)), "baseline")
        self.assertEqual(resolve_active_theme(dt.date(2026, 12, 24)), "christmas")
        self.assertEqual(resolve_active_theme(dt.date(2026, 12, 25)), "christmas")
        self.assertEqual(resolve_active_theme(dt.date(2026, 12, 26)), "christmas")
        self.assertEqual(resolve_active_theme(dt.date(2026, 10, 30)), "halloween")
        self.assertEqual(resolve_active_theme(dt.date(2026, 10, 31)), "halloween")
        self.assertEqual(resolve_active_theme(dt.date(2026, 6, 15)), "baseline")
        self.assertEqual(resolve_active_theme(dt.date(2036, 11, 15)), "baseline")

    def test_wcag_aa_all_palettes_pass(self) -> None:
        self.assertEqual(validate_all_palettes_wcag(), [])
        pal = get_theme_palette("diwali", "dark")
        self.assertEqual(sorted(pal["levels"].keys()), ["0", "1", "2", "3", "4"])

    def test_validate_svg_document_rejects_defects(self) -> None:
        valid = (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10" role="img">'
            "<title>T</title><desc>D</desc></svg>"
        )
        self.assertEqual(validate_svg_document(valid, "ok.svg"), [])
        self.assertTrue(validate_svg_document("<svg><broken", "bad.svg"))
        self.assertTrue(validate_svg_document(valid.replace("</svg>", '<rect fill="rgba(0,0,0,0.5)"/></svg>'), "rgba.svg"))
        self.assertTrue(validate_svg_document(valid.replace("</svg>", "<feGaussianBlur/></svg>"), "blur.svg"))
        self.assertTrue(validate_svg_document('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10" role="img"><title>T</title></svg>', "nodesc.svg"))

    def test_xml_escape_and_attr(self) -> None:
        self.assertEqual(xml_escape("AI & ML Intern"), "AI &amp; ML Intern")
        self.assertEqual(
            xml_escape('''a & b < c > d "e" 'f' '''),
            "a &amp; b &lt; c &gt; d &quot;e&quot; &apos;f&apos; ",
        )
        self.assertEqual(
            xml_attr('''AI & "ML" 'Intern' <1>'''),
            '"AI &amp; &quot;ML&quot; &apos;Intern&apos; &lt;1&gt;"',
        )


if __name__ == "__main__":
    unittest.main()
