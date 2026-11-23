"""Unit tests for GraphQL telemetry ingestion, Hero/Skyline SVGs, dist/ packaging, and Camo purger."""

from __future__ import annotations

import datetime as dt
import io
import json
import pathlib
import re
import tempfile
import unittest
import urllib.error
from unittest import mock

from scripts import generate_3d_contrib, purge_camo
from scripts.profile_core import THEME_NAMES, load_profile, validate_svg_document
from scripts.render_hero import render_hero_svg

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "sample_graphql.json"


def _make_graphql_payload(num_days: int, *, start_date: dt.date = dt.date(2025, 11, 23)) -> dict:
    """Build a synthetic GitHub GraphQL calendar + 6-repo response."""
    weeks: list[dict] = []
    cur_week: list[dict] = []
    for i in range(num_days):
        d = start_date + dt.timedelta(days=i)
        dow = (d.weekday() + 1) % 7  # Sunday=0 .. Saturday=6
        if dow == 0 and cur_week:
            weeks.append({"contributionDays": cur_week})
            cur_week = []
        cnt = (i * 3) % 19
        lvl = (
            "NONE"
            if cnt == 0
            else "FIRST_QUARTILE"
            if cnt < 4
            else "SECOND_QUARTILE"
            if cnt < 9
            else "THIRD_QUARTILE"
            if cnt < 15
            else "FOURTH_QUARTILE"
        )
        cur_week.append(
            {
                "date": d.isoformat(),
                "contributionCount": cnt,
                "contributionLevel": lvl,
                "weekday": dow,
            }
        )
    if cur_week:
        weeks.append({"contributionDays": cur_week})

    data: dict = {
        "user": {
            "contributionsCollection": {
                "contributionCalendar": {
                    "weeks": weeks,
                }
            }
        }
    }
    stars_list = [0, 1, 4, 5, 12, 2]
    langs = ["TypeScript", "Rust", "JavaScript", "TypeScript", "Python", None]
    for idx in range(6):
        data[f"repo_{idx}"] = {
            "stargazerCount": stars_list[idx],
            "pushedAt": "2026-11-20T12:00:00Z",
            "primaryLanguage": {"name": langs[idx]} if langs[idx] is not None else None,
        }
    return {"data": data}


class _FakeHTTPResponse:
    def __init__(self, body: str, status: int = 200) -> None:
        self._body = body.encode("utf-8")
        self.status = status

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "_FakeHTTPResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class TestTelemetryAndSvgs(unittest.TestCase):
    def setUp(self) -> None:
        self.profile = load_profile(REPO_ROOT / "profile.json")
        self.repo_slugs = [p["repo"] for p in self.profile["projects"]]

    def test_ist_window_span_under_one_year(self) -> None:
        from_iso, to_iso = generate_3d_contrib.compute_ist_window_utc(dt.date(2026, 11, 23))
        from_dt = dt.datetime.fromisoformat(from_iso.replace("Z", "+00:00"))
        to_dt = dt.datetime.fromisoformat(to_iso.replace("Z", "+00:00"))
        self.assertEqual(to_dt - from_dt, dt.timedelta(days=364, hours=23, minutes=59, seconds=59))

    def test_calendar_bounds_and_fatal_errors(self) -> None:
        for n in (365, 366, 371, 372):
            parsed = generate_3d_contrib.parse_graphql_payload(_make_graphql_payload(n), self.repo_slugs)
            self.assertEqual(len(parsed["days"]), n)

        for bad_n in (364, 373):
            with self.assertRaises(RuntimeError):
                generate_3d_contrib.parse_graphql_payload(_make_graphql_payload(bad_n), self.repo_slugs)

        neg_payload = _make_graphql_payload(366)
        neg_payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"][0]["contributionDays"][0]["contributionCount"] = -1
        with self.assertRaises(RuntimeError):
            generate_3d_contrib.parse_graphql_payload(neg_payload, self.repo_slugs)

        user_err = _make_graphql_payload(366)
        user_err["errors"] = [{"path": ["user", "contributionsCollection"], "message": "Forbidden"}]
        with self.assertRaises(RuntimeError):
            generate_3d_contrib.parse_graphql_payload(user_err, self.repo_slugs)

        missing_path_err = _make_graphql_payload(366)
        missing_path_err["errors"] = [{"message": "Internal error"}]
        with self.assertRaises(RuntimeError):
            generate_3d_contrib.parse_graphql_payload(missing_path_err, self.repo_slugs)

    def test_partial_repo_error_null_language_and_star_threshold(self) -> None:
        payload = _make_graphql_payload(366)
        payload["errors"] = [{"path": ["repo_1"], "message": "Could not resolve to a Repository"}]
        payload["data"]["repo_1"] = None
        parsed = generate_3d_contrib.parse_graphql_payload(payload, self.repo_slugs)

        repos = parsed["repositories"]
        self.assertEqual(repos[self.repo_slugs[1]], {"stars": 0, "display_stars": False, "primary_language": None, "pushed_at": None})
        self.assertFalse(repos[self.repo_slugs[0]]["display_stars"])  # 0 stars
        self.assertFalse(repos[self.repo_slugs[2]]["display_stars"])  # 4 stars
        self.assertTrue(repos[self.repo_slugs[3]]["display_stars"])   # 5 stars
        self.assertTrue(repos[self.repo_slugs[4]]["display_stars"])   # 12 stars
        self.assertIsNone(repos[self.repo_slugs[5]]["primary_language"])

    def test_retry_backoff_and_fail_fast_401(self) -> None:
        ok_body = json.dumps(_make_graphql_payload(366))
        err_429 = urllib.error.HTTPError("https://api.github.com/graphql", 429, "Too Many Requests", {}, io.BytesIO(b""))
        err_502 = urllib.error.HTTPError("https://api.github.com/graphql", 502, "Bad Gateway", {}, io.BytesIO(b""))
        sleeps: list[float] = []

        with mock.patch("urllib.request.urlopen", side_effect=[err_429, err_502, _FakeHTTPResponse(ok_body)]):
            parsed = generate_3d_contrib.fetch_telemetry(
                "hynko431",
                self.repo_slugs,
                "ghp_fake",
                dt.date(2026, 11, 23),
                sleep_fn=sleeps.append,
            )
        self.assertEqual(sleeps, [1, 3])
        self.assertEqual(len(parsed["days"]), 366)

        sleeps_401: list[float] = []
        err_401 = urllib.error.HTTPError("https://api.github.com/graphql", 401, "Unauthorized", {}, io.BytesIO(b""))
        with mock.patch("urllib.request.urlopen", side_effect=[err_401]):
            with self.assertRaises(RuntimeError) as ctx:
                generate_3d_contrib.fetch_telemetry(
                    "hynko431",
                    self.repo_slugs,
                    "ghp_bad",
                    dt.date(2026, 11, 23),
                    sleep_fn=sleeps_401.append,
                )
        self.assertEqual(sleeps_401, [])
        self.assertIn("401", str(ctx.exception))
        self.assertIn("GH_PROFILE_READ_TOKEN", str(ctx.exception))

    def _assert_all_y_within(self, svg_text: str, max_y: float) -> None:
        for m in re.finditer(r'points="([^"]+)"', svg_text):
            for pair in m.group(1).strip().split():
                _, y_str = pair.split(",")
                self.assertLessEqual(float(y_str), max_y, f"Polygon y={y_str} exceeds {max_y}")
        for m in re.finditer(r'\by="([0-9.]+)"', svg_text):
            self.assertLessEqual(float(m.group(1)), max_y, f"Attribute y={m.group(1)} exceeds {max_y}")

    def test_hero_and_skyline_all_themes_and_54_week_bounds(self) -> None:
        fixture_payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        parsed = generate_3d_contrib.parse_graphql_payload(fixture_payload, self.repo_slugs)
        stats = generate_3d_contrib.compute_stats(parsed["days"])

        # Synthetic 54-week calendar (372 days starting Saturday)
        parsed_54 = generate_3d_contrib.parse_graphql_payload(
            _make_graphql_payload(372, start_date=dt.date(2025, 11, 22)), self.repo_slugs
        )
        stats_54 = generate_3d_contrib.compute_stats(parsed_54["days"])
        self.assertGreaterEqual(max(d.week for d in parsed_54["days"]) + 1, 54)

        for theme in THEME_NAMES:
            for mode in ("dark", "light"):
                hero = render_hero_svg(self.profile, theme, mode)
                self.assertEqual(validate_svg_document(hero, f"hero-{theme}-{mode}"), [])
                self._assert_all_y_within(hero, 270.0)

                sky = generate_3d_contrib.render_svg(self.profile["handle"], parsed["days"], stats, theme, mode)
                self.assertEqual(validate_svg_document(sky, f"sky-{theme}-{mode}"), [])
                self.assertNotIn("PEAK / DAY", sky)
                self.assertNotIn("Peak:", sky)
                self._assert_all_y_within(sky, 456.0)

                sky54 = generate_3d_contrib.render_svg(self.profile["handle"], parsed_54["days"], stats_54, theme, mode)
                self.assertEqual(validate_svg_document(sky54, f"sky54-{theme}-{mode}"), [])
                self._assert_all_y_within(sky54, 456.0)

    def test_build_dist_packages_complete_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = pathlib.Path(tmpdir) / "dist"
            rc = generate_3d_contrib.main(
                [
                    "--profile",
                    str(REPO_ROOT / "profile.json"),
                    "--repo-root",
                    str(REPO_ROOT),
                    "--out-dir",
                    str(out_dir),
                    "--date",
                    "2026-11-08",
                    "--telemetry-fixture",
                    str(FIXTURE_PATH),
                ]
            )
            self.assertEqual(rc, 0)
            for rel in (
                "index.html",
                "styles.css",
                "app.js",
                "telemetry.json",
                "profile.json",
                "assets/banner-3d-dark.svg",
                "assets/banner-3d-light.svg",
                "assets/contrib-3d-dark.svg",
                "assets/contrib-3d-light.svg",
                "assets/stack-3d-dark.svg",
                "assets/stack-3d-light.svg",
                "assets/icons/coldpin-dark.svg",
                "assets/icons/medical-light.svg",
                "assets/icons/contact-portfolio-dark.svg",
            ):
                self.assertTrue((out_dir / rel).exists(), f"Missing dist artifact: {rel}")

            tel = json.loads((out_dir / "telemetry.json").read_text(encoding="utf-8"))
            self.assertEqual(tel["active_theme"], "diwali")
            self.assertIn("active_days", tel["stats"])

    def test_camo_purger_dedup_and_non_fatal_500(self) -> None:
        sample_html = (
            '<picture>'
            '<source media="(prefers-color-scheme: dark)" srcset="https://camo.githubusercontent.com/aaa 1x, https://camo.githubusercontent.com/bbb 2x">'
            '<source media="(prefers-color-scheme: light)" srcset="https://camo.githubusercontent.com/ccc">'
            '<img src="https://camo.githubusercontent.com/ccc" alt="test">'
            '<img src="https://example.com/ignored.png">'
            '</picture>'
        )
        urls = purge_camo.extract_camo_urls(sample_html)
        self.assertEqual(
            urls,
            [
                "https://camo.githubusercontent.com/aaa",
                "https://camo.githubusercontent.com/bbb",
                "https://camo.githubusercontent.com/ccc",
            ],
        )

        err_500 = urllib.error.HTTPError("https://camo.githubusercontent.com/bbb", 500, "Server Error", {}, io.BytesIO(b""))
        with mock.patch(
            "urllib.request.urlopen",
            side_effect=[
                _FakeHTTPResponse(sample_html, 200),
                _FakeHTTPResponse("", 200),
                err_500,
                _FakeHTTPResponse("", 200),
            ],
        ):
            rc = purge_camo.main(["--repo", "hynko431/hynko431"])
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
