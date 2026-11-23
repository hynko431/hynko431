"""Unit tests for scripts.build_static."""

from __future__ import annotations

import pathlib
import re
import shutil
import tempfile
import unittest

from scripts import build_static
from scripts.profile_core import load_profile, validate_svg_document

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


class TestBuildStatic(unittest.TestCase):
    def setUp(self) -> None:
        self.profile = load_profile(REPO_ROOT / "profile.json")

    def test_deterministic_lf_readme_and_layer1_assertions(self) -> None:
        base = self.profile["dynamic_assets_base"]
        r1 = build_static.render_readme(self.profile, base)
        r2 = build_static.render_readme(self.profile, base)
        self.assertEqual(r1, r2)
        self.assertNotIn("\r\n", r1)

        # Disallowed headings and legacy widgets/links
        self.assertNotIn("<h1", r1.lower())
        self.assertIsNone(re.search(r"(?m)^# ", r1))
        self.assertNotIn("hynko431githubstats.vercel.app", r1)
        self.assertNotIn("herokuapp.com", r1)
        self.assertNotIn("instagram.com", r1)
        self.assertNotIn("auto-updated daily", r1.lower())

        # Every <picture> declares dark + light <source> and light fallback <img src>
        pictures = re.findall(r"<picture>.*?</picture>", r1, flags=re.DOTALL)
        self.assertGreaterEqual(len(pictures), 13)
        for pic in pictures:
            self.assertIn('(prefers-color-scheme: dark)', pic)
            light_m = re.search(r'media="\(prefers-color-scheme: light\)" srcset="([^"]+)"', pic)
            img_m = re.search(r'<img [^>]*src="([^"]+)"', pic)
            self.assertIsNotNone(light_m)
            self.assertIsNotNone(img_m)
            self.assertEqual(light_m.group(1), img_m.group(1))

        # Separate single-destination links and Explorer deep links
        self.assertIn('https://coldpin-docs.pages.dev/', r1)
        self.assertIn('https://agent-a-thon.vercel.app/', r1)
        explorer = self.profile["explorer_url"]
        self.assertIn(f"{explorer}#projects", r1)
        self.assertIn(f"{explorer}#stack", r1)
        self.assertIn(f"{explorer}#skyline", r1)

        # 2-column bespoke SVG bento project cards and zero repeated plain-text stack table
        for proj in self.profile["projects"]:
            self.assertIn(f'./assets/cards/{proj["slug"]}-dark.svg', r1)
            self.assertIn(f'./assets/cards/{proj["slug"]}-light.svg', r1)
        self.assertNotIn("<details>", r1)
        self.assertNotIn("Plain-text stack index", r1)

        # Searchable plain text keywords in Experience, Education, Summary, and links
        for kw in (
            "FastAPI",
            "PostgreSQL",
            "Redis",
            "Celery",
            "Docker",
            "Rust",
            "LangChain",
            "FAISS",
            "Coldpin",
            "Saral Vidhya",
            "ASAR IT Technologies",
            "SmartBridge",
            "JNTUA",
        ):
            self.assertIn(kw, r1, f"Missing Ctrl+F keyword: {kw}")

    def test_all_34_static_svgs_valid(self) -> None:
        for rel in build_static.STATIC_ICON_FILES:
            p = REPO_ROOT / rel
            self.assertTrue(p.exists(), f"Missing icon: {rel}")
            self.assertEqual(validate_svg_document(p.read_text(encoding="utf-8"), rel), [])
        for mode in ("dark", "light"):
            svg = build_static.render_stack_svg(self.profile, mode)
            self.assertEqual(validate_svg_document(svg, f"stack-3d-{mode}.svg"), [])
            self.assertNotIn("\r\n", svg)
            self.assertIn("3D ISOMETRIC STACK ARCHITECTURE", svg)
            for tier_tag in ("L01", "L02", "L03", "L04"):
                self.assertIn(tier_tag, svg)
        for proj in self.profile["projects"]:
            for mode in ("dark", "light"):
                card_path = REPO_ROOT / "assets" / "cards" / f'{proj["slug"]}-{mode}.svg'
                self.assertTrue(card_path.exists(), f"Missing generated card: {card_path}")
                card_svg = card_path.read_text(encoding="utf-8")
                self.assertEqual(validate_svg_document(card_svg, card_path.name), [])
                self.assertNotIn("\r\n", card_svg)

    def test_check_mode_detects_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = pathlib.Path(tmpdir)
            shutil.copy2(REPO_ROOT / "profile.json", tmp / "profile.json")
            shutil.copytree(REPO_ROOT / "assets" / "icons", tmp / "assets" / "icons")

            rc_build = build_static.main(["--repo-root", str(tmp)])
            self.assertEqual(rc_build, 0)
            rc_ok = build_static.main(["--repo-root", str(tmp), "--check"])
            self.assertEqual(rc_ok, 0)

            # Mutate README.md -> --check must fail non-zero
            readme_p = tmp / "README.md"
            readme_p.write_text(readme_p.read_text(encoding="utf-8") + "\ndrift\n", encoding="utf-8")
            rc_fail = build_static.main(["--repo-root", str(tmp), "--check"])
            self.assertNotEqual(rc_fail, 0)


if __name__ == "__main__":
    unittest.main()
